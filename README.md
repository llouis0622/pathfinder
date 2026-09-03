# Pathfinder

부산 교통약자(휠체어·고령자·보행보조기·시각장애인)를 위한 **자체 경로 탐색** 서비스.
OSM 보행망 + 지하철 + 버스를 하나의 그래프로 만들고, 날씨·건물 그늘·경사·계단·엘리베이터를
비용에 반영해 **ACO + GA**로 서로 다른 상위 3개 경로를 찾는다.

| 문서 | 내용 |
|---|---|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | 서비스 구성, 요청 흐름, 데이터 원칙 |
| [docs/COST_MODEL.md](docs/COST_MODEL.md) | 프로필별·날씨별 엣지 비용 공식 |
| [docs/ALGORITHMS.md](docs/ALGORITHMS.md) | 회랑 추출, ACO, GA, 다양성 Top 3, 배지 |
| [docs/DATA_PIPELINE.md](docs/DATA_PIPELINE.md) | OSM·DEM·지하철·버스·건물 빌드와 PostGIS 스키마 |

## 진행 상태

| 단계 | 내용 | 상태 |
|---|---|---|
| Phase 0 | 설계 문서, 부산 기초 데이터(DEM·지하철·버스정류장·경계) | 완료 |
| Phase 1 | 엔진 코어: 멀티모달 그래프, 4개 프로필 비용 모델, ACO + GA, Top 3 다양성, 그늘·경사·배지 | 완료 |
| Phase 2 | 데이터 파이프라인(OSM 보행망·DEM·지하철·버스·건물)과 PostGIS 스토어 | 완료 |
| Phase 3 | 엔진 API, 백엔드(장소 검색·날씨·오케스트레이션·로그) | 완료 |
| Phase 4 | 프론트엔드(Kakao 지도, Top 3 카드) | 예정 |
| Phase 5 | Docker Compose, CI, 통합 검증 | 예정 |

## 로컬 실행 (컨테이너 없이)

```bash
# 엔진 (합성 그래프)
cd engine && pip install -r requirements-dev.txt
GRAPH_SOURCE=file uvicorn app.main:app --port 8001
# 백엔드 (PostgreSQL 필요, 테이블은 시작 시 자동 생성)
cd backend && pip install -r requirements-dev.txt
DATABASE_URL=postgresql+asyncpg://pathfinder:pathfinder_dev@localhost:5432/pathfinder ENGINE_URL=http://localhost:8001 \
  uvicorn app.main:app --port 8000
curl -X POST localhost:8000/api/route -H 'content-type: application/json' \
  -d '{"origin":{"lat":35.15,"lng":129.06},"destination":{"lat":35.1536,"lng":129.0726},"profile":"wheelchair"}'
```

API 목록은 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md#api)에 있다.

## 테스트

```bash
cd engine
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
pytest -q            # PostGIS 통합 테스트는 PATHFINDER_TEST_DSN 접속이 될 때만 실행
cd ../backend && pip install -r requirements-dev.txt && pytest -q   # 외부 API·엔진은 가짜 응답, DB는 SQLite
```

합성 격자 도시(`data/samples/grid_city.npz`)로 엔진 전체를 검증한다. 실제 부산 그래프 빌드는
[docs/DATA_PIPELINE.md](docs/DATA_PIPELINE.md)를 따른다.
