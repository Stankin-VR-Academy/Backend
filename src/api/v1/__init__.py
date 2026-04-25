# API v1 module
from fastapi import APIRouter

from src.api.v1 import auth, chat, profiles, rooms, sessions

api_router = APIRouter()

# Include all routers
api_router.include_router(auth.router, prefix="/auth", tags=["Auth"])
api_router.include_router(profiles.router, prefix="/profiles", tags=["Profiles"])
api_router.include_router(rooms.router, prefix="/rooms", tags=["Rooms"])
api_router.include_router(sessions.router, prefix="/sessions", tags=["Sessions"])
api_router.include_router(chat.router, prefix="/chat", tags=["Chat"])
