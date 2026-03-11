"""Envelope de resposta padrão da API."""
from typing import Any, Optional


def wrap_response(data: Any, request_id: Optional[str] = None) -> dict:
    """
    Envolve qualquer dado na estrutura de resposta padrão da OmniMemory API.
    Garante consistência em todos os endpoints.
    """
    return {
        "success": True,
        "request_id": request_id,
        "data": data,
    }
