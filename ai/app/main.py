from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import pathfinding

app = FastAPI(
    title="Pathfinder AI Server",
    description="교통약자 맞춤형 경로탐색 AI 서버 — KSP / GA / ACO / Tree 알고리즘",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", summary="헬스체크", description="AI 서버 상태를 확인합니다.")
async def health():
    return {"status": "ok", "service": "ai"}


app.include_router(pathfinding.router)
