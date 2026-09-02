"""httpx 클라이언트 팩토리. 테스트는 `override_transport` 로 외부 호출을 가로챈다."""
from __future__ import annotations

import httpx

override_transport: httpx.AsyncBaseTransport | None = None


def client(timeout: float = 10.0) -> httpx.AsyncClient:
    if override_transport is not None:
        return httpx.AsyncClient(transport=override_transport, timeout=timeout)
    return httpx.AsyncClient(timeout=timeout)
