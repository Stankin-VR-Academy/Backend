from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Union
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class Vector3(BaseModel):
    """3D-вектор. Используется и для позиции, и для эйлеровых углов поворота (в градусах)."""

    x: float = 0.0
    y: float = 0.0
    z: float = 0.0


class Vector3Scale(BaseModel):
    """3D-вектор для масштаба объекта (по умолчанию 1.0 по всем осям)."""

    x: float = 1.0
    y: float = 1.0
    z: float = 1.0


class TransformPayload(BaseModel):
    """Полный transform игрока в VR-комнате."""

    position: Vector3 = Field(default_factory=Vector3)
    rotation: Vector3 = Field(default_factory=Vector3, description="Эйлеровы углы (rx, ry, rz) в градусах")
    client_ts: Optional[float] = Field(
        default=None,
        description="Таймстемп клиента в мс (для интерполяции/lag compensation)",
    )


class ObjectTransform(BaseModel):
    """Полный transform объекта в VR-комнате (с масштабом)."""

    position: Vector3 = Field(default_factory=Vector3)
    rotation: Vector3 = Field(default_factory=Vector3, description="Эйлеровы углы (rx, ry, rz) в градусах")
    scale: Vector3Scale = Field(default_factory=Vector3Scale)


class ParticipantState(BaseModel):
    """Состояние одного участника комнаты."""

    user_id: UUID
    username: Optional[str] = None
    transform: TransformPayload = Field(default_factory=TransformPayload)
    server_ts: float = Field(..., description="Серверный таймстемп последнего обновления (UNIX, секунды)")


class RoomObjectState(BaseModel):
    """Состояние одного объекта в VR-комнате."""

    object_id: UUID = Field(..., description="UUID объекта (генерируется сервером при spawn)")
    owner_user_id: UUID = Field(..., description="UUID пользователя, заспавнившего объект")
    prefab: str = Field(..., min_length=1, max_length=64, description="Имя префаба/ассета на стороне клиента")
    transform: ObjectTransform = Field(default_factory=ObjectTransform)
    data: Dict[str, Any] = Field(default_factory=dict, description="Произвольные кастомные данные объекта (цвет, текст, состояние)")
    ephemeral: bool = Field(default=False, description="Если true — объект автоматически удаляется при отключении владельца")
    server_ts: float = Field(..., description="Серверный таймстемп последнего обновления (UNIX, секунды)")


class IncomingMessageType(str, Enum):
    TRANSFORM = "transform"
    PING = "ping"
    REQUEST_SNAPSHOT = "request_snapshot"
    SPAWN_OBJECT = "spawn_object"
    TRANSFORM_OBJECT = "transform_object"
    DESTROY_OBJECT = "destroy_object"


class OutgoingMessageType(str, Enum):
    INIT = "init"
    JOIN = "join"
    LEAVE = "leave"
    TRANSFORM = "transform"
    SNAPSHOT = "snapshot"
    PONG = "pong"
    ERROR = "error"
    OBJECT_SPAWNED = "object_spawned"
    OBJECT_TRANSFORMED = "object_transformed"
    OBJECT_DESTROYED = "object_destroyed"


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


class IncomingSpawnObject(BaseModel):
    """Запрос на создание нового объекта в комнате.

    Сервер сам присваивает `object_id` (UUID) и широковещательно рассылает
    `object_spawned` всем участникам, включая отправителя — так клиент узнаёт
    финальный id объекта. Для корреляции запроса и ответа клиент может
    передать `client_request_id`.
    """

    type: Literal[IncomingMessageType.SPAWN_OBJECT] = IncomingMessageType.SPAWN_OBJECT
    prefab: str = Field(..., min_length=1, max_length=64)
    transform: ObjectTransform = Field(default_factory=ObjectTransform)
    data: Dict[str, Any] = Field(default_factory=dict)
    ephemeral: bool = False
    client_request_id: Optional[str] = Field(
        default=None,
        max_length=64,
        description="Опциональный ID запроса на стороне клиента — будет возвращён в object_spawned",
    )

    @field_validator("data")
    @classmethod
    def _validate_data_size(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        if len(v) > 32:
            raise ValueError("data has too many keys (max 32)")
        return v


class IncomingTransformObject(BaseModel):
    """Запрос на обновление transform существующего объекта."""

    type: Literal[IncomingMessageType.TRANSFORM_OBJECT] = IncomingMessageType.TRANSFORM_OBJECT
    object_id: UUID
    transform: ObjectTransform
    client_ts: Optional[float] = None


class IncomingDestroyObject(BaseModel):
    """Запрос на удаление объекта из комнаты."""

    type: Literal[IncomingMessageType.DESTROY_OBJECT] = IncomingMessageType.DESTROY_OBJECT
    object_id: UUID


IncomingMessage = Union[
    IncomingTransform,
    IncomingPing,
    IncomingSnapshotRequest,
    IncomingSpawnObject,
    IncomingTransformObject,
    IncomingDestroyObject,
]


class OutgoingInit(BaseModel):
    type: Literal[OutgoingMessageType.INIT] = OutgoingMessageType.INIT
    room_id: UUID
    self_user_id: UUID
    server_ts: float
    participants: List[ParticipantState]
    objects: List[RoomObjectState] = Field(default_factory=list)


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
    objects: List[RoomObjectState] = Field(default_factory=list)


class OutgoingPong(BaseModel):
    type: Literal[OutgoingMessageType.PONG] = OutgoingMessageType.PONG
    server_ts: float
    client_ts: Optional[float] = None


class OutgoingError(BaseModel):
    type: Literal[OutgoingMessageType.ERROR] = OutgoingMessageType.ERROR
    code: str
    message: str


class OutgoingObjectSpawned(BaseModel):
    """Событие создания объекта в комнате."""

    type: Literal[OutgoingMessageType.OBJECT_SPAWNED] = OutgoingMessageType.OBJECT_SPAWNED
    object_id: UUID
    owner_user_id: UUID
    prefab: str
    transform: ObjectTransform
    data: Dict[str, Any] = Field(default_factory=dict)
    ephemeral: bool = False
    server_ts: float
    client_request_id: Optional[str] = None


class OutgoingObjectTransformed(BaseModel):
    """Событие обновления transform объекта."""

    type: Literal[OutgoingMessageType.OBJECT_TRANSFORMED] = OutgoingMessageType.OBJECT_TRANSFORMED
    object_id: UUID
    by_user_id: UUID
    transform: ObjectTransform
    server_ts: float
    client_ts: Optional[float] = None


class OutgoingObjectDestroyed(BaseModel):
    """Событие удаления объекта из комнаты."""

    type: Literal[OutgoingMessageType.OBJECT_DESTROYED] = OutgoingMessageType.OBJECT_DESTROYED
    object_id: UUID
    by_user_id: UUID
    server_ts: float
    reason: str = Field(default="user_request", description="user_request | owner_disconnected | room_closed")
