from contextlib import asynccontextmanager
import asyncio

import uvicorn
from fastapi import FastAPI
from sqlalchemy import text

from core.config import settings
from core.logger import logger
from src.api.v1 import api_router
from src.database.database import AsyncSessionLocal, Base, engine
from src.services.redis_client import redis_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle events для приложения"""
    logger.info("Starting application...")
    await redis_client.connect()
    logger.info("Ensuring database schema is initialized...")
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database schema initialized successfully")
    except Exception as e:
        logger.exception(f"Failed to initialize database schema: {e}")

    max_attempts = 5
    retry_delay_seconds = 2

    for attempt in range(1, max_attempts + 1):
        try:
            async with AsyncSessionLocal() as db:
                await db.execute(text("SELECT 1"))
                logger.info("Database connected successfully")
                break
        except Exception as e:
            if attempt == max_attempts:
                logger.exception(
                    f"Failed to connect to database after {max_attempts} attempts: {e}"
                )
            else:
                logger.warning(
                    f"Database connection attempt {attempt}/{max_attempts} failed: {e}. "
                    f"Retrying in {retry_delay_seconds}s..."
                )
                await asyncio.sleep(retry_delay_seconds)

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
