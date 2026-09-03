"""엔진 HTTP 클라이언트."""
from __future__ import annotations

from typing import Any

import httpx

from .. import http
from ..config import Settings


class EngineError(Exception):
    def __init__(self, status: int, detail: str) -> None:
        super().__init__(detail)
        self.status = status
        self.detail = detail


async def search(cfg: Settings, payload: dict[str, Any]) -> dict[str, Any]:
    try:
        async with http.client(timeout=cfg.engine_timeout_s) as client:
            r = await client.post(f"{cfg.engine_url}/api/search", json=payload)
    except httpx.HTTPError as exc:
        raise EngineError(503, f"엔진에 연결할 수 없습니다 ({type(exc).__name__})") from exc
    if r.status_code != 200:
        try:
            detail = r.json().get("detail", r.text)
        except ValueError:
            detail = r.text
        raise EngineError(r.status_code, str(detail))
    return r.json()


async def profiles(cfg: Settings) -> list[dict[str, Any]]:
    async with http.client(timeout=5.0) as client:
        r = await client.get(f"{cfg.engine_url}/api/profiles")
        r.raise_for_status()
        return r.json()


async def health(cfg: Settings) -> dict[str, Any]:
    try:
        async with http.client(timeout=3.0) as client:
            r = await client.get(f"{cfg.engine_url}/health")
            return {"status": "ok" if r.status_code == 200 else "degraded", "detail": r.json() if r.status_code == 200 else r.text}
    except httpx.HTTPError as exc:
        return {"status": "down", "detail": type(exc).__name__}


MVT_MEDIA_TYPE = "application/vnd.mapbox-vector-tile"


async def tile(cfg: Settings, z: int, x: int, y: int) -> tuple[int, bytes]:
    """그래프 벡터 타일을 그대로 전달한다 (204 = 빈 타일)."""
    try:
        async with http.client(timeout=15.0) as client:
            r = await client.get(f"{cfg.engine_url}/api/tiles/{z}/{x}/{y}.mvt")
    except httpx.HTTPError as exc:
        raise EngineError(503, f"엔진에 연결할 수 없습니다 ({type(exc).__name__})") from exc
    return r.status_code, r.content


async def tiles_meta(cfg: Settings) -> dict[str, Any]:
    async with http.client(timeout=5.0) as client:
        r = await client.get(f"{cfg.engine_url}/api/tiles/meta")
        r.raise_for_status()
        return r.json()


async def shade(cfg: Settings, params: dict[str, Any]) -> dict[str, Any]:
    try:
        async with http.client(timeout=cfg.engine_timeout_s) as client:
            r = await client.get(f"{cfg.engine_url}/api/shade", params=params)
    except httpx.HTTPError as exc:
        raise EngineError(503, f"엔진에 연결할 수 없습니다 ({type(exc).__name__})") from exc
    if r.status_code != 200:
        try:
            detail = r.json().get("detail", r.text)
        except ValueError:
            detail = r.text
        raise EngineError(r.status_code, str(detail))
    return r.json()
