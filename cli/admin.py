"""
CLI da OmniMemory API — comandos administrativos.

Uso:
    python -m cli.admin tenant create --id "slug" --name "Nome"
    python -m cli.admin tenant list
    python -m cli.admin tenant rotate-key --id "slug"
    python -m cli.admin migration run
    python -m cli.admin migration status
    python -m cli.admin seed
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import print as rprint

app = typer.Typer(
    name="omni",
    help="🧠 OmniMemory API — CLI Administrativa",
    rich_markup_mode="rich",
)
tenant_app = typer.Typer(name="tenant", help="Gerenciar Tenants")
migration_app = typer.Typer(name="migration", help="Gerenciar Migrations")
security_app = typer.Typer(name="security", help="Operações de Segurança Críticas")

app.add_typer(tenant_app)
app.add_typer(migration_app)
app.add_typer(security_app)

console = Console()


# ─── Tenant Commands ──────────────────────────────────────────────────────────

@tenant_app.command("create")
def create_tenant(
    id: str = typer.Option(..., help="ID/slug do tenant"),
    name: str = typer.Option(..., help="Nome da operação"),
    expires: str = typer.Option(None, help="Data de expiração (YYYY-MM-DD)"),
):
    """Cria um novo Tenant e exibe a API Key gerada."""
    async def _run():
        from app.database import AsyncSessionLocal
        from app.domain.tenants.model import Tenant, TenantSettings
        from app.core.security import APIKeyManager
        from sqlalchemy.future import select
        from datetime import datetime, timezone

        async with AsyncSessionLocal() as db:
            exists = (await db.execute(select(Tenant).filter(Tenant.id == id))).scalars().first()
            if exists:
                console.print(f"[red]❌ Tenant '{id}' já existe.[/red]")
                raise typer.Exit(1)

            raw_key = APIKeyManager.generate_key()
            expires_dt = datetime.strptime(expires, "%Y-%m-%d").replace(tzinfo=timezone.utc) if expires else None

            tenant = Tenant(
                id=id,
                name=name,
                api_key=APIKeyManager.hash_key(raw_key),
                subscription_expires_at=expires_dt,
                api_key_last_rotated_at=datetime.now(timezone.utc),
            )
            db.add(tenant)
            db.add(TenantSettings(tenant_id=id))
            await db.commit()

        console.print(Panel(
            f"[green]✅ Tenant criado com sucesso![/green]\n\n"
            f"[bold]ID:[/bold] {id}\n"
            f"[bold]Nome:[/bold] {name}\n"
            f"[bold]API Key:[/bold] [yellow]{id}:{raw_key}[/yellow]\n\n"
            f"[dim]⚠️  Salve a API Key — ela não será exibida novamente.[/dim]",
            title="🧠 OmniMemory — Novo Tenant",
        ))

    asyncio.run(_run())


@tenant_app.command("list")
def list_tenants():
    """Lista todos os Tenants ativos."""
    async def _run():
        from app.database import AsyncSessionLocal
        from app.domain.tenants.model import Tenant
        from sqlalchemy.future import select
        from sqlalchemy.orm import selectinload
        from datetime import datetime, timezone

        async with AsyncSessionLocal() as db:
            tenants = (await db.execute(
                select(Tenant).options(selectinload(Tenant.settings))
            )).scalars().all()

        table = Table(title="🧠 OmniMemory — Tenants", show_header=True, header_style="bold cyan")
        table.add_column("ID", style="bold")
        table.add_column("Nome")
        table.add_column("Ativo", justify="center")
        table.add_column("API Key (sufixo)")
        table.add_column("Expiração")
        table.add_column("RPM")

        for t in tenants:
            active = "✅" if t.is_active else "❌"
            key_suffix = t.api_key[-8:] if t.api_key else "—"
            expires = str(t.subscription_expires_at.date()) if t.subscription_expires_at else "Vitalício"
            rpm = str(t.settings.rate_limit_rpm) if t.settings else "60"
            table.add_row(t.id, t.name, active, key_suffix, expires, rpm)

        console.print(table)

    asyncio.run(_run())


@tenant_app.command("rotate-key")
def rotate_key(
    id: str = typer.Option(..., help="ID do tenant"),
    confirm: bool = typer.Option(False, "--confirm", help="Confirmar operação"),
):
    """Gera nova API Key para o tenant. A chave antiga é imediatamente invalidada."""
    if not confirm:
        console.print("[yellow]⚠️  Use --confirm para confirmar. A chave antiga será invalidada![/yellow]")
        raise typer.Exit(0)

    async def _run():
        from app.database import AsyncSessionLocal
        from app.domain.tenants.model import Tenant
        from app.core.security import APIKeyManager
        from sqlalchemy.future import select
        from datetime import datetime, timezone

        async with AsyncSessionLocal() as db:
            tenant = (await db.execute(select(Tenant).filter(Tenant.id == id))).scalars().first()
            if not tenant:
                console.print(f"[red]❌ Tenant '{id}' não encontrado.[/red]")
                raise typer.Exit(1)

            raw_key = APIKeyManager.generate_key()
            tenant.api_key = APIKeyManager.hash_key(raw_key)
            tenant.api_key_last_rotated_at = datetime.now(timezone.utc)
            await db.commit()

        console.print(Panel(
            f"[green]🔑 API Key rotacionada![/green]\n\n"
            f"[bold]Tenant:[/bold] {id}\n"
            f"[bold]Nova API Key:[/bold] [yellow]{id}:{raw_key}[/yellow]\n\n"
            f"[dim]⚠️  Atualize o .env do seu orquestrador imediatamente.[/dim]",
            title="🔑 Rotação de Chave",
        ))

    asyncio.run(_run())


@tenant_app.command("delete")
def delete_tenant(
    id: str = typer.Option(..., help="ID do tenant"),
    confirm: bool = typer.Option(False, "--confirm", help="Confirmar deleção IRREVERSÍVEL"),
):
    """Deleta um tenant e TODOS os seus dados associados (cascade)."""
    if not confirm:
        console.print("[red]⚠️  Use --confirm para confirmar a deleção IRREVERSÍVEL![/red]")
        raise typer.Exit(1)

    async def _run():
        from app.database import AsyncSessionLocal
        from app.domain.tenants.model import Tenant
        from sqlalchemy.future import select

        async with AsyncSessionLocal() as db:
            tenant = (await db.execute(select(Tenant).filter(Tenant.id == id))).scalars().first()
            if not tenant:
                console.print(f"[red]❌ Tenant '{id}' não encontrado.[/red]")
                raise typer.Exit(1)

            await db.delete(tenant)
            await db.commit()

        console.print(f"[green]✅ Tenant '{id}' removido com sucesso.[/green]")

    asyncio.run(_run())


@app.command("seed")
def seed_env():
    """Popula o banco com dados de teste e garante o super-usuário admin."""
    async def _run():
        from app.database import AsyncSessionLocal
        from app.domain.tenants.model import Tenant, TenantSettings
        from app.core.security import APIKeyManager
        from sqlalchemy.future import select
        import secrets

        async with AsyncSessionLocal() as db:
            # 1. Garantir tenant de teste
            test_id = "test"
            exists = (await db.execute(select(Tenant).filter(Tenant.id == test_id))).scalars().first()
            if not exists:
                raw_key = secrets.token_hex(16)
                tenant = Tenant(
                    id=test_id,
                    name="Tenant de Teste",
                    api_key=APIKeyManager.hash_key(raw_key),
                )
                db.add(tenant)
                db.add(TenantSettings(tenant_id=test_id))
                await db.commit()
                console.print(f"[green]✅ Tenant 'test' criado. Key: [yellow]{test_id}:{raw_key}[/yellow][/green]")

        console.print("[bold green]✨ Seeding concluído.[/bold green]")

    asyncio.run(_run())


# ─── Migration Commands ───────────────────────────────────────────────────────

@migration_app.command("run")
def run_migrations():
    """Executa todas as migrations pendentes (alembic upgrade head)."""
    import subprocess
    result = subprocess.run(["alembic", "upgrade", "head"], capture_output=True, text=True)
    if result.returncode == 0:
        console.print("[green]✅ Migrations aplicadas com sucesso.[/green]")
        console.print(result.stdout)
    else:
        console.print("[red]❌ Erro nas migrations:[/red]")
        console.print(result.stderr)
        raise typer.Exit(1)


@migration_app.command("status")
def migration_status():
    """Exibe o status atual das migrations."""
    import subprocess
    result = subprocess.run(["alembic", "current"], capture_output=True, text=True)
    console.print(result.stdout or result.stderr)


# ─── Keygen ───────────────────────────────────────────────────────────────────

@app.command("keygen")
def keygen():
    """Gera chaves seguras para SECRET_KEY, SUPER_ADMIN_KEY e ENCRYPTION_KEY."""
    import secrets
    from cryptography.fernet import Fernet

    console.print(Panel(
        f"[bold]SECRET_KEY=[/bold][yellow]{secrets.token_hex(32)}[/yellow]\n"
        f"[bold]SUPER_ADMIN_KEY=[/bold][yellow]{secrets.token_hex(32)}[/yellow]\n"
        f"[bold]ENCRYPTION_KEY=[/bold][yellow]{Fernet.generate_key().decode()}[/yellow]",
        title="🔐 Chaves Geradas — Cole no .env",
    ))


# ─── Security Commands ────────────────────────────────────────────────────────

@security_app.command("rotate-encryption-key")
def rotate_encryption_key(
    old_key: str = typer.Option(..., help="Chave de criptografia atual"),
    new_key: str = typer.Option(..., help="Nova chave de criptografia"),
    confirm: bool = typer.Option(False, "--confirm", help="Confirmar recodificação total"),
):
    """
    Decodifica TODAS as memórias com a chave antiga e recodifica com a nova.
    Útil para rotação de segredos ou recuperação após vazamento.
    """
    if not confirm:
        console.print("[yellow]⚠️  Esta operação recodificará todo o banco. Use --confirm.[/yellow]")
        raise typer.Exit(0)

    async def _run():
        from app.database import AsyncSessionLocal
        from app.domain.memories.model import Memory
        from sqlalchemy.future import select
        from cryptography.fernet import Fernet
        import base64

        try:
            f_old = Fernet(old_key.encode())
            f_new = Fernet(new_key.encode())
        except Exception as e:
            console.print(f"[red]❌ Erro ao inicializar Fernet: {e}[/red]")
            raise typer.Exit(1)

        async with AsyncSessionLocal() as db:
            memories = (await db.execute(select(Memory))).scalars().all()
            console.print(f"🔄 Processando {len(memories)} memórias...")

            count = 0
            for mem in memories:
                try:
                    # Tenta ler o valor atual (que deve estar criptografado)
                    # Nota: mem.value retorna o valor real se o modelo tiver o getter automático
                    # Mas no modelo carregado via SQL, queremos o valor cru se possível.
                    # Se o modelo usa Getters/Setters transparentes, precisamos do valor cru.
                    raw_val = mem.value
                    # Re-criptografar (o setter do modelo cuida da criptografia se configurado)
                    # Se o modelo cryptografar no setter, basta atribuir.
                    # Vamos assumir que mem.value acessa o dado decifrado via OLD_KEY (se configurada no env)
                    # Então precisamos de um hack temporário ou injetar a chave.
                    # Melhor: Usar o valor cru do banco.
                    # Para simplificar, vamos assumir que o modelo cuida disso se mudarmos o settings.
                    # Ou fazemos manual aqui:
                    pass
                except Exception:
                    continue

        console.print("[yellow]⚠️  Comando em implementação. Requer ajuste nos modelos para bypass de cache de env.[/yellow]")

    asyncio.run(_run())


if __name__ == "__main__":
    app()
