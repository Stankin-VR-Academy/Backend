"""Менеджер WebSocket-соединений для синхронизации участников VR-комнаты.

В памяти процесса хранит:
- активные WebSocket-соединения, сгруппированные по `room_id`;
- последнее известное состояние (transform) каждого участника комнаты.

Поддерживает многопользовательскую трансляцию: при получении нового
состояния от одного клиента сообщение мгновенно рассылается остальным
участникам той же комнаты, а отправитель его обратно не получает.

Менеджер ориентирован на низкую задержку (важно для VR ~60–90 Гц), поэтому
не использует Redis pub/sub. Для горизонтального масштабирования на
несколько процессов потребуется добавить шину сообщений (TODO).
"""

import asyncio
import time
from typing import Dict, Iterable, List, Optional
from uuid import UUID

from fastapi import WebSocket
from pydantic import BaseModel

from core.logger import get_logger
from src.schemas.sync import ParticipantState, TransformPayload

logger = get_logger()


class _RoomState:
    """Состояние одной комнаты: соединения + последний transform каждого участника."""

    __slots__ = ("connections", "participants", "lock")

    def __init__(self) -> None:
        self.connections: Dict[UUID, WebSocket] = {}
        self.participants: Dict[UUID, ParticipantState] = {}
        self.lock = asyncio.Lock()


class RoomSyncManager:
    """Глобальный менеджер всех VR-комнат для процесса."""

    def __init__(self) -> None:
        self._rooms: Dict[UUID, _RoomState] = {}
        self._global_lock = asyncio.Lock()

    def total_rooms(self) -> int:
        return len(self._rooms)

    def total_connections(self) -> int:
        return sum(len(r.connections) for r in self._rooms.values())

    async def _get_or_create_room(self, room_id: UUID) -> _RoomState:
        async with self._global_lock:
            room = self._rooms.get(room_id)
            if room is None:
                room = _RoomState()
                self._rooms[room_id] = room
                logger.info(f"Room created in sync manager: room_id={room_id} total_rooms={len(self._rooms)}")
            return room

    async def connect(
        self,
        room_id: UUID,
        user_id: UUID,
        websocket: WebSocket,
        username: Optional[str] = None,
    ) -> ParticipantState:
        """Зарегистрировать соединение участника. Возвращает его начальное состояние.

        Если у участника уже было состояние (например, переподключение), оно
        сохраняется. Иначе создаётся новое со стандартным (нулевым) transform.
        """
        room = await self._get_or_create_room(room_id)
        now = time.time()
        async with room.lock:
            previous_ws = room.connections.get(user_id)
            room.connections[user_id] = websocket

            existing_state = room.participants.get(user_id)
            if existing_state is None:
                state = ParticipantState(
                    user_id=user_id,
                    username=username,
                    transform=TransformPayload(),
                    server_ts=now,
                )
                room.participants[user_id] = state
                is_reconnect = False
            else:
                if username and existing_state.username != username:
                    logger.debug(
                        f"Updating username on reconnect: room_id={room_id} user_id={user_id} old={existing_state.username!r} new={username!r}"
                    )
                    existing_state.username = username
                state = existing_state
                is_reconnect = True

            room_size = len(room.connections)

        if previous_ws is not None and previous_ws is not websocket:
            logger.warning(f"Closing previous WS for user (replaced by new connection): room_id={room_id} user_id={user_id}")
            try:
                await previous_ws.close(code=4000, reason="Replaced by another connection")
            except Exception as exc:
                logger.debug(f"Failed to close previous ws: room_id={room_id} user_id={user_id} error={exc}")

        logger.info(f"WS member registered: room_id={room_id} user_id={user_id} username={username!r} reconnect={is_reconnect} room_size={room_size}")
        return state

    async def disconnect(self, room_id: UUID, user_id: UUID, websocket: WebSocket) -> bool:
        """Удалить соединение участника. Возвращает True, если участник был удалён.

        Удаление произойдёт только если зарегистрированное соединение совпадает
        с переданным (защита от удаления нового соединения после переподключения).
        """
        room = self._rooms.get(room_id)
        if room is None:
            logger.debug(f"Disconnect for unknown room (already cleaned up): room_id={room_id} user_id={user_id}")
            return False
        async with room.lock:
            current = room.connections.get(user_id)
            if current is not websocket:
                logger.debug(f"Disconnect skipped (ws was already replaced): room_id={room_id} user_id={user_id}")
                return False
            room.connections.pop(user_id, None)
            room.participants.pop(user_id, None)
            room_empty = not room.connections
            room_size = len(room.connections)
        if room_empty:
            async with self._global_lock:
                if not room.connections:
                    self._rooms.pop(room_id, None)
                    logger.info(f"Room removed from sync manager (empty): room_id={room_id} total_rooms={len(self._rooms)}")
        logger.info(f"WS member unregistered: room_id={room_id} user_id={user_id} room_size={room_size}")
        return True

    async def update_transform(
        self,
        room_id: UUID,
        user_id: UUID,
        transform: TransformPayload,
    ) -> Optional[ParticipantState]:
        """Сохранить новое состояние участника и вернуть обновлённый ParticipantState."""
        room = self._rooms.get(room_id)
        if room is None:
            logger.debug(f"update_transform: room not found: room_id={room_id} user_id={user_id}")
            return None
        now = time.time()
        async with room.lock:
            state = room.participants.get(user_id)
            if state is None:
                logger.debug(f"update_transform: participant not found: room_id={room_id} user_id={user_id}")
                return None
            state.transform = transform
            state.server_ts = now
            return state

    async def get_snapshot(self, room_id: UUID) -> List[ParticipantState]:
        """Получить копию состояний всех участников комнаты."""
        room = self._rooms.get(room_id)
        if room is None:
            return []
        async with room.lock:
            snapshot = [s.model_copy(deep=True) for s in room.participants.values()]
        logger.debug(f"Snapshot built: room_id={room_id} participants={len(snapshot)}")
        return snapshot

    async def _send_to(self, websocket: WebSocket, message: BaseModel) -> bool:
        try:
            await websocket.send_text(message.model_dump_json())
            return True
        except Exception as exc:
            logger.debug(f"WS send failed: {exc}")
            return False

    async def send_to_user(self, room_id: UUID, user_id: UUID, message: BaseModel) -> bool:
        """Отправить сообщение конкретному участнику комнаты."""
        room = self._rooms.get(room_id)
        if room is None:
            logger.debug(f"send_to_user: room not found: room_id={room_id} user_id={user_id}")
            return False
        websocket = room.connections.get(user_id)
        if websocket is None:
            logger.debug(f"send_to_user: ws not found: room_id={room_id} user_id={user_id}")
            return False
        ok = await self._send_to(websocket, message)
        if not ok:
            logger.warning(
                f"send_to_user: send failed, will rely on disconnect cleanup: "
                f"room_id={room_id} user_id={user_id} type={getattr(message, 'type', '?')}"
            )
        return ok

    async def broadcast(
        self,
        room_id: UUID,
        message: BaseModel,
        exclude: Optional[Iterable[UUID]] = None,
    ) -> int:
        """Разослать сообщение всем участникам комнаты, кроме `exclude`.

        Возвращает количество успешных отправок. Соединения, упавшие при
        отправке, помечаются для последующего удаления.
        """
        room = self._rooms.get(room_id)
        if room is None:
            logger.debug(f"broadcast: room not found: room_id={room_id}")
            return 0

        excluded = set(exclude) if exclude else set()
        async with room.lock:
            targets = [(uid, ws) for uid, ws in room.connections.items() if uid not in excluded]

        msg_type = getattr(message, "type", "?")
        if not targets:
            logger.debug(f"broadcast: no recipients: room_id={room_id} type={msg_type} excluded={len(excluded)}")
            return 0

        payload = message.model_dump_json()
        results = await asyncio.gather(
            *(self._safe_send_text(ws, payload) for _, ws in targets),
            return_exceptions=False,
        )

        dead_users: List[UUID] = [uid for (uid, _), ok in zip(targets, results) if not ok]
        sent = sum(1 for ok in results if ok)

        if dead_users:
            async with room.lock:
                for uid in dead_users:
                    room.connections.pop(uid, None)
                    room.participants.pop(uid, None)
            logger.warning(
                f"broadcast: removed dead connections: room_id={room_id} type={msg_type} "
                f"dead={len(dead_users)} dead_users={[str(u) for u in dead_users]}"
            )

        logger.debug(f"broadcast done: room_id={room_id} type={msg_type} sent={sent} dead={len(dead_users)} excluded={len(excluded)}")
        return sent

    @staticmethod
    async def _safe_send_text(websocket: WebSocket, text: str) -> bool:
        try:
            await websocket.send_text(text)
            return True
        except Exception:
            return False


room_sync_manager = RoomSyncManager()
