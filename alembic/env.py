from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlalchemy.dialects import postgresql

from app.core.config import settings
from app.db.base import Base

# Importar TODOS los modelos para que Alembic los detecte en autogenerate.
from app.models import catalog  # noqa: F401
from app.models import customers  # noqa: F401
from app.models import geography  # noqa: F401
from app.models import inventory  # noqa: F401
from app.models import sales  # noqa: F401
from app.models import simulation  # noqa: F401
from app.models import suppliers  # noqa: F401

# Objeto de configuración de Alembic.
config = context.config

# Inyectar la URL real desde settings.
config.set_main_option("sqlalchemy.url", settings.database_url)

# Configurar logging desde alembic.ini.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Metadata para autogenerate.
target_metadata = Base.metadata


def include_object(object, name, type_, reflected, compare_to):
    """Filtra objetos que Alembic NO debe gestionar.

    - Ignora tipos ENUM en autogenerate. Los enums se crean manualmente
      en la migración inicial y se reutilizan con create_type=False.
      Esto evita el error 'type already exists'.
    """
    if type_ == "type" and isinstance(object, postgresql.ENUM):
        return False
    return True


def run_migrations_offline() -> None:
    """Ejecuta migraciones en modo 'offline' (sin conexión real a la DB)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
        include_object=include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Ejecuta migraciones en modo 'online' (con conexión real a la DB)."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
            include_object=include_object,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()