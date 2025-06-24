# migrations/env.py

import os
import sys
from pathlib import Path
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

# Add root project directory to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent  # points to xiphi1/datamodel/xiphi/
sys.path.append(str(BASE_DIR))

# Import your SQLAlchemy Base metadata
from postgres.models import Base  # your models.py must define `Base = declarative_base()`

# Alembic Config object
config = context.config

# Load logging config
fileConfig(config.config_file_name)

# Set metadata for autogenerate support
target_metadata = Base.metadata

# Read database URL from env or fallback to ini
def get_database_url():
    return os.getenv("DATABASE_URL") or config.get_main_option("sqlalchemy.url")


def run_migrations_offline():
    url = get_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        url=get_database_url(),
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            transactional_ddl=False
        )
        context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
