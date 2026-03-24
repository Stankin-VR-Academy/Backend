import uuid
from enum import Enum

from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from src.database.database import Base


class ServerMemberRole(str, Enum):
    OWNER = "owner"
    ADMIN = "admin"
    MODERATOR = "moderator"
    MEMBER = "member"


class ServerMember(Base):
    __tablename__ = "server_members"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    server_id = Column(UUID(as_uuid=True), ForeignKey("servers.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(20), nullable=False, default=ServerMemberRole.MEMBER)
    joined_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    # Relationships
    server = relationship("Server", back_populates="members")
    user = relationship("User", back_populates="server_memberships")

    __table_args__ = (
        UniqueConstraint("server_id", "user_id", name="uq_server_member"),
        CheckConstraint("role IN ('owner', 'admin', 'moderator', 'member')", name="check_server_member_role"),
    )

    def __repr__(self):
        return f"<ServerMember(id={self.id}, server_id={self.server_id}, user_id={self.user_id})>"
