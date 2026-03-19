from os import getenv

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # PostgreSQL

    DATABASE_URL: str = getenv("DATABASE_URL")

    # Redis
    REDIS_URL: str = getenv("REDIS_URL")

    # JWT
    SECRET_KEY: str = getenv("SECRET_KEY")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Room Join Tokens
    ROOM_JOIN_TOKEN_EXPIRE_MINUTES: int = 15

    # API
    PROJECT_NAME: str = "VR Academy API"

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True, extra="ignore")


settings = Settings()
