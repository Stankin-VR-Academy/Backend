from typing import Any, List
from uuid import uuid4

from fastapi import APIRouter, Response, status

from core.logger import get_logger
from src.schemas.message import (
    MessageCreate,
    MessageDetailResponse,
    MessageResponse,
    MessageUpdate,
    RoomJoinTokenCreate,
    RoomJoinTokenResponse,
)

router = APIRouter()
logger = get_logger({"module": "chat"})


@router.get("/rooms/{room_id}/messages", response_model=List[MessageResponse])
async def list_messages(room_id: str, limit: int = 50, offset: int = 0) -> Any:
    """
    Получить список сообщений в комнате.

    **Заглушка:** Возвращает фиктивный список сообщений.
    """
    logger.info(f"List messages attempt, room_id: {room_id}")
    # TODO: Реализовать получение списка сообщений
    return [
        MessageResponse(
            id=uuid4(),
            room_id=uuid4(),
            user_id=uuid4(),
            content="Test message",
            message_type="text",
            reply_to_id=None,
            created_at="2024-01-15T10:30:00Z",
            updated_at="2024-01-15T10:30:00Z",
            is_edited=False,
        )
    ]


@router.post("/rooms/{room_id}/messages", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def create_message(room_id: str, message_data: MessageCreate) -> Any:
    """
    Создать новое сообщение в комнате.

    **Заглушка:** Возвращает фиктивные данные сообщения.
    """
    logger.info(f"Create message attempt, room_id: {room_id}")
    # TODO: Реализовать создание сообщения
    return MessageResponse(
        id=uuid4(),
        room_id=uuid4(),
        user_id=uuid4(),
        content=message_data.content,
        message_type=message_data.message_type,
        reply_to_id=message_data.reply_to_id,
        created_at="2024-01-15T10:30:00Z",
        updated_at="2024-01-15T10:30:00Z",
        is_edited=False,
    )


@router.get("/messages/{message_id}", response_model=MessageDetailResponse)
async def get_message(message_id: str) -> Any:
    """
    Получить информацию о сообщении.

    **Заглушка:** Возвращает фиктивные данные сообщения.
    """
    logger.info(f"Get message attempt: {message_id}")
    # TODO: Реализовать получение сообщения
    return MessageDetailResponse(
        id=uuid4(),
        room_id=uuid4(),
        user_id=uuid4(),
        content="Test message",
        message_type="text",
        reply_to_id=None,
        created_at="2024-01-15T10:30:00Z",
        updated_at="2024-01-15T10:30:00Z",
        is_edited=False,
        replies=[],
    )


@router.patch("/messages/{message_id}", response_model=MessageResponse)
async def update_message(message_id: str, message_data: MessageUpdate) -> Any:
    """
    Обновить сообщение.

    **Заглушка:** Возвращает обновленные фиктивные данные.
    """
    logger.info(f"Update message attempt: {message_id}")
    # TODO: Реализовать обновление сообщения
    return MessageResponse(
        id=uuid4(),
        room_id=uuid4(),
        user_id=uuid4(),
        content=message_data.content,
        message_type="text",
        reply_to_id=None,
        created_at="2024-01-15T10:30:00Z",
        updated_at="2024-01-15T10:30:00Z",
        is_edited=True,
    )


@router.delete("/messages/{message_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_message(message_id: str) -> Response:
    """
    Удалить сообщение.

    **Заглушка:** Возвращает успешный статус.
    """
    logger.info(f"Delete message attempt: {message_id}")
    # TODO: Реализовать удаление сообщения
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/rooms/{room_id}/tokens", response_model=RoomJoinTokenResponse, status_code=status.HTTP_201_CREATED)
async def create_join_token(room_id: str, token_data: RoomJoinTokenCreate) -> Any:
    """
    Создать токен для входа в комнату.

    **Заглушка:** Возвращает фиктивные данные токена.
    """
    logger.info(f"Create join token attempt, room_id: {room_id}")
    # TODO: Реализовать создание токена
    return RoomJoinTokenResponse(
        id=uuid4(),
        room_id=uuid4(),
        user_id=uuid4(),
        token="fake_token_" + str(uuid4()),
        expires_at=token_data.expires_at,
        max_uses=token_data.max_uses,
        uses_count=0,
        is_active=True,
        created_at="2024-01-15T10:30:00Z",
    )


@router.get("/tokens/{token_id}", response_model=RoomJoinTokenResponse)
async def get_join_token(token_id: str) -> Any:
    """
    Получить информацию о токене для входа.

    **Заглушка:** Возвращает фиктивные данные токена.
    """
    logger.info(f"Get join token attempt: {token_id}")
    # TODO: Реализовать получение токена
    return RoomJoinTokenResponse(
        id=uuid4(),
        room_id=uuid4(),
        user_id=uuid4(),
        token="fake_token_" + str(uuid4()),
        expires_at="2024-12-31T23:59:59Z",
        max_uses=1,
        uses_count=0,
        is_active=True,
        created_at="2024-01-15T10:30:00Z",
    )
