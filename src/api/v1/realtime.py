"""Realtime-синхронизация участников VR-комнаты по WebSocket.

Эндпоинт: ``GET /api/v1/ws/rooms/{room_id}?token=<JWT access token>``

Протокол сообщений (JSON UTF-8):

Клиент -> сервер:
- ``{"type": "transform", "position": {"x":..,"y":..,"z":..}, "rotation": {"x":..,"y":..,"z":..}, "client_ts": <ms>}``
- ``{"type": "ping", "client_ts": <ms>}``
- ``{"type": "request_snapshot"}``
- ``{"type": "spawn_object", "prefab": <str>, "transform": {...}, "data": {...}, "ephemeral": <bool>, "client_request_id": <str|null>}``
- ``{"type": "transform_object", "object_id": <uuid>, "transform": {...}, "client_ts": <ms|null>}``
- ``{"type": "destroy_object", "object_id": <uuid>}``

Сервер -> клиент:
- ``{"type": "init", "room_id": <uuid>, "self_user_id": <uuid>, "server_ts": <s>, "participants": [...], "objects": [...]}``
- ``{"type": "join", "user_id": <uuid>, "username": <str|null>, "server_ts": <s>, "transform": {...}}``
- ``{"type": "leave", "user_id": <uuid>, "server_ts": <s>}``
- ``{"type": "transform", "user_id": <uuid>, "position": {...}, "rotation": {...}, "server_ts": <s>, "client_ts": <ms|null>}``
- ``{"type": "snapshot", "server_ts": <s>, "participants": [...], "objects": [...]}``
- ``{"type": "pong", "server_ts": <s>, "client_ts": <ms|null>}``
- ``{"type": "object_spawned", "object_id": <uuid>, "owner_user_id": <uuid>, "prefab": <str>, "transform": {...}, "data": {...}, "ephemeral": <bool>, "server_ts": <s>, "client_request_id": <str|null>}``
- ``{"type": "object_transformed", "object_id": <uuid>, "by_user_id": <uuid>, "transform": {...}, "server_ts": <s>, "client_ts": <ms|null>}``
- ``{"type": "object_destroyed", "object_id": <uuid>, "by_user_id": <uuid>, "server_ts": <s>, "reason": <str>}``
- ``{"type": "error", "code": <str>, "message": <str>}``

Аутентификация выполняется через query-параметр ``token`` (JWT access token).
Соединение разрывается с кодом 4401, если токен отсутствует/невалиден,
с кодом 4404, если комната не найдена/неактивна, с 4400 при невалидном payload.
"""

import json
import time
from dataclasses import dataclass, field
from typing import Optional
from uuid import UUID

from authlib.jose import JoseError, jwt
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, ValidationError
from sqlalchemy import select

from core.config import settings
from core.logger import get_logger
from src.database.database import AsyncSessionLocal
from src.models.room import Room
from src.models.room_member import RoomMember, RoomMemberRole
from src.models.user import User
from src.schemas.sync import (
    IncomingDestroyObject,
    IncomingMessageType,
    IncomingPing,
    IncomingSnapshotRequest,
    IncomingSpawnObject,
    IncomingTransform,
    IncomingTransformObject,
    OutgoingError,
    OutgoingInit,
    OutgoingJoin,
    OutgoingLeave,
    OutgoingObjectDestroyed,
    OutgoingObjectSpawned,
    OutgoingObjectTransformed,
    OutgoingPong,
    OutgoingSnapshot,
    OutgoingTransform,
    TransformPayload,
)
from src.services.redis_client import redis_client
from src.services.room_sync import ObjectError, room_sync_manager

router = APIRouter()
logger = get_logger()

WS_CODE_UNAUTHORIZED = 4401
WS_CODE_NOT_FOUND = 4404
WS_CODE_BAD_REQUEST = 4400
WS_CODE_INTERNAL = 4500

TOKEN_BLACKLIST_PREFIX = "auth:blacklist"

TRANSFORM_LOG_EVERY_N = 300


@dataclass
class _SessionStats:
    """Счётчики и метрики одной WS-сессии для итогового логирования."""

    started_at: float = field(default_factory=time.time)
    bytes_received: int = 0
    bytes_sent: int = 0
    msg_in_total: int = 0
    msg_in_by_type: dict = field(default_factory=dict)
    msg_out_total: int = 0
    invalid_json_count: int = 0
    invalid_payload_count: int = 0
    unknown_type_count: int = 0
    first_transform_logged: bool = False

    def inc_in(self, msg_type: Optional[str], size: int) -> None:
        self.msg_in_total += 1
        self.bytes_received += size
        key = msg_type or "<unknown>"
        self.msg_in_by_type[key] = self.msg_in_by_type.get(key, 0) + 1


def _client_addr(websocket: WebSocket) -> str:
    client = websocket.client
    if client is None:
        return "?"
    return f"{client.host}:{client.port}"


class _RealtimeProtocolDoc(BaseModel):
    """Описание WebSocket-протокола realtime-синхронизации."""

    endpoint: str
    auth: str
    close_codes: dict[int, str]
    client_to_server: dict[str, dict]
    server_to_client: dict[str, dict]
    notes: list[str]


_REALTIME_DOC_DESCRIPTION = """\
**Это документация для WebSocket-эндпоинта `/api/v1/ws/rooms/{room_id}`.**

OpenAPI/Swagger не описывает WebSocket-протоколы (это ограничение спецификации
OpenAPI 3.x), поэтому здесь приведено текстовое описание.

### Подключение

```
ws(s)://<host>/api/v1/ws/rooms/{room_id}?token=<JWT access token>
```

`token` — обычный JWT access token, полученный через `/api/v1/auth/login`.

### Коды закрытия (4xxx — application-defined)

- `4400` — невалидный `room_id` или payload
- `4401` — нет токена / токен невалиден / отозван / пользователь не найден
- `4404` — комната не найдена или неактивна
- `4500` — внутренняя ошибка сервера
- `4000` — соединение заменено новым подключением того же пользователя

### Сообщения от клиента

- `transform` — обновление позиции и поворота игрока (отправляйте 30–90 раз/сек)
- `ping` — измерение RTT (сервер ответит `pong` с тем же `client_ts`)
- `request_snapshot` — запросить полное состояние всех участников и объектов
- `spawn_object` — создать объект в комнате; сервер вернёт `object_spawned` с `object_id`
- `transform_object` — обновить transform объекта (только владельцу или модератору)
- `destroy_object` — удалить объект (только владельцу или модератору)

### Сообщения от сервера

- `init` — отправляется один раз при подключении: список текущих участников и объектов
- `join` — другим клиентам, когда вошёл новый участник
- `leave` — другим клиентам при отключении
- `transform` — широковещательно; отправителю не дублируется
- `snapshot` — ответ на `request_snapshot` (участники + объекты)
- `pong` — ответ на `ping`
- `object_spawned` — рассылается ВСЕМ (включая отправителя `spawn_object`) с финальным `object_id`
- `object_transformed` — рассылается всем кроме автора (low-latency, у автора уже есть локальное состояние)
- `object_destroyed` — рассылается ВСЕМ; `reason` ∈ `user_request | owner_disconnected | room_closed`
- `error` — `{code, message}` при невалидном payload, нарушении прав или превышении лимитов

### Лимиты по объектам

- максимум 256 объектов на комнату
- максимум 32 объектов на пользователя
- объекты с `ephemeral: true` автоматически уничтожаются при отключении владельца
"""


_REALTIME_DOC_EXAMPLE = _RealtimeProtocolDoc(
    endpoint="ws(s)://<host>/api/v1/ws/rooms/{room_id}?token=<JWT>",
    auth="JWT access token via query parameter `token`",
    close_codes={
        4000: "Replaced by another connection of the same user",
        4400: "Invalid room_id or payload",
        4401: "Missing/invalid/revoked token or user not found",
        4404: "Room not found or inactive",
        4500: "Internal server error",
    },
    client_to_server={
        "transform": {
            "type": "transform",
            "position": {"x": 0.0, "y": 1.7, "z": 0.0},
            "rotation": {"x": 0.0, "y": 90.0, "z": 0.0},
            "client_ts": 1714680000123,
        },
        "ping": {"type": "ping", "client_ts": 1714680000123},
        "request_snapshot": {"type": "request_snapshot"},
        "spawn_object": {
            "type": "spawn_object",
            "prefab": "marker",
            "transform": {
                "position": {"x": 1.0, "y": 1.5, "z": -2.0},
                "rotation": {"x": 0.0, "y": 0.0, "z": 0.0},
                "scale": {"x": 1.0, "y": 1.0, "z": 1.0},
            },
            "data": {"color": "#ff0000"},
            "ephemeral": False,
            "client_request_id": "client-tmp-1",
        },
        "transform_object": {
            "type": "transform_object",
            "object_id": "44444444-4444-4444-4444-444444444444",
            "transform": {
                "position": {"x": 1.2, "y": 1.5, "z": -2.0},
                "rotation": {"x": 0.0, "y": 45.0, "z": 0.0},
                "scale": {"x": 1.0, "y": 1.0, "z": 1.0},
            },
            "client_ts": 1714680000600,
        },
        "destroy_object": {
            "type": "destroy_object",
            "object_id": "44444444-4444-4444-4444-444444444444",
        },
    },
    server_to_client={
        "init": {
            "type": "init",
            "room_id": "00000000-0000-0000-0000-000000000000",
            "self_user_id": "11111111-1111-1111-1111-111111111111",
            "server_ts": 1714680000.123,
            "participants": [
                {
                    "user_id": "22222222-2222-2222-2222-222222222222",
                    "username": "alice",
                    "transform": {
                        "position": {"x": 1.0, "y": 1.7, "z": -2.0},
                        "rotation": {"x": 0.0, "y": 180.0, "z": 0.0},
                        "client_ts": None,
                    },
                    "server_ts": 1714679999.500,
                }
            ],
            "objects": [
                {
                    "object_id": "44444444-4444-4444-4444-444444444444",
                    "owner_user_id": "22222222-2222-2222-2222-222222222222",
                    "prefab": "marker",
                    "transform": {
                        "position": {"x": 1.0, "y": 1.5, "z": -2.0},
                        "rotation": {"x": 0.0, "y": 0.0, "z": 0.0},
                        "scale": {"x": 1.0, "y": 1.0, "z": 1.0},
                    },
                    "data": {"color": "#ff0000"},
                    "ephemeral": False,
                    "server_ts": 1714679999.700,
                }
            ],
        },
        "join": {
            "type": "join",
            "user_id": "33333333-3333-3333-3333-333333333333",
            "username": "bob",
            "server_ts": 1714680000.500,
            "transform": {
                "position": {"x": 0.0, "y": 1.7, "z": 0.0},
                "rotation": {"x": 0.0, "y": 0.0, "z": 0.0},
                "client_ts": None,
            },
        },
        "leave": {
            "type": "leave",
            "user_id": "33333333-3333-3333-3333-333333333333",
            "server_ts": 1714680005.000,
        },
        "transform": {
            "type": "transform",
            "user_id": "22222222-2222-2222-2222-222222222222",
            "position": {"x": 1.2, "y": 1.7, "z": -2.0},
            "rotation": {"x": 0.0, "y": 175.0, "z": 0.0},
            "server_ts": 1714680000.700,
            "client_ts": 1714680000600,
        },
        "snapshot": {
            "type": "snapshot",
            "server_ts": 1714680000.800,
            "participants": [],
            "objects": [],
        },
        "pong": {
            "type": "pong",
            "server_ts": 1714680000.900,
            "client_ts": 1714680000123,
        },
        "object_spawned": {
            "type": "object_spawned",
            "object_id": "44444444-4444-4444-4444-444444444444",
            "owner_user_id": "22222222-2222-2222-2222-222222222222",
            "prefab": "marker",
            "transform": {
                "position": {"x": 1.0, "y": 1.5, "z": -2.0},
                "rotation": {"x": 0.0, "y": 0.0, "z": 0.0},
                "scale": {"x": 1.0, "y": 1.0, "z": 1.0},
            },
            "data": {"color": "#ff0000"},
            "ephemeral": False,
            "server_ts": 1714680001.000,
            "client_request_id": "client-tmp-1",
        },
        "object_transformed": {
            "type": "object_transformed",
            "object_id": "44444444-4444-4444-4444-444444444444",
            "by_user_id": "22222222-2222-2222-2222-222222222222",
            "transform": {
                "position": {"x": 1.2, "y": 1.5, "z": -2.0},
                "rotation": {"x": 0.0, "y": 45.0, "z": 0.0},
                "scale": {"x": 1.0, "y": 1.0, "z": 1.0},
            },
            "server_ts": 1714680001.300,
            "client_ts": 1714680000600,
        },
        "object_destroyed": {
            "type": "object_destroyed",
            "object_id": "44444444-4444-4444-4444-444444444444",
            "by_user_id": "22222222-2222-2222-2222-222222222222",
            "server_ts": 1714680002.000,
            "reason": "user_request",
        },
        "error": {"type": "error", "code": "invalid_json", "message": "Message is not valid JSON"},
    },
    notes=[
        "WebSocket endpoints are not part of OpenAPI; see this endpoint for protocol docs.",
        "transform messages should be sent at 30-90 Hz for VR.",
        "The server never echoes a player transform back to its sender.",
        "object_spawned is broadcast to ALL (including the spawner) so they get the assigned object_id.",
        "object_transformed is broadcast to ALL EXCEPT the actor (the actor already has local state).",
        "object_destroyed is broadcast to ALL (including the actor) as an authoritative ack.",
        "Only the object owner OR a room moderator (host/moderator) can transform/destroy an object.",
        "Objects with ephemeral=true are auto-destroyed when their owner disconnects.",
        "Limits: 256 objects per room, 32 objects per user.",
        "Reconnecting with the same user_id closes the previous connection (code 4000).",
        "For multi-worker deployments add a Redis pub/sub layer (currently single-process).",
    ],
)


@router.get(
    "/rooms/{room_id}/protocol",
    response_model=_RealtimeProtocolDoc,
    summary="Документация WebSocket-протокола VR realtime-синхронизации",
    description=_REALTIME_DOC_DESCRIPTION,
)
async def realtime_protocol_docs(room_id: str) -> _RealtimeProtocolDoc:
    """Возвращает описание WS-протокола (для отображения в Swagger)."""
    return _REALTIME_DOC_EXAMPLE


def _decode_access_token(token: str, logger) -> Optional[UUID]:
    """Декодирует JWT и возвращает user_id. None — если токен невалиден."""
    try:
        claims = jwt.decode(token, settings.SECRET_KEY)
        claims.validate()
    except JoseError as exc:
        logger.warning(f"WS auth: token decode failed: {exc.__class__.__name__}: {exc}")
        return None

    if claims.get("type") != "access":
        logger.warning(f"WS auth: token type is not access: type={claims.get('type')!r}")
        return None

    sub = claims.get("sub")
    if not sub:
        logger.warning("WS auth: token has no 'sub' claim")
        return None
    try:
        user_id = UUID(str(sub))
    except (ValueError, TypeError) as exc:
        logger.warning(f"WS auth: token 'sub' is not a UUID: sub={sub!r} error={exc}")
        return None

    logger.debug(f"WS auth: token decoded ok user_id={user_id} exp={claims.get('exp')} iat={claims.get('iat')}")
    return user_id


async def _is_token_revoked(token: str, logger) -> bool:
    if redis_client.redis is None:
        logger.debug("WS auth: Redis unavailable, skipping blacklist check")
        return False
    try:
        value = await redis_client.redis.get(f"{TOKEN_BLACKLIST_PREFIX}:{token}")
        return value is not None
    except Exception as exc:
        logger.warning(f"WS auth: Redis blacklist check failed (treating as not revoked): {exc}")
        return False


@router.websocket("/rooms/{room_id}")
async def ws_room_sync(websocket: WebSocket, room_id: str, token: Optional[str] = Query(default=None, description="JWT access token")) -> None:
    """WebSocket-синхронизация позиции и поворота игроков в VR-комнате."""
    client_addr = _client_addr(websocket)
    logger.info(f"WS connect attempt: client={client_addr} room_id={room_id} token_present={bool(token)} token_len={len(token) if token else 0}")

    if not token:
        logger.warning("WS auth rejected: missing access token")
        await websocket.close(code=WS_CODE_UNAUTHORIZED, reason="Missing access token")
        return

    if await _is_token_revoked(token, logger):
        logger.warning("WS auth rejected: token has been revoked")
        await websocket.close(code=WS_CODE_UNAUTHORIZED, reason="Token revoked")
        return

    user_id = _decode_access_token(token, logger)
    if user_id is None:
        logger.warning("WS auth rejected: invalid or expired token")
        await websocket.close(code=WS_CODE_UNAUTHORIZED, reason="Invalid or expired token")
        return

    try:
        normalized_room_id = UUID(room_id)
    except ValueError:
        logger.warning(f"WS rejected: invalid room_id format: room_id={room_id!r}")
        await websocket.close(code=WS_CODE_BAD_REQUEST, reason="Invalid room_id format")
        return

    username: Optional[str] = None
    is_moderator: bool = False
    try:
        async with AsyncSessionLocal() as db:
            logger.debug("WS lookup: querying room and user from DB")
            room_result = await db.execute(select(Room.id, Room.is_active, Room.created_by).where(Room.id == normalized_room_id))
            room_row = room_result.first()
            if room_row is None:
                logger.warning("WS rejected: room not found")
                await websocket.close(code=WS_CODE_NOT_FOUND, reason="Room not found")
                return
            if not room_row.is_active:
                logger.warning("WS rejected: room is inactive")
                await websocket.close(code=WS_CODE_NOT_FOUND, reason="Room is inactive")
                return

            user_result = await db.execute(select(User).where(User.id == user_id))
            user = user_result.scalar_one_or_none()
            if user is None:
                logger.warning("WS rejected: user from token not found in DB")
                await websocket.close(code=WS_CODE_UNAUTHORIZED, reason="User not found")
                return
            username = getattr(user, "username", None)

            if room_row.created_by == user_id:
                is_moderator = True
            else:
                member_result = await db.execute(
                    select(RoomMember.role).where(
                        RoomMember.room_id == normalized_room_id,
                        RoomMember.user_id == user_id,
                    )
                )
                role = member_result.scalar_one_or_none()
                if role in (RoomMemberRole.HOST.value, RoomMemberRole.MODERATOR.value):
                    is_moderator = True

            logger.debug(
                f"WS lookup ok: room exists & active, user found username={username!r} is_moderator={is_moderator}"
            )
    except Exception as exc:
        logger.exception(f"WS auth/db error: {exc}")
        try:
            await websocket.close(code=WS_CODE_INTERNAL, reason="Internal error")
        except Exception:
            pass
        return

    await websocket.accept()
    logger.info(f"WS handshake accepted: client={client_addr} username={username!r}")

    stats = _SessionStats()
    close_reason = "client_disconnect"

    try:
        self_state = await room_sync_manager.connect(
            room_id=normalized_room_id,
            user_id=user_id,
            websocket=websocket,
            username=username,
        )

        snapshot = await room_sync_manager.get_snapshot(normalized_room_id)
        objects_snapshot = await room_sync_manager.get_objects_snapshot(normalized_room_id)
        logger.debug(
            f"Sending init: participants_in_room={len(snapshot)} objects_in_room={len(objects_snapshot)}"
        )
        sent_init = await room_sync_manager.send_to_user(
            normalized_room_id,
            user_id,
            OutgoingInit(
                room_id=normalized_room_id,
                self_user_id=user_id,
                server_ts=time.time(),
                participants=snapshot,
                objects=objects_snapshot,
            ),
        )
        if sent_init:
            stats.msg_out_total += 1
        else:
            logger.warning("Failed to send init to user (will close)")

        logger.debug("Broadcasting join to other participants")
        join_recipients = await room_sync_manager.broadcast(
            normalized_room_id,
            OutgoingJoin(
                user_id=user_id,
                username=username,
                server_ts=self_state.server_ts,
                transform=self_state.transform,
            ),
            exclude=[user_id],
        )
        logger.info(f"WS join broadcast: recipients={join_recipients}")

        await _receive_loop(websocket, normalized_room_id, user_id, stats, is_moderator, logger)

    except WebSocketDisconnect as exc:
        close_reason = f"client_disconnect(code={exc.code})"
        logger.info(f"WS client disconnected: code={exc.code}")
    except Exception as exc:
        close_reason = f"server_exception({exc.__class__.__name__})"
        logger.exception(f"WS unexpected error: {exc}")
    finally:
        duration = max(time.time() - stats.started_at, 1e-6)
        avg_in_hz = stats.msg_in_total / duration
        logger.info(
            f"WS session ending: reason={close_reason} duration_s={duration:.3f} "
            f"msg_in={stats.msg_in_total} msg_out={stats.msg_out_total} "
            f"avg_in_hz={avg_in_hz:.2f} bytes_in={stats.bytes_received} "
            f"by_type={stats.msg_in_by_type} invalid_json={stats.invalid_json_count} "
            f"invalid_payload={stats.invalid_payload_count} unknown_type={stats.unknown_type_count}"
        )

        ephemeral_object_ids = await room_sync_manager.pop_ephemeral_objects(normalized_room_id, user_id)
        removed = await room_sync_manager.disconnect(normalized_room_id, user_id, websocket)
        if removed:
            for object_id in ephemeral_object_ids:
                ephemeral_recipients = await room_sync_manager.broadcast(
                    normalized_room_id,
                    OutgoingObjectDestroyed(
                        object_id=object_id,
                        by_user_id=user_id,
                        server_ts=time.time(),
                        reason="owner_disconnected",
                    ),
                )
                logger.info(
                    f"WS ephemeral object_destroyed broadcast: object_id={object_id} recipients={ephemeral_recipients}"
                )
            leave_recipients = await room_sync_manager.broadcast(
                normalized_room_id,
                OutgoingLeave(user_id=user_id, server_ts=time.time()),
            )
            logger.info(f"WS leave broadcast: recipients={leave_recipients}")
        else:
            logger.debug("WS leave broadcast skipped (already replaced/unregistered)")


async def _receive_loop(
    websocket: WebSocket,
    room_id: UUID,
    user_id: UUID,
    stats: _SessionStats,
    is_moderator: bool,
    logger,
) -> None:
    """Основной цикл чтения сообщений от клиента."""
    while True:
        raw = await websocket.receive_text()
        size = len(raw)

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            stats.invalid_json_count += 1
            stats.inc_in(None, size)
            logger.warning(f"Invalid JSON from client: size={size} error={exc} preview={raw[:120]!r}")
            sent = await room_sync_manager.send_to_user(
                room_id,
                user_id,
                OutgoingError(code="invalid_json", message="Message is not valid JSON"),
            )
            if sent:
                stats.msg_out_total += 1
            continue

        msg_type = data.get("type") if isinstance(data, dict) else None
        stats.inc_in(msg_type, size)

        if msg_type == IncomingMessageType.TRANSFORM.value:
            await _handle_transform(room_id, user_id, data, stats, logger)
        elif msg_type == IncomingMessageType.PING.value:
            await _handle_ping(room_id, user_id, data, stats, logger)
        elif msg_type == IncomingMessageType.REQUEST_SNAPSHOT.value:
            await _handle_snapshot_request(room_id, user_id, data, stats, logger)
        elif msg_type == IncomingMessageType.SPAWN_OBJECT.value:
            await _handle_spawn_object(room_id, user_id, data, stats, logger)
        elif msg_type == IncomingMessageType.TRANSFORM_OBJECT.value:
            await _handle_transform_object(room_id, user_id, data, stats, is_moderator, logger)
        elif msg_type == IncomingMessageType.DESTROY_OBJECT.value:
            await _handle_destroy_object(room_id, user_id, data, stats, is_moderator, logger)
        else:
            stats.unknown_type_count += 1
            logger.warning(
                f"Unknown message type from client: type={msg_type!r} keys={list(data.keys()) if isinstance(data, dict) else type(data).__name__}"
            )
            sent = await room_sync_manager.send_to_user(
                room_id,
                user_id,
                OutgoingError(code="unknown_type", message=f"Unknown message type: {msg_type!r}"),
            )
            if sent:
                stats.msg_out_total += 1


async def _handle_transform(room_id: UUID, user_id: UUID, data: dict, stats: _SessionStats, logger) -> None:
    try:
        msg = IncomingTransform.model_validate(data)
    except ValidationError as exc:
        stats.invalid_payload_count += 1
        logger.warning(f"Invalid transform payload: errors={exc.error_count()} first_error={exc.errors()[:1]}")
        sent = await room_sync_manager.send_to_user(
            room_id,
            user_id,
            OutgoingError(code="invalid_transform", message=str(exc.errors())[:512]),
        )
        if sent:
            stats.msg_out_total += 1
        return

    if not stats.first_transform_logged:
        stats.first_transform_logged = True
        logger.info(
            f"First transform received: pos=({msg.position.x:.3f},{msg.position.y:.3f},{msg.position.z:.3f}) "
            f"rot=({msg.rotation.x:.2f},{msg.rotation.y:.2f},{msg.rotation.z:.2f}) "
            f"client_ts={msg.client_ts}"
        )
    elif stats.msg_in_by_type.get("transform", 0) % TRANSFORM_LOG_EVERY_N == 0:
        logger.debug(
            f"Transform progress: count={stats.msg_in_by_type.get('transform')} pos=({msg.position.x:.2f},{msg.position.y:.2f},{msg.position.z:.2f})"
        )

    transform = TransformPayload(
        position=msg.position,
        rotation=msg.rotation,
        client_ts=msg.client_ts,
    )
    state = await room_sync_manager.update_transform(room_id, user_id, transform)
    if state is None:
        logger.warning("Transform dropped: participant state missing (race with disconnect?)")
        return

    recipients = await room_sync_manager.broadcast(
        room_id,
        OutgoingTransform(
            user_id=user_id,
            position=state.transform.position,
            rotation=state.transform.rotation,
            server_ts=state.server_ts,
            client_ts=msg.client_ts,
        ),
        exclude=[user_id],
    )
    stats.msg_out_total += recipients


async def _handle_ping(room_id: UUID, user_id: UUID, data: dict, stats: _SessionStats, logger) -> None:
    try:
        msg = IncomingPing.model_validate(data)
    except ValidationError:
        logger.debug("Malformed ping payload, replying with empty pong")
        msg = IncomingPing()
    sent = await room_sync_manager.send_to_user(room_id, user_id, OutgoingPong(server_ts=time.time(), client_ts=msg.client_ts))
    if sent:
        stats.msg_out_total += 1


async def _handle_snapshot_request(room_id: UUID, user_id: UUID, data: dict, stats: _SessionStats, logger) -> None:
    try:
        IncomingSnapshotRequest.model_validate(data)
    except ValidationError:
        pass
    snapshot = await room_sync_manager.get_snapshot(room_id)
    objects = await room_sync_manager.get_objects_snapshot(room_id)
    logger.info(f"Snapshot requested by user, participants={len(snapshot)} objects={len(objects)}")
    sent = await room_sync_manager.send_to_user(
        room_id,
        user_id,
        OutgoingSnapshot(server_ts=time.time(), participants=snapshot, objects=objects),
    )
    if sent:
        stats.msg_out_total += 1


async def _handle_spawn_object(
    room_id: UUID,
    user_id: UUID,
    data: dict,
    stats: _SessionStats,
    logger,
) -> None:
    try:
        msg = IncomingSpawnObject.model_validate(data)
    except ValidationError as exc:
        stats.invalid_payload_count += 1
        logger.warning(f"Invalid spawn_object payload: errors={exc.error_count()} first_error={exc.errors()[:1]}")
        sent = await room_sync_manager.send_to_user(
            room_id,
            user_id,
            OutgoingError(code="invalid_spawn_object", message=str(exc.errors())[:512]),
        )
        if sent:
            stats.msg_out_total += 1
        return

    try:
        result = await room_sync_manager.spawn_object(
            room_id=room_id,
            owner_user_id=user_id,
            prefab=msg.prefab,
            transform=msg.transform,
            data=msg.data,
            ephemeral=msg.ephemeral,
        )
    except ObjectError as exc:
        logger.warning(f"spawn_object rejected: code={exc.code} message={exc.message}")
        sent = await room_sync_manager.send_to_user(
            room_id,
            user_id,
            OutgoingError(code=exc.code, message=exc.message),
        )
        if sent:
            stats.msg_out_total += 1
        return

    state = result.state
    recipients = await room_sync_manager.broadcast(
        room_id,
        OutgoingObjectSpawned(
            object_id=state.object_id,
            owner_user_id=state.owner_user_id,
            prefab=state.prefab,
            transform=state.transform,
            data=state.data,
            ephemeral=state.ephemeral,
            server_ts=state.server_ts,
            client_request_id=msg.client_request_id,
        ),
    )
    stats.msg_out_total += recipients
    logger.info(
        f"Object spawned & broadcast: room_id={room_id} object_id={state.object_id} "
        f"owner={user_id} prefab={msg.prefab!r} ephemeral={msg.ephemeral} recipients={recipients}"
    )


async def _handle_transform_object(
    room_id: UUID,
    user_id: UUID,
    data: dict,
    stats: _SessionStats,
    is_moderator: bool,
    logger,
) -> None:
    try:
        msg = IncomingTransformObject.model_validate(data)
    except ValidationError as exc:
        stats.invalid_payload_count += 1
        logger.warning(f"Invalid transform_object payload: errors={exc.error_count()} first_error={exc.errors()[:1]}")
        sent = await room_sync_manager.send_to_user(
            room_id,
            user_id,
            OutgoingError(code="invalid_transform_object", message=str(exc.errors())[:512]),
        )
        if sent:
            stats.msg_out_total += 1
        return

    try:
        result = await room_sync_manager.transform_object(
            room_id=room_id,
            object_id=msg.object_id,
            actor_user_id=user_id,
            transform=msg.transform,
            actor_is_moderator=is_moderator,
        )
    except ObjectError as exc:
        logger.warning(f"transform_object rejected: code={exc.code} message={exc.message}")
        sent = await room_sync_manager.send_to_user(
            room_id,
            user_id,
            OutgoingError(code=exc.code, message=exc.message),
        )
        if sent:
            stats.msg_out_total += 1
        return

    state = result.state
    recipients = await room_sync_manager.broadcast(
        room_id,
        OutgoingObjectTransformed(
            object_id=state.object_id,
            by_user_id=user_id,
            transform=state.transform,
            server_ts=state.server_ts,
            client_ts=msg.client_ts,
        ),
        exclude=[user_id],
    )
    stats.msg_out_total += recipients


async def _handle_destroy_object(
    room_id: UUID,
    user_id: UUID,
    data: dict,
    stats: _SessionStats,
    is_moderator: bool,
    logger,
) -> None:
    try:
        msg = IncomingDestroyObject.model_validate(data)
    except ValidationError as exc:
        stats.invalid_payload_count += 1
        logger.warning(f"Invalid destroy_object payload: errors={exc.error_count()} first_error={exc.errors()[:1]}")
        sent = await room_sync_manager.send_to_user(
            room_id,
            user_id,
            OutgoingError(code="invalid_destroy_object", message=str(exc.errors())[:512]),
        )
        if sent:
            stats.msg_out_total += 1
        return

    try:
        snapshot = await room_sync_manager.destroy_object(
            room_id=room_id,
            object_id=msg.object_id,
            actor_user_id=user_id,
            actor_is_moderator=is_moderator,
        )
    except ObjectError as exc:
        logger.warning(f"destroy_object rejected: code={exc.code} message={exc.message}")
        sent = await room_sync_manager.send_to_user(
            room_id,
            user_id,
            OutgoingError(code=exc.code, message=exc.message),
        )
        if sent:
            stats.msg_out_total += 1
        return

    recipients = await room_sync_manager.broadcast(
        room_id,
        OutgoingObjectDestroyed(
            object_id=snapshot.object_id,
            by_user_id=user_id,
            server_ts=time.time(),
            reason="user_request",
        ),
    )
    stats.msg_out_total += recipients
    logger.info(
        f"Object destroyed & broadcast: room_id={room_id} object_id={snapshot.object_id} "
        f"by_user={user_id} recipients={recipients}"
    )
