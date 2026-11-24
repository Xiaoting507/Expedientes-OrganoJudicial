"""Sprint 7: aplica las migraciones de Alembic al arrancar en producción (reemplaza create_all)."""
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]


def actualizar_esquema() -> None:
    from alembic import command
    from alembic.config import Config

    cfg = Config(str(RAIZ / "alembic.ini"))
    cfg.attributes["configurar_logs"] = False
    command.upgrade(cfg, "head")
