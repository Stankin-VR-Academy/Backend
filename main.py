from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from sqlalchemy import text

from core.config import settings
from core.logger import logger
from src.api.v1 import api_router
from src.database.database import AsyncSessionLocal
from src.services.redis_client import redis_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle events для приложения"""
    logger.info("Starting application...")
    await redis_client.connect()

    try:
        async with AsyncSessionLocal() as db:
            await db.execute(text("SELECT 1"))
            logger.info("Database connected successfully")
    except Exception as e:
        logger.error(f"Failed to connect to database: {e}")
        raise

    yield

    logger.info("Shutting down application...")
    await redis_client.disconnect()


app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    description="VR Academy API - Backend для VR-платформы",
    lifespan=lifespan,
)


app.include_router(api_router, prefix="/api/v1")


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True, log_config=None)
