"""
Testes unitários — Idempotência e Cache.
"""
import json
import pytest
from unittest.mock import AsyncMock, patch

from app.core.security import APIKeyManager, JWTManager


# ─── Idempotência ─────────────────────────────────────────────────────────────

class TestIdempotency:
    """Testa o decorator de idempotência sem precisar de HTTP client."""

    @pytest.mark.asyncio
    async def test_sem_chave_executa_normalmente(self):
        """Sem X-Idempotency-Key → função executada normalmente."""
        from app.core.idempotency import idempotency_key_required
        from unittest.mock import AsyncMock, MagicMock
        from fastapi import Request

        mock_request = MagicMock(spec=Request)
        mock_request.headers = {}
        mock_request.state.request_id = "test-rid"

        call_count = 0

        @idempotency_key_required
        async def fake_endpoint(request, req=None):
            nonlocal call_count
            call_count += 1
            return {"result": call_count}

        await fake_endpoint(mock_request)
        await fake_endpoint(mock_request)

        assert call_count == 2  # Executado 2x sem chave de idempotência


# ─── Cache Decorator ─────────────────────────────────────────────────────────

class TestCacheDecorator:

    @pytest.mark.asyncio
    async def test_cache_hit_nao_executa_funcao(self):
        """Se dado está no cache, a função não deve ser chamada."""
        from app.core.cache import cached

        call_count = 0

        with patch("app.core.cache.RedisManager") as mock_rm:
            # Primeiro call: cache miss
            mock_rm.get_cache = AsyncMock(return_value=None)
            mock_rm.set_cache = AsyncMock()

            @cached(ttl_seconds=300, key_fn=lambda tenant_id: f"test:{tenant_id}")
            async def get_data(tenant_id: str):
                nonlocal call_count
                call_count += 1
                return {"value": "expensive_result"}

            result1 = await get_data("tenant_a")
            assert call_count == 1
            assert result1["value"] == "expensive_result"

            # Segundo call: cache hit
            mock_rm.get_cache = AsyncMock(return_value={"value": "cached_result"})
            result2 = await get_data("tenant_a")
            assert call_count == 1  # Não chamou novamente
            assert result2["value"] == "cached_result"

    @pytest.mark.asyncio
    async def test_cache_diferente_por_chave(self):
        """Chaves diferentes devem ter caches independentes."""
        from app.core.cache import cached
        results = []

        with patch("app.core.cache.RedisManager") as mock_rm:
            mock_rm.get_cache = AsyncMock(return_value=None)
            mock_rm.set_cache = AsyncMock()

            @cached(ttl_seconds=300, key_fn=lambda x: f"data:{x}")
            async def get_by_id(x: str):
                results.append(x)
                return {"id": x}

            await get_by_id("a")
            await get_by_id("b")
            assert "a" in results
            assert "b" in results


# ─── Segurança Adicional ───────────────────────────────────────────────────────

class TestSecurityEdgeCases:

    def test_api_key_prefix_correto(self):
        key = APIKeyManager.generate_key()
        assert key.startswith("omni_")
        assert len(key) > 40

    def test_bcrypt_hash_diferente_a_cada_geracao(self):
        """bcrypt.gensalt() → hash diferente para a mesma senha."""
        raw = "omni_mesma_chave"
        h1 = APIKeyManager.hash_key(raw)
        h2 = APIKeyManager.hash_key(raw)
        assert h1 != h2  # Salts diferentes
        # Mas ambas são válidas
        assert APIKeyManager.verify_key(raw, h1)
        assert APIKeyManager.verify_key(raw, h2)

    def test_jwt_expirado_retorna_none(self):
        """JWT expirado deve retornar None."""
        from jose import jwt
        from datetime import datetime, timezone, timedelta
        import os

        expired_payload = {
            "sub": "admin",
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),  # Já expirado
        }
        secret = os.environ.get("SECRET_KEY", "test_key")
        expired_token = jwt.encode(expired_payload, secret, algorithm="HS256")

        result = JWTManager.decode_token(expired_token)
        assert result is None

    def test_hmac_different_payloads(self):
        """Mesmo secret, payloads diferentes → assinaturas diferentes."""
        from app.core.security import HMACSigner
        sig1 = HMACSigner.sign("secret", "payload_a")
        sig2 = HMACSigner.sign("secret", "payload_b")
        assert sig1 != sig2

    def test_fernet_encrypt_decrypt_roundtrip(self):
        """Criptografar → descriptografar deve retornar o valor original."""
        from cryptography.fernet import Fernet
        from unittest.mock import patch

        key = Fernet.generate_key().decode()
        original = "Dado sensível do usuário: CPF 000.000.000-00"

        with patch("app.core.security.settings") as mock_settings:
            mock_settings.encryption_key = key
            from app.core.security import CryptoManager
            CryptoManager._fernet = None  # Forçar reinicialização

            encrypted = CryptoManager.encrypt(original)
            decrypted = CryptoManager.decrypt(encrypted)

            assert encrypted != original
            assert decrypted == original
            CryptoManager._fernet = None  # Cleanup
