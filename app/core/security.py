"""
Módulo de segurança central da OmniMemory API.

Responsável por:
- Hashing e validação de API Keys (bcrypt)
- Geração e validação de JWT (Admin)
- Criptografia de dados sensíveis (AES-256 via Fernet)
- Assinatura HMAC-SHA256 para webhooks
- Proteção SSRF em URLs de webhook
"""
import hashlib
import hmac
import ipaddress
import logging
import re
import secrets
import urllib.parse
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import bcrypt
from cryptography.fernet import Fernet
from jose import JWTError, jwt

from ..config import settings

logger = logging.getLogger(__name__)

# ─── API Key Manager ─────────────────────────────────────────────────────────

class APIKeyManager:
    """Gerencia geração, hash e validação de API Keys dos Tenants."""

    PREFIX = "omni_"  # Prefixo identificador para facilitar revogação

    @staticmethod
    def generate_key() -> str:
        """Gera uma API Key aleatória segura com prefixo identificador."""
        raw = secrets.token_urlsafe(32)
        return f"{APIKeyManager.PREFIX}{raw}"

    @staticmethod
    def hash_key(raw_key: str) -> str:
        """Hash bcrypt da API Key para armazenamento seguro."""
        return bcrypt.hashpw(raw_key.encode(), bcrypt.gensalt()).decode()

    @staticmethod
    def verify_key(raw_key: str, hashed_key: str) -> bool:
        """Verifica se a raw key corresponde ao hash armazenado."""
        try:
            return bcrypt.checkpw(raw_key.encode(), hashed_key.encode())
        except Exception:
            return False

    @staticmethod
    def parse_header_key(header_value: str) -> tuple[str, str]:
        """
        Faz o parse do header X-API-Key no formato 'tenant_id:raw_key'.
        Retorna (tenant_id, raw_key).
        """
        if ":" not in header_value:
            raise ValueError("X-API-Key inválida: formato esperado 'tenant_id:key'")
        tenant_id, _, raw_key = header_value.partition(":")
        return tenant_id.strip(), raw_key.strip()


# ─── JWT Manager (Admin) ─────────────────────────────────────────────────────

class JWTManager:
    """Gerencia tokens JWT para autenticação do Admin Dashboard."""

    @staticmethod
    def create_access_token(data: dict[str, Any]) -> str:
        """Cria um JWT de acesso com expiração curta (15min default)."""
        payload = data.copy()
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.jwt_access_token_expire_minutes
        )
        payload.update({"exp": expire, "type": "access"})
        return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)

    @staticmethod
    def create_refresh_token(data: dict[str, Any]) -> str:
        """Cria um JWT de refresh com expiração longa (7 dias default)."""
        payload = data.copy()
        expire = datetime.now(timezone.utc) + timedelta(
            days=settings.jwt_refresh_token_expire_days
        )
        payload.update({"exp": expire, "type": "refresh"})
        return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)

    @staticmethod
    def decode_token(token: str) -> Optional[dict[str, Any]]:
        """Decodifica e valida um JWT. Retorna None se inválido/expirado."""
        try:
            return jwt.decode(
                token,
                settings.secret_key,
                algorithms=[settings.jwt_algorithm],
            )
        except JWTError as e:
            logger.warning(f"JWT decode failed: {e}")
            return None

    @staticmethod
    def verify_admin_credentials(password: str) -> bool:
        """Verifica se a senha fornecida é a senha administrativa."""
        return secrets.compare_digest(password, settings.admin_password)


# ─── Crypto Manager (Dados em Repouso) ──────────────────────────────────────

class CryptoManager:
    """Criptografia AES-256 via Fernet para dados sensíveis (memórias)."""

    _fernet: Optional[Fernet] = None

    @classmethod
    def _get_fernet(cls) -> Optional[Fernet]:
        if cls._fernet is None and settings.encryption_key:
            try:
                cls._fernet = Fernet(settings.encryption_key.encode())
            except Exception as e:
                logger.error(f"Fernet initialization failed: {e}")
        return cls._fernet

    @classmethod
    def encrypt(cls, value: str) -> str:
        """Criptografa uma string. Retorna o valor original se sem chave configurada."""
        fernet = cls._get_fernet()
        if not fernet:
            return value  # Graceful degradation sem chave
        try:
            return fernet.encrypt(value.encode()).decode()
        except Exception as e:
            logger.error(f"Encryption failed: {e}")
            return value

    @classmethod
    def decrypt(cls, value: str) -> str:
        """Descriptografa uma string. Retorna o valor original se sem chave ou falha."""
        fernet = cls._get_fernet()
        if not fernet:
            return value
        try:
            return fernet.decrypt(value.encode()).decode()
        except Exception:
            return value  # Valor pode não estar criptografado (migração)

    @staticmethod
    def generate_fernet_key() -> str:
        """Gera uma nova Fernet key. Usar via CLI no setup inicial."""
        return Fernet.generate_key().decode()


# ─── HMAC Signer (Webhooks) ──────────────────────────────────────────────────

class HMACSigner:
    """Assinatura HMAC-SHA256 para webhooks seguros."""

    @staticmethod
    def sign(secret: str, payload: str) -> str:
        """Gera a assinatura HMAC-SHA256 do payload."""
        return hmac.new(
            secret.encode(),
            payload.encode(),
            hashlib.sha256,
        ).hexdigest()

    @staticmethod
    def verify(secret: str, payload: str, signature: str) -> bool:
        """Verifica se a assinatura é válida (comparação segura contra timing attacks)."""
        expected = HMACSigner.sign(secret, payload)
        return hmac.compare_digest(expected, signature)


# ─── SSRF Protection ─────────────────────────────────────────────────────────

# Ranges de IP privados/reservados que não devem ser acessados via webhook
_BLOCKED_RANGES = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),  # Link-local
    ipaddress.ip_network("::1/128"),          # IPv6 loopback
    ipaddress.ip_network("fc00::/7"),         # IPv6 privado
]

_BLOCKED_HOSTNAMES = re.compile(
    r"^(localhost|internal|metadata\.google\.internal|169\.254\.\d+\.\d+)$",
    re.IGNORECASE,
)


def validate_webhook_url(url: str) -> str:
    """
    Valida uma URL de webhook contra ataques SSRF.
    Bloqueia IPs privados, loopback e hostnames internos.

    Raises ValueError se a URL for suspeita.
    Returns a URL original se válida.
    """
    try:
        parsed = urllib.parse.urlparse(url)
    except Exception:
        raise ValueError(f"URL inválida: {url}")

    if parsed.scheme not in ("http", "https"):
        raise ValueError("Webhook URL deve usar http ou https")

    hostname = parsed.hostname or ""

    if _BLOCKED_HOSTNAMES.match(hostname):
        raise ValueError(f"Webhook URL com hostname interno não permitido: {hostname}")

    # Verificar se é um IP e se é privado
    try:
        ip = ipaddress.ip_address(hostname)
        for blocked_range in _BLOCKED_RANGES:
            if ip in blocked_range:
                raise ValueError(f"Webhook URL com IP privado não permitido: {hostname}")
    except ValueError as e:
        if "not permitted" in str(e) or "interno" in str(e):
            raise
        # Não é um IP — é um hostname (ok, DNS resolve em runtime)
        pass

    return url
