"""Entorno de Alembic: usa el mismo DATABASE_URL y los mismos modelos que la app."""
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app import models  # noqa: F401  (registra las tablas en Base.metadata)
from app.config import DATABASE_URL
from app.db import Base

config = context.config
if config.config_file_name is not None and config.attributes.get("configurar_logs", True):
    fileConfig(config.config_file_name)
config.set_main_option("sqlalchemy.url", DATABASE_URL.replace("%", "%%"))
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(url=config.get_main_option("sqlalchemy.url"), target_metadata=target_metadata,
                      literal_binds=True, render_as_batch=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    conectable = engine_from_config(config.get_section(config.config_ini_section, {}), prefix="sqlalchemy.",
                                    poolclass=pool.NullPool)
    with conectable.connect() as conexion:
        if conexion.dialect.name == "postgresql":
            # Dos réplicas arrancan a la vez: solo una aplica las migraciones, la otra espera
            from sqlalchemy import text

            conexion.execute(text("SELECT pg_advisory_lock(7420261)"))
            conexion.commit()
        context.configure(connection=conexion, target_metadata=target_metadata, render_as_batch=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
