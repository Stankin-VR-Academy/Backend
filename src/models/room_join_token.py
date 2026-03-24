import uuid

from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from src.database.database import Base


class RoomJoinToken(Base):
    __tablename__ = "room_join_tokens"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    room_id = Column(UUID(as_uuid=True), ForeignKey("rooms.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token = Column(String(255), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    max_uses = Column(Integer, nullable=False, default=1)
    uses_count = Column(Integer, nullable=False, default=0)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    # Relationships
    room = relationship("Room", back_populates="join_tokens")
    user = relationship("User", back_populates="room_join_tokens")

    __table_args__ = (
        CheckConstraint("max_uses > 0", name="check_token_max_uses"),
        CheckConstraint("uses_count >= 0", name="check_token_uses_count"),
    )

    def __repr__(self):
        return f"<RoomJoinToken(id={self.id}, room_id={self.room_id}, token={self.token})>"
