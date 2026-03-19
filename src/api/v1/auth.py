from fastapi import APIRouter

from core.logger import get_logger

router = APIRouter()

logger = get_logger({"ping": "pong"})


@router.get("/ping")
def ping():
    logger.info("ping")
    return {"ping": "pong2"}
