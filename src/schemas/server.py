from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from src.schemas.user import UserResponse


class ServerBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    icon_url: Optional[str] = None
    max_members: int = Field(default=100, gt=0)


class ServerCreate(ServerBase):
    pass


class ServerUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    icon_url: Optional[str] = None
    max_members: Optional[int] = Field(None, gt=0)
    is_active: Optional[bool] = None


class ServerResponse(BaseModel):
    id: UUID
    name: str
    description: Optional[str] = None
    owner_id: UUID
    icon_url: Optional[str] = None
    max_members: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ServerDetailResponse(ServerResponse):
    owner: Optional[UserResponse] = None
    member_count: int = 0
    room_count: int = 0


class ServerMemberBase(BaseModel):
    role: str = Field(default="member")


class ServerMemberUpdate(BaseModel):
    role: str


class ServerMemberResponse(BaseModel):
    id: UUID
    server_id: UUID
    user_id: UUID
    role: str
    joined_at: datetime

    class Config:
        from_attributes = True
