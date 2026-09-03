# 빌드 컨텍스트: 레포 루트 (docker compose build 가 그렇게 설정한다)
FROM python:3.11-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

COPY engine/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY engine/app ./app
COPY data/samples ./data/samples

ENV GRAPH_SOURCE=file GRAPH_BUNDLE_PATH=/app/data/samples/grid_city.npz BUILDINGS_PATH=/app/data/samples/grid_city_buildings.json

EXPOSE 8001
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
