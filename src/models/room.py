import uuid
from enum import Enum

from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from src.database.database import Base


class RoomType(str, Enum):
    CLASSROOM = "classroom"
    LOBBY = "lobby"
    PRIVATE = "private"
    VOICE_ONLY = "voice_only"


class Room(Base):
    __tablename__ = "rooms"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    room_type = Column(String(20), nullable=False, default=RoomType.CLASSROOM, index=True)
    max_participants = Column(Integer, nullable=False, default=30)
    is_voice_enabled = Column(Boolean, nullable=False, default=True)
    is_text_enabled = Column(Boolean, nullable=False, default=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=False, index=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    # Relationships
    created_by_user = relationship("User", back_populates="created_rooms")
    members = relationship("RoomMember", back_populates="room", cascade="all, delete-orphan")
    user_sessions = relationship("UserSession", back_populates="room", cascade="all, delete-orphan")
    messages = relationship("Message", back_populates="room", cascade="all, delete-orphan")
    join_tokens = relationship("RoomJoinToken", back_populates="room", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint("max_participants > 0", name="check_room_max_participants"),
        CheckConstraint("room_type IN ('classroom', 'lobby', 'private', 'voice_only')", name="check_room_type"),
    )

    def __repr__(self):
        return f"<Room(id={self.id}, name={self.name})>"
