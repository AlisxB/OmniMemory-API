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
    async def enqueue(tenant_id: str, event: str, payload: dict, webhook_id: int = None):
        """Adiciona um evento à fila de webhooks no Redis."""
        try:
            from ..redis import get_redis
            r = await get_redis()
            job = json.dumps({
                "tenant_id": tenant_id,
                "event": event,
                "payload": payload,
                "webhook_id": webhook_id,
                "attempts": 0,
                "created_at": time.time(),
            })
            await r.rpush(WEBHOOK_QUEUE_KEY, job)
            if webhook_id is None:
                logger.info(f"Webhook event enqueued: event={event} tenant={tenant_id}")
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
                await r.ping()
                
                while True:
                    try:
                        item = await r.blpop(WEBHOOK_QUEUE_KEY, timeout=5)
                        if not item:
                            continue
                        
                        _, raw = item
                        job = json.loads(raw)
                        # Dispara o processamento em background para não travar a fila
                        asyncio.create_task(WebhookWorker._dispatch_job(job))
                        
                    except asyncio.CancelledError:
                        return
                    except Exception as e:
                        logger.error(f"WebhookWorker Loop Error: {e}")
                        await asyncio.sleep(1)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"WebhookWorker Redis Error: {e} — reconectando em 5s")
                await asyncio.sleep(5)

    @staticmethod
    async def _dispatch_job(job: dict):
        """
        Lógica de despacho:
        1. Se webhook_id é None: busca todos os destinos e cria jobs específicos.
        2. Se webhook_id está presente: envia apenas para aquele destino com retry.
        """
        from ..redis import get_redis
        from sqlalchemy.future import select
        from sqlalchemy.orm import selectinload

        tenant_id = job.get("tenant_id")
        event = job.get("event")
        payload = job.get("payload")
        webhook_id = job.get("webhook_id")
        attempts = job.get("attempts", 0)

        try:
            async with AsyncSessionLocal() as db:
                # FASE 1: Distribuição (Splitter)
                if webhook_id is None:
                    stmt = select(WebhookSubscription).filter(
                        WebhookSubscription.tenant_id == tenant_id,
                        WebhookSubscription.is_active == True,
                    )
                    webhooks = (await db.execute(stmt)).scalars().all()
                    
                    for wh in webhooks:
                        # Filtrar por evento
                        if wh.events != ["*"] and event not in wh.events:
                            continue
                        # Enfileira um job específico para esta URL
                        await WebhookWorker.enqueue(tenant_id, event, payload, webhook_id=wh.id)
                    return

                # FASE 2: Entrega Individual
                stmt = select(WebhookSubscription).filter(WebhookSubscription.id == webhook_id)
                wh = (await db.execute(stmt)).scalars().first()

                if not wh or not wh.is_active:
                    return

                # Payload final híbrido (raiz + data)
                full_payload = {
                    "event": event,
                    "tenant_id": tenant_id,
                    "timestamp": time.time(),
                    "data": payload,
                }
                if isinstance(payload, dict):
                    full_payload.update(payload)
                
                body = json.dumps(full_payload)
                signature = HMACSigner.sign(wh.secret, body)

                logger.info(f"Webhook SEND: event={event} url={wh.url} (Attempt {attempts+1})")
                
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
                        logger.info(f"Webhook SUCCESS: event={event} url={wh.url}")
                except Exception as e:
                    logger.warning(f"Webhook FAILED: url={wh.url} error={e}")
                    
                    if attempts < MAX_RETRIES:
                        # Re-enfileira para tentar mais tarde
                        delay = RETRY_DELAYS[min(attempts, len(RETRY_DELAYS) - 1)]
                        logger.info(f"Webhook RETRY: agendando em {delay}s para {wh.url}")
                        
                        # Aguarda o delay fora da fila do Redis, mas dentro da task
                        await asyncio.sleep(delay)
                        job["attempts"] = attempts + 1
                        r = await get_redis()
                        await r.rpush(WEBHOOK_QUEUE_KEY, json.dumps(job))
                    else:
                        logger.error(f"Webhook DEAD: url={wh.url} após {attempts+1} tentativas")

        except Exception as e:
            logger.error(f"Critical error in _dispatch_job: {e}", exc_info=True)
