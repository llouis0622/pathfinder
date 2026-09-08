"""검색 결과 캐시. 같은 출발·도착(1e-5° ≈ 1 m 반올림)·프로필·그늘 선호·30분 시간대·날씨 조건이면 엔진을 다시 부르지 않는다.

TTL 이 지나거나 시설 오버라이드가 바뀌면(`clear`) 무효화된다. 개인화 재정렬은 캐시 뒤에서 사용자별로 적용된다.
"""
from __future__ import annotations

import time
from collections import OrderedDict
from datetime import datetime
from typing import Any

BUCKET_MIN = 30


def search_key(origin: tuple[float, float], destination: tuple[float, float], profile: str, prefer_shade: bool, departure_at: datetime,
               weather_flags: list[str], k: int, time_budget_s: float | None = None, seed: int | None = None) -> tuple:
    bucket = departure_at.replace(minute=(departure_at.minute // BUCKET_MIN) * BUCKET_MIN, second=0, microsecond=0)
    return (round(origin[0], 5), round(origin[1], 5), round(destination[0], 5), round(destination[1], 5), profile, bool(prefer_shade),
            bucket.isoformat(), tuple(sorted(weather_flags)), int(k), time_budget_s, seed)


class SearchCache:
    def __init__(self, ttl_s: float, maxsize: int) -> None:
        self.ttl_s = float(ttl_s)
        self.maxsize = int(maxsize)
        self._items: OrderedDict[tuple, tuple[float, dict[str, Any]]] = OrderedDict()
        self.hits = 0
        self.misses = 0

    @property
    def enabled(self) -> bool:
        return self.ttl_s > 0 and self.maxsize > 0

    def get(self, key: tuple, now: float | None = None) -> dict[str, Any] | None:
        if not self.enabled:
            return None
        now = now or time.monotonic()
        item = self._items.get(key)
        if item is None or item[0] < now:
            if item is not None:
                self._items.pop(key, None)
            self.misses += 1
            return None
        self._items.move_to_end(key)
        self.hits += 1
        return item[1]

    def put(self, key: tuple, value: dict[str, Any], now: float | None = None) -> None:
        if not self.enabled:
            return
        now = now or time.monotonic()
        self._items[key] = (now + self.ttl_s, value)
        self._items.move_to_end(key)
        while len(self._items) > self.maxsize:
            self._items.popitem(last=False)

    def clear(self) -> None:
        self._items.clear()

    def stats(self) -> dict[str, Any]:
        return {"enabled": self.enabled, "ttl_s": self.ttl_s, "maxsize": self.maxsize, "size": len(self._items), "hits": self.hits, "misses": self.misses}
