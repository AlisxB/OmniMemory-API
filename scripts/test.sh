#!/usr/bin/env bash
# scripts/test.sh — Roda os testes localmente com as variáveis corretas
# Uso: bash scripts/test.sh [unit|integration|all] [--cov]

set -e

SUITE=${1:-all}
COV_FLAG=${2:-}

# Configurar variáveis de ambiente para teste
export ENVIRONMENT=test
export SECRET_KEY="local_test_secret_key_32_chars_minimum_!!"
export ADMIN_PASSWORD="test_admin_pass"
export SUPER_ADMIN_KEY="local_test_super_admin_key"
export DATABASE_URL="sqlite+aiosqlite:///:memory:"
export REDIS_HOST="localhost"
export ENCRYPTION_KEY=""
export GROQ_API_KEY="test_key"

echo "🧪 OmniMemory API — Rodando testes..."
echo "Suite: $SUITE"
echo ""

COV_OPTS=""
if [ "$COV_FLAG" == "--cov" ]; then
    COV_OPTS="--cov=app --cov-report=term-missing --cov-report=html:htmlcov"
fi

case $SUITE in
    unit)
        echo "Rodando testes unitários..."
        pytest tests/unit/ -v $COV_OPTS
        ;;
    integration)
        echo "Rodando testes de integração..."
        pytest tests/integration/ -v $COV_OPTS
        ;;
    all)
        echo "Rodando todos os testes..."
        pytest tests/ -v $COV_OPTS
        ;;
    *)
        echo "Uso: $0 [unit|integration|all] [--cov]"
        exit 1
        ;;
esac

echo ""
echo "✅ Testes concluídos!"

if [ "$COV_FLAG" == "--cov" ]; then
    echo "📊 Coverage report em: htmlcov/index.html"
fi
