"""관측성: 요청 ID, Prometheus 지표, JSON 로그.

- 모든 요청에 `X-Request-ID` 를 붙인다(클라이언트가 보내면 그대로, 없으면 생성). 엔진 호출에도 같은 값을 전달해
  프론트 → 백엔드 → 엔진 로그를 한 ID 로 잇는다. 접근 로그(`api_access_logs.request_id`)에도 남는다.
- `/metrics`: http 요청 수·지연, 경로 검색 수·엔진 지연, 캐시 적중, 엔진 상태.
- `LOG_FORMAT=json` 이면 로그 한 줄이 JSON 이고 request_id 가 들어간다.
"""
from __future__ import annotations

import contextvars
import json
import logging
import time
import uuid
from typing import Any

from fastapi import FastAPI, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="")

REQUEST_ID_HEADER = "X-Request-ID"

HTTP_REQUESTS = Counter("pathfinder_http_requests_total", "HTTP 요청 수", ["method", "route", "status"])
HTTP_LATENCY = Histogram("pathfinder_http_request_seconds", "HTTP 처리 시간(초)", ["method", "route"],
                         buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10))
ROUTE_SEARCHES = Counter("pathfinder_route_searches_total", "경로 검색 수", ["profile", "status", "cached"])
ENGINE_LATENCY = Histogram("pathfinder_engine_search_seconds", "엔진 탐색 왕복 시간(초)", buckets=(0.1, 0.25, 0.5, 1, 2, 3, 5, 10, 30))
ROUTE_CHOICES = Counter("pathfinder_route_choices_total", "경로 선택 수", ["shown_rank", "learned"])
SEARCH_CACHE = Counter("pathfinder_search_cache_total", "검색 캐시", ["result"])
ENGINE_UP = Gauge("pathfinder_engine_up", "마지막 헬스체크에서 엔진이 살아 있으면 1")
ALERTS_SENT = Counter("pathfinder_alerts_sent_total", "보낸 알림 수", ["rule"])


def current_request_id() -> str:
    return request_id_var.get()


def route_template(request: Request) -> str:
    route = request.scope.get("route")
    path = getattr(route, "path", None)
    if path:
        return path
    return "unmatched"


def install(app: FastAPI, metrics_enabled: bool = True) -> None:
    @app.middleware("http")
    async def request_id_and_metrics(request: Request, call_next: Any) -> Response:
        rid = (request.headers.get(REQUEST_ID_HEADER) or "").strip()[:64] or uuid.uuid4().hex
        token = request_id_var.set(rid)
        request.state.request_id = rid
        started = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            response.headers[REQUEST_ID_HEADER] = rid
            return response
        finally:
            if metrics_enabled and request.url.path != "/metrics":
                route = route_template(request)
                HTTP_REQUESTS.labels(request.method, route, str(status)).inc()
                HTTP_LATENCY.labels(request.method, route).observe(time.perf_counter() - started)
            request_id_var.reset(token)

    if metrics_enabled:
        @app.get("/metrics", include_in_schema=False)
        async def metrics() -> Response:
            return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


# ---------------------------------------------------------------- JSON 로그
class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"), "level": record.levelname, "logger": record.name,
            "msg": record.getMessage(),
        }
        rid = request_id_var.get()
        if rid:
            payload["request_id"] = rid
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get() or "-"
        return True


def configure_logging(level: str, fmt: str) -> None:
    root = logging.getLogger()
    root.setLevel(level.upper())
    for h in list(root.handlers):
        root.removeHandler(h)
    handler = logging.StreamHandler()
    if fmt.lower() == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.addFilter(RequestIdFilter())
        handler.setFormatter(logging.Formatter("%(levelname)s [%(request_id)s] %(name)s: %(message)s"))
    root.addHandler(handler)
