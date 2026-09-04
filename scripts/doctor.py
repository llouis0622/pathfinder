#!/usr/bin/env python3
"""설정 진단: 루트 .env(와 서비스별 .env)를 읽어 무엇이 들어왔고 무엇이 빠져 어떤 기능이 축소 동작할지 표로 보여 준다.

    python scripts/doctor.py            # 현재 폴더의 .env 기준
    python scripts/doctor.py --env prod.env
    python scripts/doctor.py --json     # 기계가 읽기 좋은 출력

외부 패키지 없이 동작한다. DB 접속은 psycopg 가 설치돼 있을 때만 실제로 붙어 본다.
종료 코드: 필수 항목이 '없음' 이면 1, 아니면 0.
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_JWT = "change-me-in-production"


def read_env(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        v = v.strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
            v = v[1:-1]
        out[k.strip()] = v
    return out


def merged_env(root_env: Path) -> dict[str, str]:
    env = read_env(root_env)
    for sub in ("backend", "engine", "frontend"):
        env.update(read_env(ROOT / sub / ".env"))     # 서비스별 .env 가 있으면 우선
    env.update({k: v for k, v in os.environ.items() if k in env or k.startswith(("VITE_", "POSTGRES_", "KAKAO_", "NAVER_", "JWT_", "ADMIN_", "DATABASE_", "ENGINE_", "GRAPH_", "ALERT_", "BUS_", "VWORLD_", "PUBLIC_", "FRONTEND_", "WEATHER_", "OPENWEATHER_"))})
    return env


def tcp_open(host: str, port: int, timeout: float = 2.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def check_db(url: str) -> tuple[str, str]:
    if not url:
        return "missing", "DATABASE_URL 없음"
    if url.startswith("sqlite"):
        return "degraded", "SQLite (개발·테스트용)"
    u = urlparse(url.replace("postgresql+asyncpg://", "postgresql://").replace("postgresql+psycopg://", "postgresql://"))
    host, port = u.hostname or "localhost", u.port or 5432
    if host in ("db",) and not tcp_open(host, port):
        return "degraded", f"호스트 '{host}' 는 Docker Compose 안에서만 풀린다 (컨테이너 밖에서는 localhost 로 바꿔 확인)"
    if not tcp_open(host, port):
        return "missing", f"{host}:{port} 에 연결되지 않음 — PostgreSQL 이 떠 있는지 확인"
    try:
        import psycopg  # type: ignore

        with psycopg.connect(u._replace(scheme="postgresql").geturl(), connect_timeout=3) as conn:
            has_postgis = conn.execute("SELECT count(*) FROM pg_extension WHERE extname='postgis'").fetchone()[0] > 0
            try:
                nodes = conn.execute("SELECT value FROM graph_meta WHERE key='node_count'").fetchone()
                graph = f", 그래프 노드 {int(nodes[0]):,}개" if nodes else ", 그래프 미적재"
            except Exception:  # noqa: BLE001
                conn.rollback()
                graph = ", 그래프 테이블 없음"
            return ("ok" if has_postgis else "degraded"), ("PostGIS 확인" if has_postgis else "PostGIS 확장 없음 (CREATE EXTENSION postgis)") + graph
    except ImportError:
        return "ok", f"{host}:{port} 응답 (psycopg 미설치로 PostGIS·그래프는 확인 안 함)"
    except Exception as exc:  # noqa: BLE001
        return "missing", f"접속 실패: {type(exc).__name__}"


def run(env: dict[str, str]) -> list[dict]:
    g = env.get
    items: list[dict] = []

    def add(key, label, level, status, detail, var=""):
        items.append({"key": key, "label": label, "level": level, "status": status, "detail": detail, "env": var})

    st, detail = check_db(g("DATABASE_URL", ""))
    add("database", "PostgreSQL + PostGIS", "required", st, detail, "DATABASE_URL")
    jwt = g("JWT_SECRET", "")
    add("jwt", "JWT 비밀키", "required", "missing" if (not jwt or jwt == DEFAULT_JWT or len(jwt) < 32) else "ok",
        "비어 있거나 기본값/32자 미만 → openssl rand -base64 48" if (not jwt or jwt == DEFAULT_JWT or len(jwt) < 32) else "설정됨", "JWT_SECRET")
    add("admin", "관리자 비밀번호", "required", "ok" if g("ADMIN_PASSWORD") else "missing", "설정됨" if g("ADMIN_PASSWORD") else "비어 있으면 /admin 이 꺼진다", "ADMIN_PASSWORD")
    pbf = next(iter((ROOT / "data" / "raw").glob("*.osm.pbf")), None) if (ROOT / "data" / "raw").is_dir() else None
    bundle = ROOT / "data" / "build" / "graph_bundle.npz"
    if bundle.is_file():
        add("graph", "부산 그래프 데이터", "required", "ok", f"빌드 산출물 있음 ({bundle.relative_to(ROOT)}) — GRAPH_SOURCE=auto 면 자동 사용", "GRAPH_SOURCE")
    elif pbf:
        add("graph", "부산 그래프 데이터", "required", "degraded", f"PBF 있음 ({pbf.name}) — run_all 을 아직 안 돌렸다. 샘플 격자로 동작 중", "GRAPH_SOURCE")
    else:
        add("graph", "부산 그래프 데이터", "required", "degraded", "OSM PBF 없음 (data/raw/south-korea-latest.osm.pbf) — 샘플 격자 도시로 동작", "GRAPH_SOURCE")
    add("dem", "부산 DEM", "required", "ok" if (ROOT / "data" / "dem" / "busan_dem_clipped_90m.tif").is_file() else "missing", "저장소에 포함" if (ROOT / "data" / "dem" / "busan_dem_clipped_90m.tif").is_file() else "data/dem 파일 없음", "")

    add("basemap", "배경 지도 (VWorld)", "recommended", "ok" if g("VITE_VWORLD_KEY") or g("VITE_BASEMAP_STYLE_URL") else "degraded",
        "설정됨" if g("VITE_VWORLD_KEY") or g("VITE_BASEMAP_STYLE_URL") else "OpenFreeMap(OSM) 배경으로 대체", "VITE_VWORLD_KEY")
    add("places", "장소 검색 (Kakao REST)", "recommended", "ok" if g("KAKAO_REST_API_KEY") else "degraded", "설정됨" if g("KAKAO_REST_API_KEY") else "역·정류장 이름만 검색되는 로컬 색인", "KAKAO_REST_API_KEY")
    add("login_kakao", "카카오 로그인", "recommended", "ok" if g("KAKAO_CLIENT_ID") else "missing", "설정됨" if g("KAKAO_CLIENT_ID") else "버튼 숨김", "KAKAO_CLIENT_ID")
    add("login_naver", "네이버 로그인", "recommended", "ok" if g("NAVER_CLIENT_ID") and g("NAVER_CLIENT_SECRET") else "missing", "설정됨" if g("NAVER_CLIENT_ID") else "버튼 숨김", "NAVER_CLIENT_ID")
    add("bus", "버스 노선 (BIMS 키)", "recommended", "ok" if g("BUS_SERVICE_KEY") or (ROOT / "data" / "build" / "bims").is_dir() else "degraded",
        "설정됨" if g("BUS_SERVICE_KEY") else "키 없음 → 파이프라인에 버스 미포함 (GTFS 폴더로 대체 가능)", "BUS_SERVICE_KEY")
    pub = g("PUBLIC_BASE_URL", "")
    add("https", "HTTPS 공개 주소", "recommended", "ok" if pub.startswith("https://") else "degraded", "HTTPS" if pub.startswith("https://") else f"{pub or '(없음)'} — 운영에서는 https 도메인 + COOKIE_SECURE=true", "PUBLIC_BASE_URL")
    wp = g("WEATHER_PROVIDER", "open_meteo")
    add("weather", "실시간 날씨", "recommended", "missing" if (wp == "openweather" and not g("OPENWEATHER_API_KEY")) else ("degraded" if wp == "none" else "ok"),
        f"{wp}" + (" (키 불필요)" if wp == "open_meteo" else ""), "WEATHER_PROVIDER")
    add("vworld_heights", "건물 실측 높이 (VWorld)", "optional", "ok" if g("VWORLD_API_KEY") or g("VITE_VWORLD_KEY") else "degraded", "설정됨" if g("VWORLD_API_KEY") or g("VITE_VWORLD_KEY") else "OSM 층수 기반 높이만 사용", "VWORLD_API_KEY")
    add("alerts", "임계 초과 알림", "optional", "ok" if g("ALERT_WEBHOOK_URL") else "missing", "웹훅 설정됨" if g("ALERT_WEBHOOK_URL") else "웹훅 없음 (/admin/alerts 에서 넣어도 됨)", "ALERT_WEBHOOK_URL")
    return items


def main() -> int:
    ap = argparse.ArgumentParser(description="Pathfinder 설정 진단")
    ap.add_argument("--env", default=str(ROOT / ".env"))
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    env_path = Path(a.env)
    env = merged_env(env_path)
    items = run(env)
    if a.json:
        print(json.dumps({"env_file": str(env_path), "items": items}, ensure_ascii=False, indent=1))
    else:
        mark = {"ok": "✅", "degraded": "🟡", "missing": "❌"}
        level = {"required": "필수", "recommended": "권장", "optional": "선택"}
        print(f"Pathfinder 설정 진단 — {env_path}{'' if env_path.is_file() else ' (없음: cp .env.example .env)'}\n")
        for lv in ("required", "recommended", "optional"):
            print(f"[{level[lv]}]")
            for i in items:
                if i["level"] == lv:
                    print(f"  {mark[i['status']]} {i['label']:<22} {i['detail']}" + (f"   ({i['env']})" if i["env"] else ""))
            print()
        missing_req = [i for i in items if i["level"] == "required" and i["status"] == "missing"]
        degraded = [i["label"] for i in items if i["status"] == "degraded"]
        if missing_req:
            print("필수 항목이 비어 있어 서비스가 온전히 뜨지 않아요: " + ", ".join(i["label"] for i in missing_req))
        else:
            print("서비스는 뜹니다." + (f" 축소 동작: {', '.join(degraded)}" if degraded else " 모든 기능이 온전히 켜져 있어요."))
        print("기입 위치와 발급 절차: docs/SETUP_GUIDE.md")
    return 1 if any(i["level"] == "required" and i["status"] == "missing" for i in items) else 0


if __name__ == "__main__":
    sys.exit(main())
