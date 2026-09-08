"""Alembic 환경. 백엔드 모델(app.models)을 대상으로 비동기 엔진(asyncpg)으로 마이그레이션한다.

    cd backend
    alembic upgrade head                       # 적용
    alembic revision --autogenerate -m "..."   # 모델 변경 후 새 리비전
    alembic stamp head                         # create_all 로 만든 기존 DB 를 현재 리비전으로 표시

DB 주소는 DATABASE_URL 환경변수(또는 backend/.env)에서 읽는다. 운영에서는 `scripts/db_migrate.sh` 를 쓴다.
"""
from __future__ import annotations

import asyncio
from logging.config import fileConfig

from sqlalchemy.ext.asyncio import async_engine_from_config
from sqlalchemy.pool import NullPool

from alembic import context
from app import models  # noqa: F401  (테이블 등록)
from app.config import settings
from app.database import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)
config.set_main_option("sqlalchemy.url", settings.database_url.replace("%", "%%"))   # configparser 보간 이스케이프

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(url=settings.database_url, target_metadata=target_metadata, literal_binds=True, dialect_opts={"paramstyle": "named"},
                      compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


def _run(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = async_engine_from_config(config.get_section(config.config_ini_section, {}), prefix="sqlalchemy.", poolclass=NullPool)
    async with connectable.connect() as connection:
        await connection.run_sync(_run)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
