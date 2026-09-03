"""SQLAlchemy 2 비동기 세션. PostgreSQL(asyncpg) 운영, SQLite(aiosqlite) 테스트.

시작 시 `create_all` 로 없는 테이블을 만들고, 이미 있는 테이블에 모델에만 있는 열이 있으면
`ALTER TABLE ... ADD COLUMN` 으로 추가한다(가산적 자동 마이그레이션). 열 삭제·타입 변경은 다루지 않는다.
"""
from __future__ import annotations

import logging
from collections.abc import AsyncIterator

from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import StaticPool

log = logging.getLogger("backend.db")


class Base(DeclarativeBase):
    pass


def make_engine(url: str) -> AsyncEngine:
    if url.startswith("sqlite"):
        return create_async_engine(url, connect_args={"check_same_thread": False}, poolclass=StaticPool)
    return create_async_engine(url, pool_pre_ping=True)


def _add_missing_columns(sync_conn) -> list[str]:
    inspector = inspect(sync_conn)
    existing_tables = set(inspector.get_table_names())
    added: list[str] = []
    dialect = sync_conn.dialect
    for table in Base.metadata.sorted_tables:
        if table.name not in existing_tables:
            continue
        have = {c["name"] for c in inspector.get_columns(table.name)}
        for column in table.columns:
            if column.name in have:
                continue
            col_type = column.type.compile(dialect=dialect)
            nullable = "" if column.nullable else " NOT NULL"
            default = ""
            if column.default is not None and getattr(column.default, "is_scalar", False):
                value = column.default.arg
                if isinstance(value, bool):
                    default = f" DEFAULT {'TRUE' if value else 'FALSE'}" if dialect.name != "sqlite" else f" DEFAULT {int(value)}"
                elif isinstance(value, (int, float)):
                    default = f" DEFAULT {value}"
                elif isinstance(value, str):
                    default = f" DEFAULT '{value}'"
            if not column.nullable and not default:
                nullable = ""   # 기존 행이 있을 수 있으므로 NULL 허용으로 추가
            q = lambda name: dialect.identifier_preparer.quote(name)  # noqa: E731
            sync_conn.execute(text(f"ALTER TABLE {q(table.name)} ADD COLUMN {q(column.name)} {col_type}{nullable}{default}"))
            added.append(f"{table.name}.{column.name}")
    return added


class Database:
    def __init__(self, url: str) -> None:
        self.engine = make_engine(url)
        self.session_factory = async_sessionmaker(self.engine, expire_on_commit=False, class_=AsyncSession)

    async def create_all(self) -> None:
        from . import models  # noqa: F401  (테이블 등록)

        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            added = await conn.run_sync(_add_missing_columns)
            if added:
                log.info("누락 열 추가: %s", ", ".join(added))

    async def dispose(self) -> None:
        await self.engine.dispose()

    async def session(self) -> AsyncIterator[AsyncSession]:
        async with self.session_factory() as s:
            yield s
