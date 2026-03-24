from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class UserSessionBase(BaseModel):
    vivox_session_id: Optional[str] = None
    position_x: float = 0.0
    position_y: float = 0.0
    position_z: float = 0.0
    rotation_x: float = 0.0
    rotation_y: float = 0.0
    rotation_z: float = 0.0
    is_muted: bool = False
    is_deafened: bool = False


class UserSessionCreate(UserSessionBase):
    room_id: UUID


class UserSessionUpdate(BaseModel):
    position_x: Optional[float] = None
    position_y: Optional[float] = None
    position_z: Optional[float] = None
    rotation_x: Optional[float] = None
    rotation_y: Optional[float] = None
    rotation_z: Optional[float] = None
    is_muted: Optional[bool] = None
    is_deafened: Optional[bool] = None


class UserSessionResponse(BaseModel):
    id: UUID
    user_id: UUID
    room_id: UUID
    vivox_session_id: Optional[str] = None
    position_x: float
    position_y: float
    position_z: float
    rotation_x: float
    rotation_y: float
    rotation_z: float
    is_muted: bool
    is_deafened: bool
    started_at: datetime
    last_active_at: datetime
    ended_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class JoinRoomRequest(BaseModel):
    room_id: UUID
    token: Optional[str] = None


class JoinRoomResponse(BaseModel):
    session_id: UUID
    vivox_session_id: Optional[str] = None
    room_id: UUID
    message: str = "Successfully joined room"


class LeaveRoomResponse(BaseModel):
    message: str = "Successfully left room"
