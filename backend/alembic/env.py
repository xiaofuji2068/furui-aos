"""Alembic 迁移环境 — 指向 furui-aios 全部 ORM 模型（步骤 2.0）。

- target_metadata = app.db.Base.metadata（覆盖 models.py / models_ai.py / models_ontology.py）
- 支持环境变量 DATABASE_URL 覆盖：SQLite 开发默认；生产切 PG 无需改本文件
"""
from logging.config import fileConfig
import os
import sys
from pathlib import Path

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# 让 alembic 能找到 backend 包（backend/ 目录）
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# 环境变量优先：DATABASE_URL（PG 切库时用）
if os.getenv("DATABASE_URL"):
    config.set_main_option("sqlalchemy.url", os.getenv("DATABASE_URL"))

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 注册全部 ORM 模型到 Base.metadata
from app.db import Base  # noqa: E402
import app.models  # noqa: E402,F401  组织/用户/角色/权限
import app.models_ai  # noqa: E402,F401 知识/审批/会话等
import app.models_ontology  # noqa: E402,F401 本体对象/链接/版本
import app.models_release  # noqa: E402,F401 交付 Release/Change/边缘站点（TASK-017）

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
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
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
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
