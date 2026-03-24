from typing import Any
from uuid import uuid4

from fastapi import APIRouter

from core.logger import get_logger
from src.schemas.user import UserResponse, UserUpdate

router = APIRouter()
logger = get_logger({"module": "profiles"})


@router.get("/me", response_model=UserResponse)
async def get_current_profile() -> Any:
    """
    Получить профиль текущего пользователя.

    **Заглушка:** Возвращает фиктивные данные пользователя.
    """
    logger.info("Get current profile attempt")
    # TODO: Реализовать получение профиля текущего пользователя
    return UserResponse(
        id=uuid4(),
        email="user@example.com",
        username="test_user",
        full_name="Test User",
        role="student",
        avatar_url="https://cdn.example.com/avatars/user123.jpg",
        is_active=True,
        is_verified=True,
        created_at="2024-01-15T10:30:00Z",
        updated_at="2024-01-20T14:45:00Z",
    )


@router.patch("/me", response_model=UserResponse)
async def update_current_profile(profile_data: UserUpdate) -> Any:
    """
    Обновить профиль текущего пользователя.

    **Заглушка:** Возвращает обновленные фиктивные данные.
    """
    logger.info(f"Update profile attempt: {profile_data}")
    # TODO: Реализовать обновление профиля
    return UserResponse(
        id=uuid4(),
        email="user@example.com",
        username="test_user",
        full_name=profile_data.full_name or "Test User",
        role="student",
        avatar_url=profile_data.avatar_url or "https://cdn.example.com/avatars/user123.jpg",
        is_active=True,
        is_verified=True,
        created_at="2024-01-15T10:30:00Z",
        updated_at="2024-01-20T14:45:00Z",
    )
