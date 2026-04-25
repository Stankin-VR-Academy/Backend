from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.logger import get_logger
from src.database.database import get_db
from src.models.user import User
from src.schemas.user import UserResponse, UserUpdate
from src.services.auth import get_current_user

router = APIRouter()
logger = get_logger({"module": "profiles"})


@router.get("/me", response_model=UserResponse)
async def get_current_profile(current_user: User = Depends(get_current_user)) -> Any:
    """
    Получить профиль текущего пользователя.

    Возвращает профиль текущего пользователя.
    """
    logger.info("Get current profile attempt")
    return current_user


@router.patch("/me", response_model=UserResponse)
async def update_current_profile(
    profile_data: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Обновить профиль текущего пользователя.

    Обновляет профиль текущего пользователя.
    """
    logger.info(f"Update profile attempt: {profile_data}")
    if profile_data.full_name is not None:
        current_user.full_name = profile_data.full_name
    if profile_data.avatar_url is not None:
        current_user.avatar_url = profile_data.avatar_url

    await db.commit()
    await db.refresh(current_user)
    return current_user
