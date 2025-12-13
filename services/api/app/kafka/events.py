"""
Kafka event schemas for different event types
"""
from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from uuid import UUID


class BaseEvent(BaseModel):
    """Base event schema with common fields"""
    event_id: str = Field(..., description="Unique event ID")
    event_type: str = Field(..., description="Type of event")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Event timestamp")
    user_id: Optional[UUID] = Field(None, description="User who triggered the event")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v),
        }


class MessageEvent(BaseEvent):
    """
    Message events for signalink.messages topic
    Event types: message.created, message.edited, message.deleted
    """
    event_type: str = "message.created"
    message_id: UUID = Field(..., description="Message ID")
    channel_id: UUID = Field(..., description="Channel ID")
    content: Optional[str] = Field(None, description="Message content")
    message_type: str = Field(default="text", description="Message type (text, image, file)")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")

    # For edited messages
    is_edited: bool = Field(default=False, description="Whether message was edited")

    # For deleted messages
    is_deleted: bool = Field(default=False, description="Whether message was deleted")


class NotificationEvent(BaseEvent):
    """
    Notification events for signalink.notifications topic
    Event types: notification.mention, notification.new_message, notification.invite
    """
    event_type: str = "notification.new_message"
    recipient_user_id: UUID = Field(..., description="User to notify")
    notification_type: str = Field(..., description="Type of notification")
    title: str = Field(..., description="Notification title")
    body: str = Field(..., description="Notification body")
    data: Optional[Dict[str, Any]] = Field(None, description="Additional notification data")

    # Related entities
    channel_id: Optional[UUID] = Field(None, description="Related channel")
    message_id: Optional[UUID] = Field(None, description="Related message")


class AnalyticsEvent(BaseEvent):
    """
    Analytics events for signalink.analytics topic
    Event types: user.action, channel.activity, message.stats
    """
    event_type: str = "user.action"
    action: str = Field(..., description="Action performed (login, send_message, join_channel)")
    entity_type: str = Field(..., description="Type of entity (user, channel, message)")
    entity_id: Optional[UUID] = Field(None, description="Entity ID")
    properties: Optional[Dict[str, Any]] = Field(None, description="Event properties")

    # Session tracking
    session_id: Optional[str] = Field(None, description="User session ID")
    ip_address: Optional[str] = Field(None, description="User IP address")
    user_agent: Optional[str] = Field(None, description="User agent string")


class PresenceEvent(BaseEvent):
    """
    Presence events for signalink.presence topic
    Event types: presence.online, presence.offline, presence.typing
    """
    event_type: str = "presence.online"
    status: str = Field(..., description="Presence status (online, offline, away, typing)")
    channel_id: Optional[UUID] = Field(None, description="Channel for typing events")

    # Device tracking
    device_id: Optional[str] = Field(None, description="Device identifier")
    platform: Optional[str] = Field(None, description="Platform (web, mobile, desktop)")
