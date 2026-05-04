from enum import Enum
from typing import List, Literal, Optional, Union
from uuid import UUID

from pydantic import BaseModel, Field


class Vector3(BaseModel):
    """3D-вектор. Используется и для позиции, и для эйлеровых углов поворота (в градусах)."""

    x: float = 0.0
    y: float = 0.0
    z: float = 0.0


class TransformPayload(BaseModel):
    """Полный transform игрока в VR-комнате."""

    position: Vector3 = Field(default_factory=Vector3)
    rotation: Vector3 = Field(default_factory=Vector3, description="Эйлеровы углы (rx, ry, rz) в градусах")
    client_ts: Optional[float] = Field(
        default=None,
        description="Таймстемп клиента в мс (для интерполяции/lag compensation)",
    )


class ParticipantState(BaseModel):
    """Состояние одного участника комнаты."""

    user_id: UUID
    username: Optional[str] = None
    transform: TransformPayload = Field(default_factory=TransformPayload)
    server_ts: float = Field(..., description="Серверный таймстемп последнего обновления (UNIX, секунды)")


class IncomingMessageType(str, Enum):
    TRANSFORM = "transform"
    PING = "ping"
    REQUEST_SNAPSHOT = "request_snapshot"


class OutgoingMessageType(str, Enum):
    INIT = "init"
    JOIN = "join"
    LEAVE = "leave"
    TRANSFORM = "transform"
    SNAPSHOT = "snapshot"
    PONG = "pong"
    ERROR = "error"


class IncomingTransform(BaseModel):
    type: Literal[IncomingMessageType.TRANSFORM] = IncomingMessageType.TRANSFORM
    position: Vector3
    rotation: Vector3
    client_ts: Optional[float] = None


class IncomingPing(BaseModel):
    type: Literal[IncomingMessageType.PING] = IncomingMessageType.PING
    client_ts: Optional[float] = None


class IncomingSnapshotRequest(BaseModel):
    type: Literal[IncomingMessageType.REQUEST_SNAPSHOT] = IncomingMessageType.REQUEST_SNAPSHOT


IncomingMessage = Union[IncomingTransform, IncomingPing, IncomingSnapshotRequest]


class OutgoingInit(BaseModel):
    type: Literal[OutgoingMessageType.INIT] = OutgoingMessageType.INIT
    room_id: UUID
    self_user_id: UUID
    server_ts: float
    participants: List[ParticipantState]


class OutgoingJoin(BaseModel):
    type: Literal[OutgoingMessageType.JOIN] = OutgoingMessageType.JOIN
    user_id: UUID
    username: Optional[str] = None
    server_ts: float
    transform: TransformPayload = Field(default_factory=TransformPayload)


class OutgoingLeave(BaseModel):
    type: Literal[OutgoingMessageType.LEAVE] = OutgoingMessageType.LEAVE
    user_id: UUID
    server_ts: float


class OutgoingTransform(BaseModel):
    type: Literal[OutgoingMessageType.TRANSFORM] = OutgoingMessageType.TRANSFORM
    user_id: UUID
    position: Vector3
    rotation: Vector3
    server_ts: float
    client_ts: Optional[float] = None


class OutgoingSnapshot(BaseModel):
    type: Literal[OutgoingMessageType.SNAPSHOT] = OutgoingMessageType.SNAPSHOT
    server_ts: float
    participants: List[ParticipantState]


class OutgoingPong(BaseModel):
    type: Literal[OutgoingMessageType.PONG] = OutgoingMessageType.PONG
    server_ts: float
    client_ts: Optional[float] = None


class OutgoingError(BaseModel):
    type: Literal[OutgoingMessageType.ERROR] = OutgoingMessageType.ERROR
    code: str
    message: str
