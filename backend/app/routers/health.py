from fastapi import APIRouter

router = APIRouter()


@router.get("/health", summary="헬스체크", description="백엔드 서버 상태를 확인합니다.")
async def health():
    return {"status": "ok", "service": "backend"}
