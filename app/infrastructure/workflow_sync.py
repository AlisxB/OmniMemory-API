import logging
import httpx
import asyncio
from ..database import AsyncSessionLocal
from ..domain.messages.model import Message
from ..redis import RedisManager
from ..config import settings

logger = logging.getLogger(__name__)

class WorkflowSyncService:
    @staticmethod
    async def sync_message_tokens(message_id: int):
        """
        Tenta buscar o total de tokens de uma execução no n8n.
        Deve ser chamado em background task após alguns segundos.
        """
        if not settings.n8n_url or not settings.n8n_api_key:
            return

        async with AsyncSessionLocal() as db:
            stmt = select(Message).filter(Message.id == message_id)
            message = (await db.execute(stmt)).scalars().first()

            if not message or not message.execution_id:
                return

            # Aguardar um pouco para garantir que o workflow terminou (n8n logs)
            await asyncio.sleep(5)

            tokens = await WorkflowSyncService.get_execution_tokens(message.execution_id)
            if tokens > 0:
                diff = tokens - (message.tokens_used or 0)
                if diff != 0:
                    message.tokens_used = tokens
                    await db.commit()
                    # Atualizar Redis com a diferença
                    from ..domain.sessions.model import Session
                    stmt_s = select(Session).filter(Session.id == message.session_id)
                    session = (await db.execute(stmt_s)).scalars().first()
                    if session:
                        await RedisManager.record_usage(session.tenant_id, tokens=diff)
                        logger.info(f"Sincronizados {tokens} tokens da execução {message.execution_id}")

    @staticmethod
    async def get_execution_tokens(execution_id: str) -> int:
        """
        Consulta a API do n8n para obter metadados da execução e extrair tokens.
        """
        try:
            # url format: http://n8n:5678/api/v1/executions/{id}
            url = f"{settings.n8n_url.rstrip('/')}/api/v1/executions/{execution_id}"
            headers = {"X-N8N-API-KEY": settings.n8n_api_key}
            
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(url, headers=headers)
                if r.status_code != 200:
                    return 0
                
                data = r.json()
                # Lógica para extrair tokens do JSON da n8n
                # Geralmente fica em data['data']['resultData']['runData']
                # Mas vamos fazer uma busca recursiva simples ou focar no padrão OpenAI
                return WorkflowSyncService._extract_tokens_from_json(data)
        except Exception as e:
            logger.error(f"Erro ao buscar execução {execution_id} no n8n: {e}")
            return 0

    @staticmethod
    def _extract_tokens_from_json(data: any) -> int:
        """Busca campos comuns de tokens em um JSON arbitrário de execução."""
        total = 0
        if isinstance(data, dict):
            # Campos comuns
            if "total_tokens" in data: return int(data["total_tokens"])
            if "usage" in data and isinstance(data["usage"], dict):
                return int(data["usage"].get("total_tokens", 0))
            if "tokens" in data and isinstance(data["tokens"], int): return data["tokens"]
            
            # Recursal
            for v in data.values():
                res = WorkflowSyncService._extract_tokens_from_json(v)
                if res > 0: total += res
        elif isinstance(data, list):
            for item in data:
                res = WorkflowSyncService._extract_tokens_from_json(item)
                if res > 0: total += res
        return total
