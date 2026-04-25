import uuid
from enum import Enum

from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from src.database.database import Base


class UserRole(str, Enum):
    STUDENT = "student"
    TEACHER = "teacher"
    ADMIN = "admin"


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(100), nullable=False)
    role = Column(
        String(20),
        nullable=False,
        default=UserRole.STUDENT,
        index=True,
    )
    avatar_url = Column(String(500), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    is_verified = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    # Relationships
    room_memberships = relationship("RoomMember", back_populates="user", cascade="all, delete-orphan")
    created_rooms = relationship("Room", back_populates="created_by_user", cascade="all, delete-orphan")
    user_sessions = relationship("UserSession", back_populates="user", cascade="all, delete-orphan")
    messages = relationship("Message", back_populates="user", cascade="all, delete-orphan")
    room_join_tokens = relationship("RoomJoinToken", back_populates="user", cascade="all, delete-orphan")

    __table_args__ = (CheckConstraint("role IN ('student', 'teacher', 'admin')", name="check_user_role"),)

    def __repr__(self):
        return f"<User(id={self.id}, username={self.username}, email={self.email})>"
