"""
MessageBufferService — versão async completa.

CORREÇÃO do projeto original:
- RedisManager era síncrono — agora é async
- Usa AsyncSessionLocal com imports limpos
"""
import asyncio
import logging

from ..database import AsyncSessionLocal

logger = logging.getLogger(__name__)


class MessageBufferService:

    @staticmethod
    async def process_message(session_id: str, content: str, window_seconds: int):
        """
        Adiciona mensagem ao buffer e agenda o disparador após a janela de silêncio.
        Se nenhuma nova mensagem chegar durante `window_seconds`, agrega e dispara webhook.
        """
        from ..redis import RedisManager

        logger.info(f"Buffer: session={session_id} window={window_seconds}s")

        # 1. Registrar no buffer e incrementar ID
        await RedisManager.add_to_buffer(session_id, content)
        current_msg_id = await RedisManager.set_last_message_id(session_id)

        # 2. Aguardar janela de silêncio
        await asyncio.sleep(window_seconds)

        # 3. Verificar se ainda é a mensagem mais recente
        last_msg_id = await RedisManager.get_last_message_id(session_id)

        if current_msg_id != last_msg_id:
            logger.info(f"Buffer skip: novas mensagens chegaram para session={session_id}")
            return

        # 4. Silêncio detectado — agregar e disparar
        async with AsyncSessionLocal() as db:
            try:
                from sqlalchemy.future import select
                from sqlalchemy.orm import selectinload
                from ..domain.sessions.model import Session

                full_content = await RedisManager.get_and_clear_buffer(session_id)

                if not full_content:
                    logger.info(f"Buffer vazio para session={session_id}")
                    return

                session_stmt = (
                    select(Session)
                    .filter(Session.id == session_id)
                    .options(selectinload(Session.user))
                )
                session = (await db.execute(session_stmt)).scalars().first()

                if not session:
                    logger.error(f"Session {session_id} não encontrada no DB durante buffer.")
                    return

                tenant_id = session.tenant_id
                ext_user_id = session.user.external_id if session.user else "unknown"
                user_channel = session.user.channel if session.user else "unknown"
                metadata = dict(session.metadata_json) if session.metadata_json else {}

                logger.info(
                    f"Buffer window closed: session={session_id} "
                    f"content_len={len(full_content)} chars"
                )

                # Disparar via WebhookWorker (não sincrono)
                from ..workers.webhook_worker import WebhookWorker
                await WebhookWorker.enqueue(
                    tenant_id,
                    "session.ready",
                    {
                        "session_id": session_id,
                        "tenant_id": tenant_id,
                        "external_user_id": ext_user_id,
                        "channel": user_channel,
                        "full_content": full_content,
                        "metadata": metadata,
                    },
                )

            except Exception as e:
                logger.error(f"Buffer processing error for session={session_id}: {e}", exc_info=True)
