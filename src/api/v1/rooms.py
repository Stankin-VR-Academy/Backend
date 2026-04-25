from typing import Any, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.logger import get_logger
from src.database.database import get_db
from src.models.room import Room
from src.models.room_member import RoomMember
from src.models.user import User
from src.models.user_session import UserSession
from src.schemas.room import (
    RoomCreate,
    RoomDetailResponse,
    RoomMemberResponse,
    RoomMemberUpdate,
    RoomResponse,
    RoomUpdate,
)
from src.services.auth import get_current_user

router = APIRouter()
logger = get_logger({"module": "rooms"})


@router.get("", response_model=List[RoomResponse])
async def list_rooms(
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Получить список комнат.

    Возвращает список комнат.
    """
    logger.info("List rooms attempt")
    query = select(Room).order_by(Room.created_at.desc())

    result = await db.execute(query)
    return result.scalars().all()


@router.post("", response_model=RoomResponse, status_code=status.HTTP_201_CREATED)
async def create_room(
    room_data: RoomCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Создать новую комнату.

    Создать новую комнату.
    """
    logger.info(f"Create room attempt: {room_data.name}")
    room = Room(
        name=room_data.name,
        description=room_data.description,
        room_type=room_data.room_type,
        max_participants=room_data.max_participants,
        is_voice_enabled=room_data.is_voice_enabled,
        is_text_enabled=room_data.is_text_enabled,
        created_by=current_user.id,
    )
    db.add(room)
    try:
        await db.commit()
        await db.refresh(room)
    except IntegrityError as error:
        await db.rollback()
        logger.warning(f"Create room integrity error: {error}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid room payload",
        ) from error
    except SQLAlchemyError as error:
        await db.rollback()
        logger.exception(f"Create room db error: {error}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not create room",
        ) from error
    return room


@router.get("/{room_id}", response_model=RoomDetailResponse)
async def get_room(room_id: str, db: AsyncSession = Depends(get_db)) -> Any:
    """
    Получить информацию о комнате.

    Получить детальную информацию о комнате.
    """
    logger.info(f"Get room attempt: {room_id}")
    try:
        normalized_room_id = UUID(room_id)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid room_id format") from error

    room_result = await db.execute(
        select(Room)
        .options(selectinload(Room.created_by_user))
        .where(Room.id == normalized_room_id)
    )
    room = room_result.scalar_one_or_none()
    if not room:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Room not found")

    participant_count_result = await db.execute(
        select(func.count(RoomMember.id)).where(RoomMember.room_id == room.id)
    )
    active_session_count_result = await db.execute(
        select(func.count(UserSession.id)).where(
            UserSession.room_id == room.id,
            UserSession.ended_at.is_(None),
        )
    )

    return RoomDetailResponse(
        **RoomResponse.model_validate(room).model_dump(),
        created_by_user=room.created_by_user,
        participant_count=participant_count_result.scalar_one(),
        active_session_count=active_session_count_result.scalar_one(),
    )


@router.patch("/{room_id}", response_model=RoomResponse)
async def update_room(
    room_id: str,
    room_data: RoomUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Обновить информацию о комнате.

    Обновить информацию о комнате.
    """
    logger.info(f"Update room attempt: {room_id}")
    try:
        normalized_room_id = UUID(room_id)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid room_id format") from error

    room_result = await db.execute(select(Room).where(Room.id == normalized_room_id))
    room = room_result.scalar_one_or_none()
    if not room:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Room not found")
    if room.created_by != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

    update_data = room_data.model_dump(exclude_unset=True)
    for field_name, field_value in update_data.items():
        setattr(room, field_name, field_value)

    try:
        await db.commit()
        await db.refresh(room)
    except IntegrityError as error:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid room payload") from error
    except SQLAlchemyError as error:
        await db.rollback()
        logger.exception(f"Update room db error: {error}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not update room") from error

    return room


@router.delete("/{room_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_room(
    room_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """
    Удалить комнату.

    Удалить комнату.
    """
    logger.info(f"Delete room attempt: {room_id}")
    try:
        normalized_room_id = UUID(room_id)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid room_id format") from error

    room_result = await db.execute(select(Room).where(Room.id == normalized_room_id))
    room = room_result.scalar_one_or_none()
    if not room:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Room not found")
    if room.created_by != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

    await db.delete(room)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{room_id}/members", response_model=List[RoomMemberResponse])
async def list_room_members(room_id: str, db: AsyncSession = Depends(get_db)) -> Any:
    """
    Получить список участников комнаты.

    Получить список участников комнаты.
    """
    logger.info(f"List room members attempt: {room_id}")
    try:
        normalized_room_id = UUID(room_id)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid room_id format") from error

    room_exists_result = await db.execute(select(Room.id).where(Room.id == normalized_room_id))
    if room_exists_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Room not found")

    members_result = await db.execute(
        select(RoomMember).where(RoomMember.room_id == normalized_room_id).order_by(RoomMember.joined_at.asc())
    )
    return members_result.scalars().all()


@router.post("/{room_id}/members/{user_id}", response_model=RoomMemberResponse, status_code=status.HTTP_201_CREATED)
async def add_room_member(
    room_id: str,
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Добавить участника в комнату.

    Добавить участника в комнату.
    """
    logger.info(f"Add room member attempt: {room_id}, {user_id}")
    try:
        normalized_room_id = UUID(room_id)
        normalized_user_id = UUID(user_id)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid room_id or user_id format") from error

    room_result = await db.execute(select(Room).where(Room.id == normalized_room_id))
    room = room_result.scalar_one_or_none()
    if not room:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Room not found")
    if room.created_by != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

    user_result = await db.execute(select(User.id).where(User.id == normalized_user_id))
    if user_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    existing_member_result = await db.execute(
        select(RoomMember).where(
            RoomMember.room_id == normalized_room_id,
            RoomMember.user_id == normalized_user_id,
        )
    )
    existing_member = existing_member_result.scalar_one_or_none()
    if existing_member:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User already in room")

    member = RoomMember(room_id=normalized_room_id, user_id=normalized_user_id, role="participant")
    db.add(member)
    try:
        await db.commit()
        await db.refresh(member)
    except IntegrityError as error:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Could not add room member") from error
    return member


@router.patch("/{room_id}/members/{user_id}", response_model=RoomMemberResponse)
async def update_room_member(
    room_id: str,
    user_id: str,
    member_data: RoomMemberUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Обновить роль участника комнаты.

    Обновить роль участника комнаты.
    """
    logger.info(f"Update room member attempt: {room_id}, {user_id}")
    try:
        normalized_room_id = UUID(room_id)
        normalized_user_id = UUID(user_id)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid room_id or user_id format") from error

    room_result = await db.execute(select(Room).where(Room.id == normalized_room_id))
    room = room_result.scalar_one_or_none()
    if not room:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Room not found")
    if room.created_by != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

    member_result = await db.execute(
        select(RoomMember).where(
            RoomMember.room_id == normalized_room_id,
            RoomMember.user_id == normalized_user_id,
        )
    )
    member = member_result.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Room member not found")

    member.role = member_data.role
    try:
        await db.commit()
        await db.refresh(member)
    except IntegrityError as error:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid member role") from error
    return member


@router.delete("/{room_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_room_member(
    room_id: str,
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Удалить участника из комнаты."""
    logger.info(f"Remove room member attempt: {room_id}, {user_id}")
    try:
        normalized_room_id = UUID(room_id)
        normalized_user_id = UUID(user_id)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid room_id or user_id format") from error

    room_result = await db.execute(select(Room).where(Room.id == normalized_room_id))
    room = room_result.scalar_one_or_none()
    if not room:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Room not found")
    if room.created_by != current_user.id and normalized_user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

    member_result = await db.execute(
        select(RoomMember).where(
            RoomMember.room_id == normalized_room_id,
            RoomMember.user_id == normalized_user_id,
        )
    )
    member = member_result.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Room member not found")

    await db.delete(member)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
