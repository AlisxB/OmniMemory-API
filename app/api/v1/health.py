"""Endpoint de health — health check da v1."""
from fastapi import APIRouter

# Health check está no main.py em /health (nível raiz)
# Este router existe para manter consistência de estrutura
router = APIRouter(tags=["observability"])
