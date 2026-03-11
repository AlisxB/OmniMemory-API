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
        logger.debug(f"Webhook enqueued: event={event} tenant={tenant_id}")

    @staticmethod
    async def process_queue():
        """Loop infinito que processa jobs da fila de webhooks."""
        from ..config import settings as _settings
        logger.info("WebhookWorker: processando fila...")

        # Conexão dedicada para BLPOP — separada do pool principal da API
        # BLPOP mantém a conexão bloqueada, o que conflitaria com o pool
        while True:
            worker_redis = None
            try:
                import redis.asyncio as aioredis
                worker_redis = aioredis.from_url(
                    _settings.redis_url,
                    encoding="utf-8",
                    decode_responses=True,
                    max_connections=2,
                )
                logger.info("WebhookWorker: conectado ao Redis")

                while True:
                    try:
                        # BLPOP bloqueia até ter item na fila
                        item = await worker_redis.blpop(WEBHOOK_QUEUE_KEY, timeout=5)
                        if not item:
                            continue
                        _, raw = item
                        job = json.loads(raw)
                        await WebhookWorker._dispatch_job(job)
                    except asyncio.CancelledError:
                        return
                    except Exception as e:
                        logger.error(f"WebhookWorker job error: {e}", exc_info=True)
                        await asyncio.sleep(1)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"WebhookWorker Redis connection error: {e} — reconectando em 5s")
                await asyncio.sleep(5)
            finally:
                if worker_redis:
                    try:
                        await worker_redis.aclose()
                    except Exception:
                        pass

    @staticmethod
    async def _dispatch_job(job: dict):
        """Despacha um job de webhook com retry e assinatura HMAC."""
        from ..redis import get_redis
        from sqlalchemy.future import select

        tenant_id = job["tenant_id"]
        event = job["event"]
        payload = job["payload"]
        attempts = job.get("attempts", 0)

        async with AsyncSessionLocal() as db:
            stmt = select(WebhookSubscription).filter(
                WebhookSubscription.tenant_id == tenant_id,
                WebhookSubscription.is_active == True,
            )
            webhooks = (await db.execute(stmt)).scalars().all()

            full_payload = {
                "event": event,
                "tenant_id": tenant_id,
                "data": payload,
                "timestamp": time.time(),
            }
            body = json.dumps(full_payload)

            for wh in webhooks:
                # Filtrar por eventos subscritos
                if wh.events != ["*"] and event not in wh.events:
                    continue

                # Assinatura HMAC-SHA256
                signature = HMACSigner.sign(wh.secret, body)

                try:
                    async with httpx.AsyncClient(timeout=10.0) as client:
                        resp = await client.post(
                            wh.url,
                            content=body,
                            headers={
                                "Content-Type": "application/json",
                                "X-OmniMemory-Signature": f"sha256={signature}",
                                "X-OmniMemory-Event": event,
                            },
                        )
                        if resp.status_code >= 400:
                            raise httpx.HTTPStatusError(
                                f"HTTP {resp.status_code}", request=resp.request, response=resp
                            )
                        logger.info(f"Webhook dispatched: event={event} url={wh.url} status={resp.status_code}")
                except Exception as e:
                    logger.warning(f"Webhook failed: event={event} url={wh.url} attempt={attempts+1} error={e}")
                    if attempts < MAX_RETRIES:
                        # Recolocar na fila com delay
                        r = await get_redis()
                        delay = RETRY_DELAYS[min(attempts, len(RETRY_DELAYS) - 1)]
                        job["attempts"] = attempts + 1
                        await asyncio.sleep(delay)
                        await r.rpush(WEBHOOK_QUEUE_KEY, json.dumps(job))
