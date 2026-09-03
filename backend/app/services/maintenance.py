"""로그 보존 기간 정리. 접근 로그·장소 검색·엔진 성능 로그는 분석용 원본(route_requests 등)이 아니므로 N일 뒤 지운다.

- `LOG_RETENTION_DAYS` (0 이면 끔): 시작 직후 한 번, 이후 하루에 한 번 `prune_logs` 를 돈다.
- 관리자 API `POST /api/admin/maintenance/prune` 로 즉시 실행할 수도 있다.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import ApiAccessLog, EngineRun, PlaceSearch

log = logging.getLogger("backend.maintenance")

PRUNE_MODELS = (ApiAccessLog, PlaceSearch, EngineRun)
DAY_S = 86400
INITIAL_DELAY_S = 60      # 시작 직후 요청 처리와 겹치지 않도록 잠시 뒤에 첫 정리


async def prune_logs(db: AsyncSession, days: int, now: datetime | None = None) -> dict[str, int]:
    """`days` 일보다 오래된 행을 지운다. days=0 이면 전부. 표별 삭제 수를 돌려준다."""
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=max(0, days))
    deleted: dict[str, int] = {}
    for model in PRUNE_MODELS:
        res = await db.execute(delete(model).where(model.created_at < cutoff))
        deleted[model.__tablename__] = int(res.rowcount or 0)
    await db.commit()
    return deleted


async def log_counts(db: AsyncSession) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for model in PRUNE_MODELS:
        total = int((await db.execute(select(func.count()).select_from(model))).scalar_one() or 0)
        oldest = (await db.execute(select(func.min(model.created_at)))).scalar_one()
        if oldest is not None and oldest.tzinfo is None:
            oldest = oldest.replace(tzinfo=timezone.utc)
        out[model.__tablename__] = {"rows": total, "oldest": (oldest.isoformat() if oldest else None)}
    return out


async def retention_loop(app: FastAPI) -> None:
    """앱 수명 동안 하루 한 번 정리한다. 실패해도 다음 주기에 다시 시도한다."""
    days = int(app.state.settings.log_retention_days)
    await asyncio.sleep(INITIAL_DELAY_S)
    while True:
        try:
            async for db in app.state.db.session():
                deleted = await prune_logs(db, days)
                if any(deleted.values()):
                    log.info("로그 정리 (%d일 초과): %s", days, deleted)
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            log.exception("로그 정리 실패")
        await asyncio.sleep(DAY_S)


def start_retention(app: FastAPI) -> asyncio.Task | None:
    if int(app.state.settings.log_retention_days) <= 0:
        return None
    return asyncio.create_task(retention_loop(app))
