"""
Router central da API v1 — agrega todos os sub-routers de domínio.
"""
from fastapi import APIRouter

from .context import router as context_router
from .memories import router as memories_router
from .webhooks import router as webhooks_router
from .prompts import router as prompts_router
from .analytics import router as analytics_router
from .audio import router as audio_router
from .health import router as health_router

router = APIRouter()
router.include_router(health_router)
router.include_router(context_router)
router.include_router(memories_router)
router.include_router(webhooks_router)
router.include_router(prompts_router)
router.include_router(analytics_router)
router.include_router(audio_router)
