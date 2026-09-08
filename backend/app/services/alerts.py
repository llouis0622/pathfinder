"""임계 초과 알림: 주기적으로 지표를 평가해 Slack 수신 웹훅(또는 JSON 웹훅)으로 보낸다.

- 규칙: 엔진 다운, 오류율, 경로 없음 비율, 엔진 p95 응답, 서버 5xx 수, 미처리 제보 수.
- 설정은 `admin_settings.alerts` 에 저장되고(관리자 화면), 없으면 환경변수 기본값을 쓴다.
- 같은 규칙은 `cooldown_min` 동안 다시 보내지 않고, 정상으로 돌아오면 복구 알림을 한 번 보낸다.
"""
from __future__ import annotations

import asyncio
import copy
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from fastapi import FastAPI
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .. import http
from ..config import Settings
from ..models import AdminSetting, AlertEvent, ApiAccessLog, EngineRun, Report, RouteRequest
from ..observability import ALERTS_SENT
from . import engine_client

log = logging.getLogger("backend.alerts")

SETTINGS_KEY = "alerts"
INITIAL_DELAY_S = 90
RULE_LABELS = {
    "engine_down": "엔진 응답 없음",
    "error_rate": "검색 오류율",
    "no_route_rate": "경로 없음 비율",
    "engine_p95_ms": "엔진 p95 응답",
    "access_5xx": "서버 오류(5xx)",
    "open_reports": "미처리 제보",
}
DEFAULTS: dict[str, Any] = {
    "enabled": True,
    "webhook_url": "",
    "format": "slack",            # slack | json
    "interval_min": 5,
    "window_min": 30,
    "cooldown_min": 60,
    "rules": {
        "engine_down": {"enabled": True},
        "error_rate": {"enabled": True, "threshold": 10.0, "min_samples": 10},       # %
        "no_route_rate": {"enabled": True, "threshold": 40.0, "min_samples": 10},    # %
        "engine_p95_ms": {"enabled": True, "threshold": 3000.0, "min_samples": 5},   # ms
        "access_5xx": {"enabled": True, "threshold": 5},                              # 건 (창 안)
        "open_reports": {"enabled": True, "threshold": 10},                           # 건
    },
}


@dataclass
class Finding:
    rule: str
    value: float | None
    threshold: float | None
    message: str


# ---------------------------------------------------------------- 설정
def _merge(base: dict, patch: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in patch.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        elif k in out or k == "rules":
            out[k] = v
    return out


def env_defaults(cfg: Settings) -> dict:
    d = copy.deepcopy(DEFAULTS)
    d["webhook_url"] = cfg.alert_webhook_url
    d["enabled"] = bool(cfg.alert_enabled)
    d["interval_min"] = int(cfg.alert_interval_min)
    return d


async def load_settings(db: AsyncSession, cfg: Settings) -> dict:
    row = await db.get(AdminSetting, SETTINGS_KEY)
    base = env_defaults(cfg)
    return _merge(base, row.value or {}) if row else base


async def save_settings(db: AsyncSession, cfg: Settings, patch: dict) -> dict:
    row = await db.get(AdminSetting, SETTINGS_KEY)
    current = _merge(env_defaults(cfg), (row.value if row else {}) or {})
    merged = _merge(current, patch)
    merged["interval_min"] = int(max(1, min(1440, merged["interval_min"])))
    merged["window_min"] = int(max(5, min(1440, merged["window_min"])))
    merged["cooldown_min"] = int(max(0, min(10080, merged["cooldown_min"])))
    if merged["format"] not in ("slack", "json"):
        merged["format"] = "slack"
    if row is None:
        db.add(AdminSetting(key=SETTINGS_KEY, value=merged))
    else:
        row.value = merged
    await db.commit()
    return merged


def public_settings(s: dict) -> dict:
    """웹훅 URL 에는 토큰이 들어 있으므로 응답에서 빼고 앞부분만 보여 준다."""
    url = s.get("webhook_url") or ""
    masked = url if len(url) <= 28 else url[:28] + "…"
    return {**{k: v for k, v in s.items() if k != "webhook_url"}, "webhook_url_masked": masked, "webhook_configured": bool(url), "rule_labels": RULE_LABELS}


# ---------------------------------------------------------------- 평가
def _p95(values: list[float]) -> float | None:
    if not values:
        return None
    xs = sorted(values)
    return float(xs[min(len(xs) - 1, int(round(0.95 * (len(xs) - 1))))])


async def evaluate(db: AsyncSession, cfg: Settings, s: dict, now: datetime | None = None) -> list[Finding]:
    now = now or datetime.now(timezone.utc)
    since = now - timedelta(minutes=int(s.get("window_min", 30)))
    rules = s.get("rules", {})
    found: list[Finding] = []

    def on(rule: str) -> bool:
        return bool(rules.get(rule, {}).get("enabled", True))

    if on("engine_down"):
        health = await engine_client.health(cfg)
        if health.get("status") != "ok":
            found.append(Finding("engine_down", None, None, f"엔진 헬스체크 실패 ({health.get('status')}: {str(health.get('detail'))[:120]})"))

    if on("error_rate") or on("no_route_rate"):
        rows = (await db.execute(select(RouteRequest.status, func.count(RouteRequest.id)).where(RouteRequest.created_at >= since)
                                 .group_by(RouteRequest.status))).all()
        counts = {str(st): int(n) for st, n in rows}
        total = sum(counts.values())
        for rule, status in (("error_rate", "error"), ("no_route_rate", "no_route")):
            r = rules.get(rule, {})
            if on(rule) and total >= int(r.get("min_samples", 10)):
                pct = 100.0 * counts.get(status, 0) / total
                if pct > float(r.get("threshold", 100)):
                    found.append(Finding(rule, round(pct, 1), float(r["threshold"]), f"{RULE_LABELS[rule]} {pct:.1f}% (창 {s['window_min']}분, {total}건 중 {counts.get(status, 0)}건)"))

    if on("engine_p95_ms"):
        r = rules["engine_p95_ms"]
        vals = [float(v) for (v,) in (await db.execute(select(EngineRun.engine_elapsed_ms).where(EngineRun.created_at >= since, EngineRun.engine_elapsed_ms.is_not(None)))).all()]
        p95 = _p95(vals)
        if p95 is not None and len(vals) >= int(r.get("min_samples", 5)) and p95 > float(r.get("threshold", 3000)):
            found.append(Finding("engine_p95_ms", round(p95), float(r["threshold"]), f"엔진 p95 {p95:.0f}ms (창 {s['window_min']}분, {len(vals)}건)"))

    if on("access_5xx"):
        r = rules["access_5xx"]
        n = int((await db.execute(select(func.count(ApiAccessLog.id)).where(ApiAccessLog.created_at >= since, ApiAccessLog.status >= 500))).scalar_one() or 0)
        if n >= int(r.get("threshold", 5)):
            found.append(Finding("access_5xx", n, float(r["threshold"]), f"서버 오류 {n}건 (창 {s['window_min']}분)"))

    if on("open_reports"):
        r = rules["open_reports"]
        n = int((await db.execute(select(func.count(Report.id)).where(Report.status == "open"))).scalar_one() or 0)
        if n >= int(r.get("threshold", 10)):
            found.append(Finding("open_reports", n, float(r["threshold"]), f"검토 대기 제보 {n}건"))
    return found


# ---------------------------------------------------------------- 전송
def payload(fmt: str, events: list[dict], service: str = "Pathfinder") -> dict:
    if fmt == "json":
        return {"service": service, "events": events}
    lines = []
    for e in events:
        icon = {"warn": ":rotating_light:", "ok": ":white_check_mark:", "test": ":bell:"}.get(e["level"], ":bell:")
        lines.append(f"{icon} *{RULE_LABELS.get(e['rule'], e['rule'])}* — {e['message']}")
    return {"text": f"*{service} 알림*\n" + "\n".join(lines)}


async def send_webhook(url: str, fmt: str, events: list[dict]) -> tuple[bool, int | None, str]:
    if not url:
        return False, None, "웹훅 URL 이 없습니다"
    try:
        async with http.client(timeout=8.0) as client:
            r = await client.post(url, json=payload(fmt, events))
            return (200 <= r.status_code < 300), r.status_code, ("" if r.status_code < 300 else r.text[:200])
    except httpx.HTTPError as exc:
        return False, None, type(exc).__name__


class AlertState:
    """규칙별 마지막 전송 시각과 현재 활성 여부 (프로세스 메모리)."""

    def __init__(self) -> None:
        self.last_sent: dict[str, datetime] = {}
        self.active: set[str] = set()


async def notify(db: AsyncSession, s: dict, findings: list[Finding], state: AlertState, now: datetime | None = None) -> list[AlertEvent]:
    """쿨다운을 지켜 경고를 보내고, 사라진 규칙에는 복구 알림을 보낸다. 보낸 이벤트(전송 실패 포함)를 돌려준다."""
    now = now or datetime.now(timezone.utc)
    cooldown = timedelta(minutes=int(s.get("cooldown_min", 60)))
    to_send: list[AlertEvent] = []
    current = {f.rule for f in findings}
    for f in findings:
        last = state.last_sent.get(f.rule)
        if last is not None and now - last < cooldown:
            continue
        to_send.append(AlertEvent(rule=f.rule, level="warn", message=f.message, value=f.value, threshold=f.threshold))
    for rule in sorted(state.active - current):
        to_send.append(AlertEvent(rule=rule, level="ok", message=f"{RULE_LABELS.get(rule, rule)} 정상으로 돌아왔어요"))
    state.active = current
    if not to_send:
        return []
    ok, status, err = await send_webhook(s.get("webhook_url", ""), s.get("format", "slack"),
                                         [{"rule": e.rule, "level": e.level, "message": e.message, "value": e.value, "threshold": e.threshold} for e in to_send])
    for e in to_send:
        e.sent, e.http_status, e.error = ok, status, err
        e.created_at = now
        if ok:
            ALERTS_SENT.labels(e.rule).inc()
            if e.level == "warn":
                state.last_sent[e.rule] = now
        db.add(e)
    await db.commit()
    for e in to_send:
        await db.refresh(e)
    return to_send


async def run_once(app: FastAPI, db: AsyncSession) -> dict:
    cfg: Settings = app.state.settings
    s = await load_settings(db, cfg)
    findings = await evaluate(db, cfg, s)
    events: list[AlertEvent] = []
    if s.get("enabled") and s.get("webhook_url"):
        events = await notify(db, s, findings, app.state.alert_state)
    return {"findings": [f.__dict__ for f in findings], "sent": [event_out(e) for e in events],
            "enabled": bool(s.get("enabled")), "webhook_configured": bool(s.get("webhook_url"))}


def event_out(e: AlertEvent) -> dict:
    created = e.created_at.replace(tzinfo=timezone.utc) if e.created_at and e.created_at.tzinfo is None else e.created_at
    return {"id": str(e.id), "created_at": (created.isoformat() if created else None), "rule": e.rule, "rule_label": RULE_LABELS.get(e.rule, e.rule),
            "level": e.level, "message": e.message, "value": e.value, "threshold": e.threshold, "sent": e.sent, "http_status": e.http_status, "error": e.error}


async def alerts_loop(app: FastAPI) -> None:
    await asyncio.sleep(INITIAL_DELAY_S)
    while True:
        interval = 300
        try:
            async for db in app.state.db.session():
                s = await load_settings(db, app.state.settings)
                interval = max(60, int(s.get("interval_min", 5)) * 60)
                if s.get("enabled") and s.get("webhook_url"):
                    result = await run_once(app, db)
                    if result["sent"]:
                        log.info("알림 전송: %s", [e["rule"] for e in result["sent"]])
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            log.exception("알림 평가 실패")
        await asyncio.sleep(interval)


def start_alerts(app: FastAPI) -> asyncio.Task:
    """루프는 항상 돌고, 켜짐 여부는 매 주기 설정(DB 값 우선, 없으면 ALERT_ENABLED)으로 판단한다. 관리자 화면에서 켜면 바로 반영된다."""
    app.state.alert_state = AlertState()
    return asyncio.create_task(alerts_loop(app))
