"""요청 한도와 엔진 동시성 보호.

- `RateLimiter`: IP 당 분당 검색 수(슬라이딩 창). 넘으면 429.
- `EngineGate`: 백엔드에서 엔진으로 동시에 보내는 탐색 수. 넘치면 잠깐 기다렸다가 503.
- 값은 환경변수 기본값 → `admin_settings.limits` 저장값(관리자 화면) 순으로 정해지고, 바꾸면 즉시 적용된다.
"""
from __future__ import annotations

import asyncio
import time
from collections import defaultdict, deque
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from ..config import Settings
from ..models import AdminSetting

SETTINGS_KEY = "limits"
MAX_TRACKED_IPS = 5000


class RateLimiter:
    def __init__(self, per_minute: int) -> None:
        self.per_minute = int(per_minute)
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self.rejected = 0

    @property
    def enabled(self) -> bool:
        return self.per_minute > 0

    def allow(self, ip: str, now: float | None = None) -> bool:
        if not self.enabled:
            return True
        now = now or time.monotonic()
        if len(self._hits) > MAX_TRACKED_IPS:
            for k in [k for k, dq in self._hits.items() if not dq or now - dq[-1] > 60]:
                self._hits.pop(k, None)
        q = self._hits[ip]
        while q and now - q[0] > 60:
            q.popleft()
        if len(q) >= self.per_minute:
            self.rejected += 1
            return False
        q.append(now)
        return True

    def retry_after(self, ip: str, now: float | None = None) -> int:
        now = now or time.monotonic()
        q = self._hits.get(ip)
        return max(1, int(60 - (now - q[0]))) if q else 60


class EngineGate:
    def __init__(self, concurrency: int, timeout_s: float) -> None:
        self.concurrency = max(1, int(concurrency))
        self.timeout_s = float(timeout_s)
        self._sem = asyncio.Semaphore(self.concurrency)
        self.inflight = 0
        self.rejected = 0

    async def acquire(self) -> bool:
        try:
            await asyncio.wait_for(self._sem.acquire(), timeout=self.timeout_s)
        except asyncio.TimeoutError:
            self.rejected += 1
            return False
        self.inflight += 1
        return True

    def release(self) -> None:
        self.inflight = max(0, self.inflight - 1)
        self._sem.release()


def defaults(cfg: Settings) -> dict[str, Any]:
    return {"route_per_minute": int(cfg.route_rate_limit_per_minute), "engine_concurrency": int(cfg.engine_concurrency),
            "engine_queue_timeout_s": float(cfg.engine_queue_timeout_s)}


async def load_limits(db: AsyncSession, cfg: Settings) -> dict[str, Any]:
    row = await db.get(AdminSetting, SETTINGS_KEY)
    return {**defaults(cfg), **((row.value if row else {}) or {})}


async def save_limits(db: AsyncSession, cfg: Settings, patch: dict[str, Any]) -> dict[str, Any]:
    row = await db.get(AdminSetting, SETTINGS_KEY)
    merged = {**defaults(cfg), **((row.value if row else {}) or {}), **patch}
    merged["route_per_minute"] = int(max(0, min(10000, merged["route_per_minute"])))
    merged["engine_concurrency"] = int(max(1, min(64, merged["engine_concurrency"])))
    merged["engine_queue_timeout_s"] = float(max(0.5, min(60.0, merged["engine_queue_timeout_s"])))
    if row is None:
        db.add(AdminSetting(key=SETTINGS_KEY, value=merged))
    else:
        row.value = merged
    await db.commit()
    return merged


def apply(app: Any, limits: dict[str, Any]) -> None:
    """앱 상태의 리미터·게이트를 새 값으로 바꾼다 (진행 중인 요청은 옛 게이트를 끝까지 쓴다)."""
    old = getattr(app.state, "rate_limiter", None)
    limiter = RateLimiter(limits["route_per_minute"])
    if old is not None:
        limiter.rejected = old.rejected
    app.state.rate_limiter = limiter
    old_gate = getattr(app.state, "engine_gate", None)
    gate = EngineGate(limits["engine_concurrency"], limits["engine_queue_timeout_s"])
    if old_gate is not None:
        gate.rejected = old_gate.rejected
    app.state.engine_gate = gate
    app.state.limits = dict(limits)


def stats(app: Any) -> dict[str, Any]:
    limiter: RateLimiter | None = getattr(app.state, "rate_limiter", None)
    gate: EngineGate | None = getattr(app.state, "engine_gate", None)
    return {"route_rejected": (limiter.rejected if limiter else 0), "engine_inflight": (gate.inflight if gate else 0),
            "engine_rejected": (gate.rejected if gate else 0)}
