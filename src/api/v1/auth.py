from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.logger import get_logger
from src.database.database import get_db
from src.models.user import User
from src.schemas.user import TokenRefresh, TokenResponse, UserCreate, UserLogin, UserResponse
from src.services.auth import (
    authenticate_user,
    create_access_token,
    create_refresh_token,
    decode_token,
    get_user_by_email,
    get_user_by_id,
    get_user_by_username,
    hash_password,
)

router = APIRouter()
logger = get_logger({"module": "auth"})


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserCreate, db: AsyncSession = Depends(get_db)) -> Any:
    """
    Регистрация нового пользователя.

    Регистрирует нового пользователя.
    """
    logger.info(f"Register attempt for email: {user_data.email}")
    try:
        existing_user = await get_user_by_email(db, user_data.email)
        if existing_user:
            logger.warning(f"Register blocked: email already exists ({user_data.email})")
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

        existing_username = await get_user_by_username(db, user_data.username)
        if existing_username:
            logger.warning(f"Register blocked: username already exists ({user_data.username})")
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already taken")

        user = User(
            email=user_data.email,
            username=user_data.username,
            full_name=user_data.full_name,
            password_hash=hash_password(user_data.password),
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        logger.info(f"User registered successfully: id={user.id}, email={user.email}")
        return user
    except Exception as error:
        await db.rollback()
        logger.exception(f"Unexpected register error for email={user_data.email}: {error}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unexpected server error",
        ) from error


@router.post("/login", response_model=TokenResponse)
async def login(credentials: UserLogin, db: AsyncSession = Depends(get_db)) -> Any:
    """
    Вход в систему.

    Возвращает пару access/refresh токенов.
    """
    logger.info(f"Login attempt for email: {credentials.email}")
    try:
        user = await authenticate_user(db, credentials.email, credentials.password)
        if not user:
            logger.warning(f"Login failed for email={credentials.email}")
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

        response = TokenResponse(
            access_token=create_access_token(user),
            refresh_token=create_refresh_token(user),
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user=user,
        )
        logger.info(f"Login success for user_id={user.id}")
        return response
    except HTTPException:
        raise
    except Exception as error:
        logger.exception(f"Unexpected login error for email={credentials.email}: {error}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unexpected server error",
        ) from error


@router.post("/refresh", response_model=dict)
async def refresh_token(token_data: TokenRefresh, db: AsyncSession = Depends(get_db)) -> Any:
    """
    Обновление access токена.

    Обновление access токена по refresh токену.
    """
    logger.info("Token refresh attempt")
    try:
        payload = decode_token(token_data.refresh_token)
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")

        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

        user = await get_user_by_id(db, user_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

        logger.info(f"Token refresh success for user_id={user.id}")
        return {
            "access_token": create_access_token(user),
            "token_type": "bearer",
            "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        }
    except HTTPException:
        raise
    except Exception as error:
        logger.exception(f"Unexpected refresh error: {error}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unexpected server error",
        ) from error


@router.post("/logout")
async def logout() -> Any:
    """
    Выход из системы.

    **Заглушка:** Возвращает успешное сообщение.
    """
    logger.info("Logout attempt")
    # TODO: Реализовать логику выхода
    return {"message": "Successfully logged out"}
