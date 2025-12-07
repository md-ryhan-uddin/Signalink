"""
WebSocket message schemas and data models
"""
from pydantic import BaseModel, Field
from typing import Optional, Literal, Dict, Any
from datetime import datetime
from uuid import UUID


class WSMessage(BaseModel):
    """Base WebSocket message structure"""
    type: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class WSMessageSend(WSMessage):
    """Client sends a message to a channel"""
    type: Literal["message.send"] = "message.send"
    channel_id: str
    content: str
    message_type: str = "text"
    metadata: Optional[Dict[str, Any]] = None


class WSMessageReceive(WSMessage):
    """Server broadcasts a message to channel subscribers"""
    type: Literal["message.receive"] = "message.receive"
    message_id: str
    channel_id: str
    user_id: str
    username: str
    content: str
    message_type: str
    metadata: Optional[Dict[str, Any]] = None
    created_at: datetime


class WSChannelSubscribe(WSMessage):
    """Client subscribes to a channel"""
    type: Literal["channel.subscribe"] = "channel.subscribe"
    channel_id: str


class WSChannelUnsubscribe(WSMessage):
    """Client unsubscribes from a channel"""
    type: Literal["channel.unsubscribe"] = "channel.unsubscribe"
    channel_id: str


class WSTypingStart(WSMessage):
    """Client starts typing in a channel"""
    type: Literal["typing.start"] = "typing.start"
    channel_id: str


class WSTypingStop(WSMessage):
    """Client stops typing in a channel"""
    type: Literal["typing.stop"] = "typing.stop"
    channel_id: str


class WSTypingIndicator(WSMessage):
    """Server broadcasts typing indicator"""
    type: Literal["typing.indicator"] = "typing.indicator"
    channel_id: str
    user_id: str
    username: str
    is_typing: bool


class WSPresenceUpdate(WSMessage):
    """Server broadcasts user presence update"""
    type: Literal["presence.update"] = "presence.update"
    user_id: str
    status: Literal["online", "offline", "away"]


class WSError(WSMessage):
    """Server sends error message"""
    type: Literal["error"] = "error"
    error: str
    code: Optional[str] = None


class WSSuccess(WSMessage):
    """Server sends success confirmation"""
    type: Literal["success"] = "success"
    message: str
    data: Optional[Dict[str, Any]] = None


class WSPing(WSMessage):
    """Client sends ping for connection health check"""
    type: Literal["ping"] = "ping"


class WSPong(WSMessage):
    """Server responds with pong"""
    type: Literal["pong"] = "pong"
