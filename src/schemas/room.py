from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from src.models.room import RoomType
from src.schemas.user import UserResponse


class RoomBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    room_type: RoomType = RoomType.CLASSROOM
    max_participants: int = Field(default=30, gt=0)
    is_voice_enabled: bool = True
    is_text_enabled: bool = True


class RoomCreate(RoomBase):
    pass


class RoomUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    room_type: Optional[RoomType] = None
    max_participants: Optional[int] = Field(None, gt=0)
    is_voice_enabled: Optional[bool] = None
    is_text_enabled: Optional[bool] = None
    is_active: Optional[bool] = None


class RoomResponse(BaseModel):
    id: UUID
    name: str
    description: Optional[str] = None
    room_type: RoomType
    max_participants: int
    is_voice_enabled: bool
    is_text_enabled: bool
    created_by: UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class RoomDetailResponse(RoomResponse):
    created_by_user: Optional[UserResponse] = None
    participant_count: int = 0
    active_session_count: int = 0


class RoomMemberBase(BaseModel):
    role: str = Field(default="participant")


class RoomMemberUpdate(BaseModel):
    role: str


class RoomMemberResponse(BaseModel):
    id: UUID
    room_id: UUID
    user_id: UUID
    role: str
    joined_at: datetime

    class Config:
        from_attributes = True
