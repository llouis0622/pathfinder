"""부산 BIMS(버스정보관리시스템) 공공 API에서 노선·정류장 순서를 받아 캐시 폴더에 저장한다.

    python -m app.pipeline.bims_fetch --out ../data/build/bims --key $BUS_SERVICE_KEY

엔드포인트 (https://apis.data.go.kr/6260000/BusanBIMS)
- busInfo             : 노선 목록 (lineid, lineno, headway 등). 응답 필드는 계정·버전에 따라 다를 수 있다.
- busInfoByRouteId    : lineid 별 정류장 순서 (bstopidx, nodeid, arsno, bstopnm, lat, lin, direction ...)
- bitArrByArsno       : 정류장(arsno) 경유 노선 (busInfo 가 비어 있을 때 노선 id 발견용)

응답 필드 이름이 문서와 다를 수 있으므로 원본 항목을 그대로 저장하고, build_bus.load_bims_cache 가
여러 후보 이름을 관용적으로 읽는다. 실행 후 `--report` 로 필드 커버리지를 확인한다.
"""
from __future__ import annotations

import argparse
import json
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import httpx

BASE_URL = "https://apis.data.go.kr/6260000/BusanBIMS"


def _items(content: bytes) -> list[dict[str, str]]:
    """XML 또는 JSON 응답에서 item 목록을 뽑는다."""
    text = content.decode("utf-8", errors="replace").strip()
    if text.startswith("{"):
        data = json.loads(text)
        body = data.get("response", {}).get("body", {})
        items = body.get("items", {})
        if isinstance(items, dict):
            items = items.get("item", [])
        return [dict(i) for i in (items if isinstance(items, list) else [items])]
    root = ET.fromstring(text)
    out = []
    for item in root.iter("item"):
        out.append({child.tag: (child.text or "").strip() for child in item})
    return out


def _get(client: httpx.Client, path: str, key: str, **params) -> list[dict[str, str]]:
    query = {"serviceKey": key, "numOfRows": 500, "pageNo": 1, "resultType": "json", **params}
    resp = client.get(f"{BASE_URL}/{path}", params=query)
    resp.raise_for_status()
    return _items(resp.content)


def fetch(out_dir: Path, key: str, line_ids: list[str] | None = None, ars_seed: list[str] | None = None,
          sleep_s: float = 0.15, limit: int | None = None) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    report = {"routes_listed": 0, "routes_fetched": 0, "errors": 0}
    with httpx.Client(timeout=20.0) as client:
        routes: dict[str, dict] = {}
        if not line_ids:
            try:
                for row in _get(client, "busInfo", key):
                    lid = str(row.get("lineid") or "").strip()
                    if lid:
                        routes[lid] = row
            except (httpx.HTTPError, ValueError) as exc:
                print(f"busInfo 실패 ({exc}); bitArrByArsno 로 노선 발견을 시도합니다")
            if not routes and ars_seed:
                for ars in ars_seed:
                    try:
                        for row in _get(client, "bitArrByArsno", key, arsno=ars):
                            lid = str(row.get("lineid") or "").strip()
                            if lid:
                                routes.setdefault(lid, {"lineid": lid, "lineno": row.get("lineno", "")})
                    except (httpx.HTTPError, ValueError):
                        report["errors"] += 1
                    time.sleep(sleep_s)
            line_ids = list(routes)
        report["routes_listed"] = len(line_ids)
        (out_dir / "routes.json").write_text(json.dumps(routes, ensure_ascii=False, indent=1), encoding="utf-8")
        for i, lid in enumerate(line_ids):
            if limit is not None and i >= limit:
                break
            target = out_dir / f"route_{lid}.json"
            if target.is_file():
                continue
            try:
                rows = _get(client, "busInfoByRouteId", key, lineid=lid)
            except (httpx.HTTPError, ValueError) as exc:
                report["errors"] += 1
                print(f"lineid={lid} 실패: {exc}")
                continue
            target.write_text(json.dumps({"lineid": lid, "stops": rows}, ensure_ascii=False), encoding="utf-8")
            report["routes_fetched"] += 1
            time.sleep(sleep_s)
    return report


def field_report(cache_dir: Path) -> dict:
    counts: dict[str, int] = {}
    files = 0
    for path in cache_dir.glob("route_*.json"):
        files += 1
        for row in json.loads(path.read_text(encoding="utf-8")).get("stops", []):
            for k in row:
                counts[k] = counts.get(k, 0) + 1
    return {"files": files, "fields": dict(sorted(counts.items(), key=lambda kv: -kv[1]))}


def main() -> None:
    parser = argparse.ArgumentParser(description="부산 BIMS 노선·정류장 수집")
    parser.add_argument("--out", type=Path, default=Path("../data/build/bims"))
    parser.add_argument("--key", required=False, default="", help="공공데이터포털 Decoding 인증키")
    parser.add_argument("--line-ids", nargs="*", default=None)
    parser.add_argument("--ars-seed-csv", type=Path, default=None, help="정류장 CSV(ars_no 열)로 노선 발견")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--report", action="store_true", help="캐시 필드 커버리지만 출력")
    args = parser.parse_args()
    if args.report:
        print(json.dumps(field_report(args.out), ensure_ascii=False, indent=1))
        return
    if not args.key:
        parser.error("--key 가 필요합니다 (BUS_SERVICE_KEY)")
    ars_seed = None
    if args.ars_seed_csv:
        import csv

        with open(args.ars_seed_csv, encoding="utf-8-sig", newline="") as f:
            ars_seed = [r["ars_no"] for r in csv.DictReader(f) if r.get("ars_no")]
    print(json.dumps(fetch(args.out, args.key, args.line_ids, ars_seed, limit=args.limit), ensure_ascii=False))


if __name__ == "__main__":
    main()
