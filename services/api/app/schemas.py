"""
Pydantic schemas for request/response validation
"""
from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import Optional, List
from datetime import datetime
from uuid import UUID


# ====================================
# User Schemas
# ====================================
class UserBase(BaseModel):
    """Base user schema"""
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    full_name: Optional[str] = None


class UserCreate(UserBase):
    """Schema for user registration"""
    password: str = Field(..., min_length=8, max_length=100)


class UserUpdate(BaseModel):
    """Schema for user updates"""
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None


class UserResponse(UserBase):
    """Schema for user response"""
    id: UUID
    avatar_url: Optional[str] = None
    is_active: bool
    is_verified: bool
    created_at: datetime
    last_seen_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class UserLogin(BaseModel):
    """Schema for user login"""
    username: str
    password: str


# ====================================
# Authentication Schemas
# ====================================
class Token(BaseModel):
    """Schema for JWT token response"""
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class TokenData(BaseModel):
    """Schema for decoded token data"""
    user_id: Optional[UUID] = None
    username: Optional[str] = None
    jti: Optional[str] = None


# ====================================
# Channel Schemas
# ====================================
class ChannelBase(BaseModel):
    """Base channel schema"""
    name: str = Field(..., min_length=2, max_length=100)
    description: Optional[str] = None
    is_private: bool = False


class ChannelCreate(ChannelBase):
    """Schema for channel creation"""
    pass


class ChannelUpdate(BaseModel):
    """Schema for channel updates"""
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    description: Optional[str] = None
    is_private: Optional[bool] = None


class ChannelResponse(ChannelBase):
    """Schema for channel response"""
    id: UUID
    created_by: UUID
    created_at: datetime
    updated_at: datetime
    member_count: Optional[int] = 0
    message_count: Optional[int] = 0

    model_config = ConfigDict(from_attributes=True)


# ====================================
# Channel Member Schemas
# ====================================
class ChannelMemberBase(BaseModel):
    """Base channel member schema"""
    channel_id: UUID
    user_id: UUID


class ChannelMemberCreate(BaseModel):
    """Schema for adding member to channel"""
    user_id: UUID
    role: str = "member"


class ChannelMemberResponse(ChannelMemberBase):
    """Schema for channel member response"""
    id: UUID
    role: str
    joined_at: datetime
    user: Optional[UserResponse] = None

    model_config = ConfigDict(from_attributes=True)


# ====================================
# Message Schemas
# ====================================
class MessageBase(BaseModel):
    """Base message schema"""
    content: str = Field(..., min_length=1, max_length=10000)
    message_type: str = "text"


class MessageCreate(MessageBase):
    """Schema for message creation"""
    channel_id: UUID
    metadata: Optional[dict] = None


class MessageUpdate(BaseModel):
    """Schema for message updates"""
    content: str = Field(..., min_length=1, max_length=10000)


class MessageResponse(MessageBase):
    """Schema for message response"""
    id: UUID
    channel_id: UUID
    user_id: Optional[UUID]
    metadata: Optional[dict] = Field(None, validation_alias="message_metadata")
    is_edited: bool
    is_deleted: bool
    created_at: datetime
    updated_at: datetime
    user: Optional[UserResponse] = None

    model_config = ConfigDict(from_attributes=True)


# ====================================
# Notification Preference Schemas
# ====================================
class NotificationPreferenceBase(BaseModel):
    """Base notification preference schema"""
    email_notifications: bool = True
    push_notifications: bool = True
    mention_notifications: bool = True
    dm_notifications: bool = True


class NotificationPreferenceUpdate(NotificationPreferenceBase):
    """Schema for updating notification preferences"""
    pass


class NotificationPreferenceResponse(NotificationPreferenceBase):
    """Schema for notification preference response"""
    id: UUID
    user_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ====================================
# Generic Response Schemas
# ====================================
class ErrorResponse(BaseModel):
    """Schema for error responses"""
    detail: str
    code: Optional[str] = None


class SuccessResponse(BaseModel):
    """Schema for generic success responses"""
    message: str
    data: Optional[dict] = None


class PaginatedResponse(BaseModel):
    """Schema for paginated responses"""
    items: List[dict]
    total: int
    page: int
    page_size: int
    total_pages: int


# ====================================
# Analytics Schemas
# ====================================
class AnalyticsEventCreate(BaseModel):
    """Schema for creating analytics events"""
    event_type: str
    user_id: Optional[UUID] = None
    channel_id: Optional[UUID] = None
    metadata: Optional[dict] = None


class AnalyticsEventResponse(BaseModel):
    """Schema for analytics event response"""
    id: UUID
    event_type: str
    user_id: Optional[UUID]
    channel_id: Optional[UUID]
    metadata: Optional[dict]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
