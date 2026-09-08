"""설정 상태 점검: 어떤 키·데이터가 들어왔고 무엇이 빠져 어떤 기능이 축소 동작 중인지.

관리자 대시보드의 "설정 상태" 카드와 `/health` 의 `features` 요약, `scripts/doctor.py` 가 같은 기준을 쓴다.
"""
from __future__ import annotations

from typing import Any

from ..config import Settings

GUIDE = "docs/SETUP_GUIDE.md"


def _item(key: str, label: str, level: str, status: str, detail: str, env: str = "", guide: str = "") -> dict[str, Any]:
    return {"key": key, "label": label, "level": level, "status": status, "detail": detail, "env": env, "guide": guide}


def setup_items(cfg: Settings, engine: dict[str, Any] | None = None, alert_webhook: bool | None = None) -> list[dict[str, Any]]:
    """level: required | recommended | optional, status: ok | degraded | missing."""
    items: list[dict[str, Any]] = []
    is_pg = cfg.database_url.startswith("postgresql")
    items.append(_item("database", "데이터베이스", "required", "ok" if is_pg else "degraded",
                       "PostgreSQL 사용" if is_pg else f"{cfg.database_url.split(':')[0]} 사용 (개발·테스트용, 운영에서는 PostgreSQL)", "DATABASE_URL", f"{GUIDE}#1-postgresql--postgis-필수"))

    eng = engine or {}
    graph = (eng.get("detail") or {}).get("graph") if isinstance(eng.get("detail"), dict) else None
    if eng.get("status") != "ok":
        items.append(_item("engine", "경로 엔진", "required", "missing", f"엔진 응답 없음 ({eng.get('status', 'unknown')}) — ENGINE_URL 과 엔진 프로세스를 확인", "ENGINE_URL"))
        items.append(_item("graph", "부산 그래프 데이터", "required", "missing", "엔진이 응답해야 확인할 수 있어요"))
    else:
        items.append(_item("engine", "경로 엔진", "required", "ok", f"연결됨 · 노드 {graph.get('nodes', '?') if graph else '?'} · 엣지 {graph.get('edges', '?') if graph else '?'}", "ENGINE_URL"))
        if graph and graph.get("sample"):
            items.append(_item("graph", "부산 그래프 데이터", "required", "degraded", "샘플 격자 도시로 동작 중 — OSM PBF 를 받아 파이프라인(run_all)을 돌리면 실제 부산 경로가 나와요",
                               "GRAPH_SOURCE", f"{GUIDE}#4-geofabrik-대한민국-osm-pbf-필수-보행망건물-원천"))
        else:
            src = (graph or {}).get("source", "")
            items.append(_item("graph", "부산 그래프 데이터", "required", "ok", f"{src} · {(graph or {}).get('resolved_from') or '실데이터'}", "GRAPH_SOURCE"))

    weak_jwt = cfg.jwt_secret_weak
    items.append(_item("jwt", "JWT 비밀키", "required", "missing" if weak_jwt else "ok",
                       "자리표시자이거나 32자 미만 — 관리자 기능이 꺼지고 공개 주소에서는 로그인이 막혀요. openssl rand -base64 48" if weak_jwt else "설정됨", "JWT_SECRET", f"{GUIDE}#2-jwt-비밀키-필수"))
    items.append(_item("admin", "관리자 비밀번호", "required", "ok" if cfg.admin_password else "missing",
                       "설정됨" if cfg.admin_password else "비어 있어 관리자 페이지가 꺼져 있어요", "ADMIN_PASSWORD", f"{GUIDE}#3-관리자-비밀번호-필수"))

    items.append(_item("places", "장소 검색 (Kakao)", "recommended", "ok" if cfg.kakao_rest_api_key else "degraded",
                       "Kakao 키워드 검색 사용" if cfg.kakao_rest_api_key else "역·정류장 이름만 검색되는 로컬 색인으로 동작 (건물·상호 검색 불가)",
                       "KAKAO_REST_API_KEY", f"{GUIDE}#6-kakao-developers-앱-장소-검색--카카오-로그인"))
    if cfg.weather_provider == "none":
        w = ("degraded", "날씨를 반영하지 않음 (WEATHER_PROVIDER=none)")
    elif cfg.weather_provider == "openweather" and not cfg.openweather_api_key:
        w = ("missing", "openweather 선택했지만 키가 없음 — 키를 넣거나 WEATHER_PROVIDER=open_meteo")
    else:
        w = ("ok", f"{cfg.weather_provider} 사용" + (" (키 불필요)" if cfg.weather_provider == "open_meteo" else ""))
    items.append(_item("weather", "실시간 날씨", "recommended", w[0], w[1], "WEATHER_PROVIDER"))
    kakao_login = bool(cfg.kakao_client_id)
    naver_login = bool(cfg.naver_client_id and cfg.naver_client_secret)
    items.append(_item("login_kakao", "카카오 로그인", "recommended", "ok" if kakao_login else "missing",
                       "설정됨" if kakao_login else "버튼이 보이지 않음 (개인화는 로그인 사용자만)", "KAKAO_CLIENT_ID", f"{GUIDE}#6-kakao-developers-앱-장소-검색--카카오-로그인"))
    items.append(_item("login_naver", "네이버 로그인", "recommended", "ok" if naver_login else "missing",
                       "설정됨" if naver_login else "버튼이 보이지 않음", "NAVER_CLIENT_ID", f"{GUIDE}#7-네이버-로그인"))
    https = cfg.public_base_url.startswith("https://")
    local = "localhost" in cfg.public_base_url or "127.0.0.1" in cfg.public_base_url
    items.append(_item("https", "HTTPS 공개 주소", "recommended", "ok" if https else ("degraded" if local else "missing"),
                       "HTTPS 사용" if https else ("로컬 개발 주소 — GPS 는 localhost 에서만, OAuth 는 이 주소로 등록" if local else "HTTP 공개 주소 — 브라우저가 GPS 를 막고 쿠키가 안전하지 않음"),
                       "PUBLIC_BASE_URL", f"{GUIDE}#10-https-도메인과-운영용-주소-운영-배포-시"))
    if cfg.allow_dev_login and not local:
        items.append(_item("dev_login", "데모 로그인", "recommended", "degraded", "공개 주소에서 데모 로그인이 켜져 있어요 — 운영에서는 ALLOW_DEV_LOGIN=false", "ALLOW_DEV_LOGIN"))
    if alert_webhook is not None:
        items.append(_item("alerts", "임계 초과 알림", "optional", "ok" if alert_webhook else "missing",
                           "웹훅 설정됨" if alert_webhook else "웹훅 없음 — /admin/alerts 에서 Slack 웹훅을 넣으면 켜져요", "ALERT_WEBHOOK_URL", "docs/ADMIN.md#알림-slack-수신-웹훅"))
    return items


def summarize(items: list[dict[str, Any]]) -> dict[str, Any]:
    req = [i for i in items if i["level"] == "required"]
    ready = all(i["status"] == "ok" for i in req)
    runnable = all(i["status"] != "missing" for i in req)
    return {
        "ready_for_production": ready,
        "runnable": runnable,
        "missing": [i["key"] for i in items if i["status"] == "missing"],
        "degraded": [i["key"] for i in items if i["status"] == "degraded"],
        "counts": {"ok": sum(i["status"] == "ok" for i in items), "degraded": sum(i["status"] == "degraded" for i in items), "missing": sum(i["status"] == "missing" for i in items)},
    }
