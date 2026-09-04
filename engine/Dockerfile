# 빌드 컨텍스트: 레포 루트 (docker compose build 가 그렇게 설정한다)
FROM python:3.11-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

COPY engine/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY engine/app ./app
COPY data/samples ./data/samples

ENV GRAPH_SOURCE=auto GRAPH_BUNDLE_PATH=/app/data/samples/grid_city.npz BUILDINGS_PATH=/app/data/samples/grid_city_buildings.json GRAPH_BUILD_DIR=/app/data/build

EXPOSE 8001
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]

# ---- 파이프라인 스테이지 (docker compose --profile pipeline): OSM·DEM·버스 빌드 의존성 포함
FROM python:3.11-slim AS pipeline
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y --no-install-recommends libgdal-dev gdal-bin build-essential && rm -rf /var/lib/apt/lists/*
COPY engine/requirements.txt engine/requirements-pipeline.txt ./
RUN pip install --no-cache-dir -r requirements-pipeline.txt
COPY engine/app ./app
