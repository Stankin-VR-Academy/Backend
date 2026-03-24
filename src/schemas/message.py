from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from src.models.message import MessageType
from src.schemas.user import UserResponse


class MessageBase(BaseModel):
    content: str = Field(..., min_length=1)
    message_type: MessageType = MessageType.TEXT
    reply_to_id: Optional[UUID] = None


class MessageCreate(MessageBase):
    room_id: UUID


class MessageUpdate(BaseModel):
    content: str = Field(..., min_length=1)


class MessageResponse(BaseModel):
    id: UUID
    room_id: UUID
    user_id: UUID
    content: str
    message_type: MessageType
    reply_to_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime
    is_edited: bool

    class Config:
        from_attributes = True


class MessageDetailResponse(MessageResponse):
    user: Optional[UserResponse] = None
    reply_to: Optional[MessageResponse] = None
    replies: list[MessageResponse] = []


class RoomJoinTokenCreate(BaseModel):
    room_id: UUID
    expires_at: datetime
    max_uses: int = Field(default=1, gt=0)


class RoomJoinTokenResponse(BaseModel):
    id: UUID
    room_id: UUID
    user_id: UUID
    token: str
    expires_at: datetime
    max_uses: int
    uses_count: int
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True
