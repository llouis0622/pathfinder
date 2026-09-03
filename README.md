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
| [docs/PERSONALIZATION.md](docs/PERSONALIZATION.md) | 카카오·네이버 로그인과 RL(컨텍스트 밴딧) 개인화 재정렬 |

## 진행 상태

| 단계 | 내용 | 상태 |
|---|---|---|
| Phase 0 | 설계 문서, 부산 기초 데이터(DEM·지하철·버스정류장·경계) | 완료 |
| Phase 1 | 엔진 코어: 멀티모달 그래프, 4개 프로필 비용 모델, ACO + GA, Top 3 다양성, 그늘·경사·배지 | 완료 |
| Phase 2 | 데이터 파이프라인(OSM 보행망·DEM·지하철·버스·건물)과 PostGIS 스토어 | 완료 |
| Phase 3 | 엔진 API, 백엔드(장소 검색·날씨·오케스트레이션·로그) | 완료 |
| Phase 4 | 프론트엔드(Kakao 지도 / 약식 SVG 지도, 프로필·조건, Top 3 카드·구간 안내·경사/그늘 오버레이) | 완료 |
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
# 프론트엔드 (vite dev 서버가 /api 를 8000 으로 프록시)
cd frontend && npm install && cp .env.example .env   # VITE_KAKAO_MAP_KEY 입력 (없으면 SVG 약식 지도)
npm run dev                                          # http://localhost:5173
```

API 목록은 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md#api)에 있다.

## 테스트

```bash
cd engine
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
pytest -q            # PostGIS 통합 테스트는 PATHFINDER_TEST_DSN 접속이 될 때만 실행
cd ../backend && pip install -r requirements-dev.txt && pytest -q   # 외부 API·엔진은 가짜 응답, DB는 SQLite
cd ../frontend && npm install && npm run typecheck && npm test        # vitest + Testing Library
```

## 프론트엔드 구성

- `src/types.ts`: 엔진 `RouteOut` 과 1:1 인 타입. 백엔드가 경로를 그대로 전달하므로 이 파일만 맞추면 된다.
- `src/components/MapView.tsx`: Kakao 지도. 선택 경로를 구간별 색(도보·지하철·버스)으로 그리고, "경사"/"그늘" 오버레이는 보행 구간을 경사 등급·그늘 비율로 칠한다.
  키가 없으면 `SchematicMap.tsx`(SVG 약식 지도)로 자동 대체된다.
- `src/components/RouteRow.tsx`, `RouteDetail.tsx`: 네이버·카카오 길찾기식 경로 행(소요시간·수단 바·요약·태그)과 세로 타임라인 상세.
- `src/components/ProfileChips.tsx`: 이용자 유형 4종 칩과 "그늘 우선" 토글. 날씨는 선택 없이 실시간으로 반영되고, 경사 회피는 항상 켜져 있다.
- 디자인: 화이트·블랙·그레이 톤(토스 스타일), 지하철 노선색만 정보 표시용으로 유지. 길찾기 패널은 카카오맵·네이버지도처럼 지도 위 상단에 뜬다.
- 로그인: 카카오·네이버 OAuth. 로그인 후 "이 경로로 가기"를 누르면 취향이 학습되어 다음 추천 순위에 반영된다 (`ALLOW_DEV_LOGIN=true`면 키 없이 데모 계정으로 체험).

합성 격자 도시(`data/samples/grid_city.npz`)로 엔진 전체를 검증한다. 실제 부산 그래프 빌드는
[docs/DATA_PIPELINE.md](docs/DATA_PIPELINE.md)를 따른다.
