"""
SummarizerService — versão refatorada.
Usa Groq (Llama 3) para gerar resumos de sessões expiradas
e armazena como memória de longo prazo criptografada.
"""
import logging
from typing import Optional

from ..database import AsyncSessionLocal
from ..config import settings

logger = logging.getLogger(__name__)


class SummarizerService:

    @staticmethod
    async def summarize_session(session_id: str):
        """
        Gera um resumo de uma sessão encerrada usando Groq e salva como Memory.
        Chamado em background quando uma sessão expira.
        """
        if not settings.groq_api_key:
            logger.warning("GROQ_API_KEY não configurada — sumarização ignorada.")
            return

        async with AsyncSessionLocal() as db:
            try:
                from sqlalchemy.future import select
                from ..domain.sessions.model import Session
                from ..domain.messages.model import Message
                from ..domain.memories.model import Memory, MemoryScope
                from ..core.security import CryptoManager
                from ..core.embeddings import EmbeddingService
                from ..redis import RedisManager

                # Buscar sessão
                session = (await db.execute(
                    select(Session).filter(Session.id == session_id)
                )).scalars().first()
                if not session:
                    logger.warning(f"Session {session_id} not found for summarization.")
                    return

                tenant_id = session.tenant_id
                user_id = session.user_id
                last_interaction = session.last_interaction_at

                # Buscar mensagens
                messages = (await db.execute(
                    select(Message)
                    .filter(Message.session_id == session_id)
                    .order_by(Message.created_at.asc())
                )).scalars().all()

                if not messages:
                    logger.info(f"Session {session_id}: sem mensagens, ignorando sumarização.")
                    return

                # Montar transcript
                transcript = "\n".join(
                    f"{m.role} ({m.created_at.strftime('%d/%m/%Y %H:%M')}): {m.content}"
                    for m in messages
                )

                prompt = f"""Você é um assistente especializado em extrair conhecimento de conversas para memória de longo prazo.

Abaixo está o histórico de uma sessão encerrada. Crie um resumo executivo em PORTUGUÊS cobrindo:
1. OBJETIVO: Qual era o propósito principal da conversa?
2. PONTOS CHAVE: Quais fatos, preferências ou problemas importantes foram mencionados?
3. RESULTADOS: Quais conclusões foram alcançadas ou ações ficaram pendentes?

Seja direto e informativo — o resumo deve ser autoexplicativo sem precisar ler o histórico completo.

HISTÓRICO:
{transcript}

RESUMO:"""

                from groq import AsyncGroq
                client = AsyncGroq(api_key=settings.groq_api_key)
                response = await client.chat.completions.create(
                    model="llama-3.1-8b-instant",
                    messages=[
                        {"role": "system", "content": "Especialista em gestão de conhecimento e memória de longo prazo."},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.3,
                    max_tokens=600,
                )

                summary = response.choices[0].message.content.strip()
                tokens_used = getattr(response.usage, "total_tokens", 0)

                # Enriquecer com data para busca semântica
                date_str = last_interaction.strftime("%d/%m/%Y") if last_interaction else "?"
                final_summary = f"[{date_str}] {summary}"

                # Gerar embedding
                emb = EmbeddingService.get_embedding(final_summary)

                # Salvar como Memory
                key = f"summary_session_{session_id}"
                db_memory = Memory(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    scope=MemoryScope.user,
                    key=key,
                    value=CryptoManager.encrypt(final_summary),
                    embedding=emb,
                )
                db.add(db_memory)
                await db.commit()

                # Registrar uso + invalidar cache
                await RedisManager.record_usage(tenant_id, tokens=tokens_used)
                await RedisManager.delete_cache(f"memories_cache:{tenant_id}:{user_id}")

                # Trigger webhook via worker
                from ..workers.webhook_worker import WebhookWorker
                await WebhookWorker.enqueue(
                    tenant_id,
                    "session.summarized",
                    {"session_id": session_id, "summary": summary[:200] + "..."},
                )

                logger.info(f"Session {session_id} summarized ({tokens_used} tokens).")

            except Exception as e:
                logger.error(f"Summarization failed for session {session_id}: {e}", exc_info=True)
