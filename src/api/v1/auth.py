from typing import Any
from uuid import uuid4

from fastapi import APIRouter, status

from core.logger import get_logger
from src.schemas.user import TokenRefresh, TokenResponse, UserCreate, UserLogin, UserResponse

router = APIRouter()
logger = get_logger({"module": "auth"})


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserCreate) -> Any:
    """
    Регистрация нового пользователя.

    **Заглушка:** Возвращает фиктивные данные пользователя.
    """
    logger.info(f"Register attempt for email: {user_data.email}")
    # TODO: Реализовать логику регистрации
    return UserResponse(
        id=uuid4(),
        email=user_data.email,
        username=user_data.username,
        full_name=user_data.full_name,
        role="student",
        avatar_url=None,
        is_active=True,
        is_verified=False,
        created_at="2024-01-15T10:30:00Z",
        updated_at="2024-01-15T10:30:00Z",
    )


@router.post("/login", response_model=TokenResponse)
async def login(credentials: UserLogin) -> Any:
    """
    Вход в систему.

    **Заглушка:** Возвращает фиктивные токены.
    """
    logger.info(f"Login attempt for email: {credentials.email}")
    # TODO: Реализовать логику входа
    return TokenResponse(
        access_token="fake_access_token_" + str(uuid4()),
        refresh_token="fake_refresh_token_" + str(uuid4()),
        token_type="bearer",
        expires_in=1800,
        user=UserResponse(
            id=uuid4(),
            email=credentials.email,
            username="test_user",
            full_name="Test User",
            role="student",
            avatar_url=None,
            is_active=True,
            is_verified=True,
            created_at="2024-01-15T10:30:00Z",
            updated_at="2024-01-15T10:30:00Z",
        ),
    )


@router.post("/refresh", response_model=dict)
async def refresh_token(token_data: TokenRefresh) -> Any:
    """
    Обновление access токена.

    **Заглушка:** Возвращает фиктивный access токен.
    """
    logger.info("Token refresh attempt")
    # TODO: Реализовать логику обновления токена
    return {
        "access_token": "new_fake_access_token_" + str(uuid4()),
        "token_type": "bearer",
        "expires_in": 1800,
    }


@router.post("/logout")
async def logout() -> Any:
    """
    Выход из системы.

    **Заглушка:** Возвращает успешное сообщение.
    """
    logger.info("Logout attempt")
    # TODO: Реализовать логику выхода
    return {"message": "Successfully logged out"}
