"""Router central do Admin — agrega sub-routers."""
from fastapi import APIRouter

from .auth import router as auth_router
from .tenants import router as tenants_router
from .analytics import router as analytics_router

router = APIRouter()
router.include_router(auth_router)
router.include_router(tenants_router)
router.include_router(analytics_router)
