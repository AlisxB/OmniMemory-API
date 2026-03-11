"""
Configuração global de logging com sanitização de dados sensíveis.

CORREÇÃO do projeto original:
O SensitiveFilter estava aplicado apenas ao logger local do main.py.
Aqui aplicamos ao ROOT LOGGER, garantindo cobertura total.
"""
import logging
import re
import sys
from typing import Optional

from ..config import settings

# ─── Padrão de dados sensíveis ───────────────────────────────────────────────
SENSITIVE_PATTERN = re.compile(
    r"(?i)(x-api-key|x-super-admin-key|admin.?password|secret.?key|"
    r"password|token|bearer|authorization|fernet|encryption.?key)"
    r"\s*[=:\"\']\s*([^\s,\"\'\}\]]{4,})",
    re.IGNORECASE,
)


class SensitiveFilter(logging.Filter):
    """
    Filtro que mascara valores sensíveis em TODOS os logs.
    Aplicado ao root logger para garantir cobertura global.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        # Mascarar na mensagem principal
        if record.msg and isinstance(record.msg, str):
            record.msg = SENSITIVE_PATTERN.sub(
                lambda m: f"{m.group(1)}=[MASKED]", record.msg
            )
        # Mascarar nos args da mensagem (formatação lazy do logging)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {
                    k: "[MASKED]" if _is_sensitive_key(k) else v
                    for k, v in record.args.items()
                }
            elif isinstance(record.args, (list, tuple)):
                record.args = tuple(
                    SENSITIVE_PATTERN.sub(lambda m: f"{m.group(1)}=[MASKED]", str(a))
                    if isinstance(a, str)
                    else a
                    for a in record.args
                )
        return True


def _is_sensitive_key(key: str) -> bool:
    """Verifica se uma chave de dict contém nome sensível."""
    sensitive_keys = {
        "password", "token", "secret", "key", "api_key",
        "authorization", "bearer", "fernet", "encryption_key",
    }
    return key.lower() in sensitive_keys


class ColoredFormatter(logging.Formatter):
    """Formatter com cores para desenvolvimento local."""

    COLORS = {
        "DEBUG": "\033[36m",     # Cyan
        "INFO": "\033[32m",      # Green
        "WARNING": "\033[33m",   # Yellow
        "ERROR": "\033[31m",     # Red
        "CRITICAL": "\033[35m",  # Magenta
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, "")
        record.levelname = f"{color}{record.levelname}{self.RESET}"
        return super().format(record)


def configure_logging():
    """
    Configura o sistema de logging global da aplicação.
    Deve ser chamado UMA VEZ no startup, antes de qualquer import de logger.
    """
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    # Limpa handlers existentes no root logger
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(log_level)

    # ─── Handler de saída ───────────────────────────────────────────────────
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(log_level)

    if settings.is_development:
        formatter = ColoredFormatter(
            fmt="%(levelname)s  %(name)s:%(lineno)d  %(message)s",
        )
    else:
        # Produção: formato mais limpo para ingestão por ferramentas como Loki/Datadog
        formatter = logging.Formatter(
            fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%SZ",
        )

    handler.setFormatter(formatter)

    # ─── Aplicar SensitiveFilter GLOBALMENTE ──────────────────────────────
    sensitive_filter = SensitiveFilter()
    root_logger.addFilter(sensitive_filter)
    root_logger.addHandler(handler)

    # ─── Silenciar loggers ruidosos de libs ──────────────────────────────
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.INFO if settings.is_development else logging.WARNING
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)

    logging.getLogger(__name__).info(
        f"Logging configured | level={settings.log_level} | env={settings.environment}"
    )
