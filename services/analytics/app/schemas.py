"""
Analytics API Schemas
"""
from pydantic import BaseModel
from datetime import datetime
from typing import Optional
from uuid import UUID


class MessageMetricsResponse(BaseModel):
    """Response schema for message metrics"""
    id: UUID
    time_window: datetime
    window_duration_seconds: int
    message_count: int
    messages_per_second: float
    active_users_count: int
    unique_senders_count: int
    active_channels_count: int
    text_messages_count: int
    image_messages_count: int
    file_messages_count: int
    system_messages_count: int
    created_at: datetime

    class Config:
        from_attributes = True


class ChannelMetricsResponse(BaseModel):
    """Response schema for channel metrics"""
    id: UUID
    channel_id: UUID
    time_window: datetime
    window_duration_seconds: int
    message_count: int
    unique_senders_count: int
    messages_per_second: float
    created_count: int
    edited_count: int
    deleted_count: int
    created_at: datetime

    class Config:
        from_attributes = True


class UserMetricsResponse(BaseModel):
    """Response schema for user metrics"""
    id: UUID
    user_id: UUID
    time_window: datetime
    window_duration_seconds: int
    messages_sent: int
    messages_edited: int
    messages_deleted: int
    channels_active: int
    created_at: datetime

    class Config:
        from_attributes = True


class SystemStatsResponse(BaseModel):
    """Response schema for overall system statistics"""
    total_messages_last_hour: int
    messages_per_second: float
    active_users_last_hour: int
    active_channels_last_hour: int
    most_active_channel_id: Optional[UUID] = None
    most_active_user_id: Optional[UUID] = None
