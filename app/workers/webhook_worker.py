"""Worker de processamento assíncrono de webhooks."""
import asyncio
import json
import logging
import time

import httpx

from ..database import AsyncSessionLocal
from ..domain.webhooks.model import WebhookSubscription
from ..core.security import HMACSigner

logger = logging.getLogger(__name__)

WEBHOOK_QUEUE_KEY = "webhook_queue"
MAX_RETRIES = 3
RETRY_DELAYS = [5, 30, 300]  # segundos (backoff exponencial simplificado)


class WebhookWorker:
    """Processa a fila de webhooks de forma assíncrona e resiliente."""

    @staticmethod
    async def enqueue(tenant_id: str, event: str, payload: dict):
        """Adiciona um evento à fila de webhooks no Redis."""
        try:
            from ..redis import get_redis
            r = await get_redis()
            job = json.dumps({
                "tenant_id": tenant_id,
                "event": event,
                "payload": payload,
                "attempts": 0,
                "created_at": time.time(),
            })
            await r.rpush(WEBHOOK_QUEUE_KEY, job)
            logger.info(f"Webhook enqueued: event={event} tenant={tenant_id}")
        except Exception as e:
            logger.error(f"Failed to enqueue webhook: {e}")

    @staticmethod
    async def process_queue():
        """Loop infinito que processa jobs da fila de webhooks."""
        from ..redis import get_redis
        logger.info("WebhookWorker: Iniciando loop de processamento...")

        while True:
            try:
                r = await get_redis()
                # Ping para testar conexão
                await r.ping()
                logger.info("WebhookWorker: Status Redis OK")

                while True:
                    try:
                        # BLPOP bloqueia até ter item na fila (timeout=5 para checar cancelamento)
                        item = await r.blpop(WEBHOOK_QUEUE_KEY, timeout=5)
                        if not item:
                            continue
                        
                        _, raw = item
                        job = json.loads(raw)
                        logger.info(f"WebhookWorker: Processando evento {job.get('event')}")
                        
                        # Dispara o job
                        asyncio.create_task(WebhookWorker._dispatch_job(job))
                        
                    except asyncio.CancelledError:
                        return
                    except Exception as e:
                        logger.error(f"WebhookWorker Loop Error: {e}", exc_info=True)
                        await asyncio.sleep(1)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"WebhookWorker Connection/Auth Error: {e} — tentando novamente em 5s")
                await asyncio.sleep(5)

    @staticmethod
    async def _dispatch_job(job: dict):
        """Despacha um job de webhook com retry e assinatura HMAC."""
        from ..redis import get_redis
        from sqlalchemy.future import select

        tenant_id = job.get("tenant_id")
        event = job.get("event")
        payload = job.get("payload")
        attempts = job.get("attempts", 0)

        if not tenant_id or not event:
            logger.error(f"WebhookWorker: Job inválido ignorado: {job}")
            return

        try:
            async with AsyncSessionLocal() as db:
                stmt = select(WebhookSubscription).filter(
                    WebhookSubscription.tenant_id == tenant_id,
                    WebhookSubscription.is_active == True,
                )
                webhooks = (await db.execute(stmt)).scalars().all()

                if not webhooks:
                    logger.debug(f"WebhookWorker: Nenhum webhook ativo para tenant {tenant_id}")
                    return

                # Payload final: chaves na raiz + chaves dentro de 'data' para compatibilidade total
                full_payload = {
                    "event": event,
                    "tenant_id": tenant_id,
                    "timestamp": time.time(),
                    "data": payload,  # Mantém estrutura antiga
                }
                # Adiciona todas as chaves do payload original na raiz
                if isinstance(payload, dict):
                    full_payload.update(payload)
                
                body = json.dumps(full_payload)
                for wh in webhooks:
                    # Log de auditoria para cada destino
                    logger.info(f"WebhookWorker: Preparando envio para {wh.url} | Evento: {event} | Payload: {body}")
                    
                    # 1. Filtrar por eventos subscritos
                    if wh.events != ["*"] and event not in wh.events:
                        logger.debug(f"WebhookWorker: Evento {event} ignorado por filtro para {wh.url}")
                        continue

                    # 2. Assinatura HMAC-SHA256
                    signature = HMACSigner.sign(wh.secret, body)

                    # 3. Enviar
                    logger.info(f"WebhookWorker: Enviando {event} para {wh.url} (Tentativa {attempts+1})")
                    try:
                        async with httpx.AsyncClient(timeout=10.0, verify=False) as client:
                            resp = await client.post(
                                wh.url,
                                content=body,
                                headers={
                                    "Content-Type": "application/json",
                                    "X-OmniMemory-Signature": f"sha256={signature}",
                                    "X-OmniMemory-Event": event,
                                    "User-Agent": "OmniMemory-Webhook/2.0",
                                },
                            )
                            resp.raise_for_status()
                            logger.info(f"Webhook SUCCESS: event={event} url={wh.url} status={resp.status_code}")
                    except Exception as e:
                        logger.warning(f"Webhook FAILED: event={event} url={wh.url} attempt={attempts+1} error={e}")
                        
                        if attempts < MAX_RETRIES:
                            # Re-encfileiramento com delay
                            delay = RETRY_DELAYS[min(attempts, len(RETRY_DELAYS) - 1)]
                            logger.info(f"Webhook: Agendando retry em {delay}s para {wh.url}")
                            
                            await asyncio.sleep(delay)
                            job["attempts"] = attempts + 1
                            r = await get_redis()
                            await r.rpush(WEBHOOK_QUEUE_KEY, json.dumps(job))
                        else:
                            logger.error(f"Webhook DEAD: event={event} url={wh.url} após {attempts+1} tentativas")

        except Exception as e:
            logger.error(f"Critical error in _dispatch_job: {e}", exc_info=True)
