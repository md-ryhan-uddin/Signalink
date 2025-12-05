"""
SQLAlchemy ORM models for Signalink
Maps to the PostgreSQL schema defined in database/schema.sql
"""
from sqlalchemy import (
    Column, String, Boolean, DateTime, Text, ForeignKey,
    CheckConstraint, Index, TIMESTAMP, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import UUID, JSONB, INET
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
from .database import Base


class User(Base):
    """User account model"""
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255))
    avatar_url = Column(String(500))
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())
    last_seen_at = Column(TIMESTAMP(timezone=True))

    # Relationships
    channels_created = relationship("Channel", back_populates="creator", foreign_keys="Channel.created_by")
    channel_memberships = relationship("ChannelMember", back_populates="user")
    messages = relationship("Message", back_populates="user")
    sessions = relationship("UserSession", back_populates="user")
    notification_preferences = relationship("NotificationPreference", back_populates="user", uselist=False)

    __table_args__ = (
        CheckConstraint("LENGTH(username) >= 3", name="username_length"),
        CheckConstraint("email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}$'", name="email_format"),
    )


class Channel(Base):
    """Channel/room model"""
    __tablename__ = "channels"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), unique=True, nullable=False, index=True)
    description = Column(Text)
    is_private = Column(Boolean, default=False, index=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    creator = relationship("User", back_populates="channels_created", foreign_keys=[created_by])
    members = relationship("ChannelMember", back_populates="channel")
    messages = relationship("Message", back_populates="channel")

    __table_args__ = (
        CheckConstraint("LENGTH(name) >= 2", name="channel_name_length"),
    )


class ChannelMember(Base):
    """Channel membership model"""
    __tablename__ = "channel_members"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    channel_id = Column(UUID(as_uuid=True), ForeignKey("channels.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(20), default="member")
    joined_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

    # Relationships
    channel = relationship("Channel", back_populates="members")
    user = relationship("User", back_populates="channel_memberships")

    __table_args__ = (
        UniqueConstraint("channel_id", "user_id", name="uq_channel_user"),
        CheckConstraint("role IN ('owner', 'admin', 'member')", name="valid_role"),
        Index("idx_channel_members_channel", "channel_id"),
        Index("idx_channel_members_user", "user_id"),
    )


class Message(Base):
    """Message model"""
    __tablename__ = "messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    channel_id = Column(UUID(as_uuid=True), ForeignKey("channels.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    content = Column(Text, nullable=False)
    message_type = Column(String(20), default="text")
    message_metadata = Column("metadata", JSONB)  # Renamed to avoid SQLAlchemy reserved word
    is_edited = Column(Boolean, default=False)
    is_deleted = Column(Boolean, default=False)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    channel = relationship("Channel", back_populates="messages")
    user = relationship("User", back_populates="messages")
    reactions = relationship("MessageReaction", back_populates="message")

    __table_args__ = (
        CheckConstraint("LENGTH(TRIM(content)) > 0", name="content_not_empty"),
        CheckConstraint("message_type IN ('text', 'image', 'file', 'system')", name="valid_message_type"),
        Index("idx_messages_channel", "channel_id", "created_at"),
    )


class MessageReaction(Base):
    """Message reaction model"""
    __tablename__ = "message_reactions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    message_id = Column(UUID(as_uuid=True), ForeignKey("messages.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    emoji = Column(String(50), nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

    # Relationships
    message = relationship("Message", back_populates="reactions")

    __table_args__ = (
        UniqueConstraint("message_id", "user_id", "emoji", name="uq_message_user_emoji"),
        Index("idx_reactions_message", "message_id"),
    )


class ReadReceipt(Base):
    """Read receipt model"""
    __tablename__ = "read_receipts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    channel_id = Column(UUID(as_uuid=True), ForeignKey("channels.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    last_read_message_id = Column(UUID(as_uuid=True), ForeignKey("messages.id", ondelete="SET NULL"))
    last_read_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("channel_id", "user_id", name="uq_channel_user_receipt"),
        Index("idx_read_receipts_channel_user", "channel_id", "user_id"),
    )


class UserSession(Base):
    """User session model for JWT tracking"""
    __tablename__ = "user_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token_jti = Column(String(255), unique=True, nullable=False, index=True)
    expires_at = Column(TIMESTAMP(timezone=True), nullable=False, index=True)
    is_revoked = Column(Boolean, default=False)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    user_agent = Column(String(500))
    ip_address = Column(INET)

    # Relationships
    user = relationship("User", back_populates="sessions")


class NotificationPreference(Base):
    """User notification preferences"""
    __tablename__ = "notification_preferences"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    email_notifications = Column(Boolean, default=True)
    push_notifications = Column(Boolean, default=True)
    mention_notifications = Column(Boolean, default=True)
    dm_notifications = Column(Boolean, default=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="notification_preferences")


class AnalyticsEvent(Base):
    """Analytics event model for tracking"""
    __tablename__ = "analytics_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_type = Column(String(50), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    channel_id = Column(UUID(as_uuid=True), ForeignKey("channels.id", ondelete="SET NULL"))
    event_metadata = Column("metadata", JSONB)  # Renamed to avoid SQLAlchemy reserved word
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), index=True)

    __table_args__ = (
        Index("idx_analytics_events_type", "event_type", "created_at"),
    )
