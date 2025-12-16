"""
Analytics Database Models
"""
from sqlalchemy import Column, String, Integer, Float, DateTime, func, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
import uuid

Base = declarative_base()


class MessageMetrics(Base):
    """
    Aggregated message metrics per time window
    Stores message count, active users, active channels per time period
    """
    __tablename__ = "message_metrics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    time_window = Column(DateTime, nullable=False, index=True)  # Start of time window
    window_duration_seconds = Column(Integer, nullable=False, default=60)

    # Message stats
    message_count = Column(Integer, nullable=False, default=0)
    messages_per_second = Column(Float, nullable=False, default=0.0)

    # User stats
    active_users_count = Column(Integer, nullable=False, default=0)
    unique_senders_count = Column(Integer, nullable=False, default=0)

    # Channel stats
    active_channels_count = Column(Integer, nullable=False, default=0)

    # Message type breakdown
    text_messages_count = Column(Integer, nullable=False, default=0)
    image_messages_count = Column(Integer, nullable=False, default=0)
    file_messages_count = Column(Integer, nullable=False, default=0)
    system_messages_count = Column(Integer, nullable=False, default=0)

    # Timestamps
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (
        Index('idx_time_window', 'time_window', 'window_duration_seconds'),
    )


class ChannelMetrics(Base):
    """
    Per-channel analytics metrics
    Tracks activity per channel over time
    """
    __tablename__ = "channel_metrics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    channel_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    time_window = Column(DateTime, nullable=False, index=True)
    window_duration_seconds = Column(Integer, nullable=False, default=60)

    # Channel activity
    message_count = Column(Integer, nullable=False, default=0)
    unique_senders_count = Column(Integer, nullable=False, default=0)
    messages_per_second = Column(Float, nullable=False, default=0.0)

    # Message operations
    created_count = Column(Integer, nullable=False, default=0)
    edited_count = Column(Integer, nullable=False, default=0)
    deleted_count = Column(Integer, nullable=False, default=0)

    # Timestamps
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (
        Index('idx_channel_time', 'channel_id', 'time_window'),
    )


class UserMetrics(Base):
    """
    Per-user analytics metrics
    Tracks user activity and engagement
    """
    __tablename__ = "user_metrics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    time_window = Column(DateTime, nullable=False, index=True)
    window_duration_seconds = Column(Integer, nullable=False, default=60)

    # User activity
    messages_sent = Column(Integer, nullable=False, default=0)
    messages_edited = Column(Integer, nullable=False, default=0)
    messages_deleted = Column(Integer, nullable=False, default=0)
    channels_active = Column(Integer, nullable=False, default=0)

    # Timestamps
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (
        Index('idx_user_time', 'user_id', 'time_window'),
    )
