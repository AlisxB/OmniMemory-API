"""
Teste unitário — Módulo de Segurança.
"""
import pytest
from app.core.security import (
    APIKeyManager,
    JWTManager,
    CryptoManager,
    HMACSigner,
    validate_webhook_url,
)


class TestAPIKeyManager:
    def test_generate_key_has_prefix(self):
        key = APIKeyManager.generate_key()
        assert key.startswith("omni_")

    def test_hash_and_verify(self):
        raw = APIKeyManager.generate_key()
        hashed = APIKeyManager.hash_key(raw)
        assert APIKeyManager.verify_key(raw, hashed) is True

    def test_wrong_key_fails(self):
        hashed = APIKeyManager.hash_key("omni_correct_key")
        assert APIKeyManager.verify_key("omni_wrong_key", hashed) is False

    def test_parse_header_key(self):
        tenant_id, raw_key = APIKeyManager.parse_header_key("meu_tenant:omni_abc123")
        assert tenant_id == "meu_tenant"
        assert raw_key == "omni_abc123"

    def test_parse_invalid_key_raises(self):
        with pytest.raises(ValueError):
            APIKeyManager.parse_header_key("invalid_no_colon")


class TestJWTManager:
    def test_create_and_decode_access_token(self):
        token = JWTManager.create_access_token({"sub": "admin"})
        decoded = JWTManager.decode_token(token)
        assert decoded is not None
        assert decoded["sub"] == "admin"
        assert decoded["type"] == "access"

    def test_create_and_decode_refresh_token(self):
        token = JWTManager.create_refresh_token({"sub": "admin"})
        decoded = JWTManager.decode_token(token)
        assert decoded is not None
        assert decoded["type"] == "refresh"

    def test_invalid_token_returns_none(self):
        assert JWTManager.decode_token("totally_invalid_token") is None


class TestHMACSigner:
    def test_sign_and_verify(self):
        secret = "mysecret"
        payload = '{"event": "test"}'
        sig = HMACSigner.sign(secret, payload)
        assert HMACSigner.verify(secret, payload, sig) is True

    def test_wrong_secret_fails(self):
        sig = HMACSigner.sign("correct_secret", "payload")
        assert HMACSigner.verify("wrong_secret", "payload", sig) is False


class TestSSRFProtection:
    def test_valid_public_url(self):
        url = validate_webhook_url("https://meusite.com/webhook")
        assert url == "https://meusite.com/webhook"

    def test_localhost_blocked(self):
        with pytest.raises(ValueError, match="interno"):
            validate_webhook_url("https://localhost/webhook")

    def test_private_ip_blocked(self):
        with pytest.raises(ValueError, match="privado"):
            validate_webhook_url("http://192.168.1.1/evil")

    def test_loopback_blocked(self):
        with pytest.raises(ValueError):
            validate_webhook_url("http://127.0.0.1/secret")

    def test_non_http_blocked(self):
        with pytest.raises(ValueError, match="http"):
            validate_webhook_url("ftp://evil.com")
