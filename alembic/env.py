from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

from atalaia.config import DATABASE_URL
from atalaia.db.base import Base
import atalaia.db.models  # noqa: F401 — garante que todos os models sejam importados

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Aponta para a metadata da Base declarativa para suporte a autogenerate
target_metadata = Base.metadata

# Injeta a URL de conexão de config.py, sem duplicar a lógica
config.set_main_option("sqlalchemy.url", DATABASE_URL)


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
