from typing import Any, List
from uuid import uuid4

from fastapi import APIRouter

from core.logger import get_logger
from src.schemas.session import (
    JoinRoomRequest,
    JoinRoomResponse,
    LeaveRoomResponse,
    UserSessionResponse,
    UserSessionUpdate,
)

router = APIRouter()
logger = get_logger({"module": "sessions"})


@router.post("/join", response_model=JoinRoomResponse)
async def join_room(join_data: JoinRoomRequest) -> Any:
    """
    Присоединиться к комнате.

    **Заглушка:** Возвращает фиктивные данные сессии.
    """
    logger.info(f"Join room attempt: {join_data.room_id}")
    # TODO: Реализовать присоединение к комнате
    return JoinRoomResponse(
        session_id=uuid4(),
        vivox_session_id="fake_vivox_session_" + str(uuid4()),
        room_id=join_data.room_id,
        message="Successfully joined room",
    )


@router.post("/leave", response_model=LeaveRoomResponse)
async def leave_room(room_id: str) -> Any:
    """
    Покинуть комнату.

    **Заглушка:** Возвращает успешное сообщение.
    """
    logger.info(f"Leave room attempt: {room_id}")
    # TODO: Реализовать выход из комнаты
    return LeaveRoomResponse(message="Successfully left room")


@router.get("", response_model=List[UserSessionResponse])
async def list_sessions(room_id: str = None) -> Any:
    """
    Получить список активных сессий.

    **Заглушка:** Возвращает фиктивный список сессий.
    """
    logger.info(f"List sessions attempt, room_id: {room_id}")
    # TODO: Реализовать получение списка сессий
    return [
        UserSessionResponse(
            id=uuid4(),
            user_id=uuid4(),
            room_id=uuid4(),
            vivox_session_id="fake_vivox_session_" + str(uuid4()),
            position_x=0.0,
            position_y=0.0,
            position_z=0.0,
            rotation_x=0.0,
            rotation_y=0.0,
            rotation_z=0.0,
            is_muted=False,
            is_deafened=False,
            started_at="2024-01-15T10:30:00Z",
            last_active_at="2024-01-15T10:30:00Z",
            ended_at=None,
        )
    ]


@router.get("/{session_id}", response_model=UserSessionResponse)
async def get_session(session_id: str) -> Any:
    """
    Получить информацию о сессии.

    **Заглушка:** Возвращает фиктивные данные сессии.
    """
    logger.info(f"Get session attempt: {session_id}")
    # TODO: Реализовать получение сессии
    return UserSessionResponse(
        id=uuid4(),
        user_id=uuid4(),
        room_id=uuid4(),
        vivox_session_id="fake_vivox_session_" + str(uuid4()),
        position_x=0.0,
        position_y=0.0,
        position_z=0.0,
        rotation_x=0.0,
        rotation_y=0.0,
        rotation_z=0.0,
        is_muted=False,
        is_deafened=False,
        started_at="2024-01-15T10:30:00Z",
        last_active_at="2024-01-15T10:30:00Z",
        ended_at=None,
    )


@router.patch("/{session_id}", response_model=UserSessionResponse)
async def update_session(session_id: str, session_data: UserSessionUpdate) -> Any:
    """
    Обновить информацию о сессии (позиция, состояние микрофона и т.д.).

    **Заглушка:** Возвращает обновленные фиктивные данные.
    """
    logger.info(f"Update session attempt: {session_id}")
    # TODO: Реализовать обновление сессии
    return UserSessionResponse(
        id=uuid4(),
        user_id=uuid4(),
        room_id=uuid4(),
        vivox_session_id="fake_vivox_session_" + str(uuid4()),
        position_x=session_data.position_x or 0.0,
        position_y=session_data.position_y or 0.0,
        position_z=session_data.position_z or 0.0,
        rotation_x=session_data.rotation_x or 0.0,
        rotation_y=session_data.rotation_y or 0.0,
        rotation_z=session_data.rotation_z or 0.0,
        is_muted=session_data.is_muted if session_data.is_muted is not None else False,
        is_deafened=session_data.is_deafened if session_data.is_deafened is not None else False,
        started_at="2024-01-15T10:30:00Z",
        last_active_at="2024-01-15T10:30:00Z",
        ended_at=None,
    )
