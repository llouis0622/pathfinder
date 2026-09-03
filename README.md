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

> 구현 진행 중. 단계별 상태는 커밋 이력을 참고한다.
