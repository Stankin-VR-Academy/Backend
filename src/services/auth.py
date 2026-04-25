import base64
import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from authlib.jose import JoseError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.logger import get_logger
from src.database.database import get_db
from src.models.user import User
from src.services.redis_client import redis_client

PASSWORD_SCHEME = "pbkdf2_sha256"
PBKDF2_ITERATIONS = 100_000
security = HTTPBearer()
logger = get_logger({"module": "auth_service"})
TOKEN_BLACKLIST_PREFIX = "auth:blacklist"


def _utc_now() -> datetime:
    return datetime.now(UTC)


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    password_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PBKDF2_ITERATIONS,
    )
    return (
        f"{PASSWORD_SCHEME}${PBKDF2_ITERATIONS}$"
        f"{base64.b64encode(salt).decode('utf-8')}$"
        f"{base64.b64encode(password_hash).decode('utf-8')}"
    )


def verify_password(password: str, hashed_password: str) -> bool:
    try:
        scheme, iterations, salt_b64, hash_b64 = hashed_password.split("$", 3)
    except ValueError:
        return False

    if scheme != PASSWORD_SCHEME:
        return False

    salt = base64.b64decode(salt_b64.encode("utf-8"))
    expected_hash = base64.b64decode(hash_b64.encode("utf-8"))
    candidate_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        int(iterations),
    )
    return hmac.compare_digest(candidate_hash, expected_hash)


def _build_token(payload: dict[str, Any], expires_delta: timedelta) -> str:
    now = _utc_now()
    claims = {
        **payload,
        "iat": int(now.timestamp()),
        "exp": int((now + expires_delta).timestamp()),
    }
    header = {"alg": settings.ALGORITHM}
    token = jwt.encode(header, claims, settings.SECRET_KEY)
    return token.decode("utf-8")


def create_access_token(user: User) -> str:
    return _build_token(
        payload={"sub": str(user.id), "email": user.email, "type": "access"},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )


def create_refresh_token(user: User) -> str:
    return _build_token(
        payload={"sub": str(user.id), "email": user.email, "type": "refresh"},
        expires_delta=timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )


def decode_token(token: str) -> dict[str, Any]:
    try:
        claims = jwt.decode(token, settings.SECRET_KEY)
        claims.validate()
        return dict(claims)
    except JoseError as error:
        logger.warning(f"Token decode failed: {error.__class__.__name__}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        ) from error


def _get_blacklist_key(token: str) -> str:
    return f"{TOKEN_BLACKLIST_PREFIX}:{token}"


async def revoke_access_token(token: str) -> None:
    payload = decode_token(token)
    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only access token can be revoked",
        )

    exp = payload.get("exp")
    if not isinstance(exp, int):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid token payload",
        )

    ttl_seconds = max(exp - int(_utc_now().timestamp()), 1)
    if redis_client.redis is not None:
        await redis_client.redis.set(_get_blacklist_key(token), "1", ex=ttl_seconds)
    else:
        logger.warning("Redis is unavailable, token revoke skipped")


async def is_access_token_revoked(token: str) -> bool:
    if redis_client.redis is None:
        return False
    value = await redis_client.redis.get(_get_blacklist_key(token))
    return value is not None


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def get_user_by_username(db: AsyncSession, username: str) -> User | None:
    result = await db.execute(select(User).where(User.username == username))
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: str) -> User | None:
    try:
        normalized_user_id = UUID(user_id)
    except ValueError:
        return None

    result = await db.execute(select(User).where(User.id == normalized_user_id))
    return result.scalar_one_or_none()


async def authenticate_user(db: AsyncSession, email: str, password: str) -> User | None:
    user = await get_user_by_email(db, email)
    if not user or not verify_password(password, user.password_hash):
        logger.info(f"Authentication failed for email={email}")
        return None
    logger.info(f"Authentication succeeded for user_id={user.id}")
    return user


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    token = credentials.credentials
    if await is_access_token_revoked(token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked",
        )

    payload = decode_token(token)
    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    user = await get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    return user
