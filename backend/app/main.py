from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import init_db
from app.routers import health, place, route

# ORM 모델 임포트 (create_all 시 인식되도록)
import app.models.user  # noqa: F401
import app.models.route  # noqa: F401
import app.models.place  # noqa: F401


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 앱 시작 시 DB 테이블 자동 생성
    await init_db()
    yield


app = FastAPI(
    title="Pathfinder Backend",
    description="교통약자 맞춤형 경로 추천 서비스 백엔드 API",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS 설정 (프론트엔드 개발 서버 허용)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://frontend:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(route.router)
app.include_router(place.router)
