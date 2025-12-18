"""
Message management endpoints
Send, retrieve, update, and delete messages
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import desc, select
from typing import List
from uuid import UUID
import logging

from ..database import get_db
from ..models import User, Message, Channel, ChannelMember
from ..schemas import MessageCreate, MessageResponse, MessageUpdate
from ..auth import get_current_user
from ..kafka import kafka_producer

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/messages", tags=["messages"])


@router.post("/", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def send_message(
    message_data: MessageCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Send a message to a channel

    - **channel_id**: ID of the channel
    - **content**: Message content (1-10000 characters)
    - **message_type**: Type of message (text, image, file, system) - default: text
    - **metadata**: Optional metadata (JSON)
    """
    # Check if channel exists
    result = await db.execute(
        select(Channel).filter(Channel.id == message_data.channel_id)
    )
    channel = result.scalar_one_or_none()

    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Channel not found"
        )

    # Check if user is a member of the channel
    result = await db.execute(
        select(ChannelMember).filter(
            ChannelMember.channel_id == message_data.channel_id,
            ChannelMember.user_id == current_user.id
        )
    )
    membership = result.scalar_one_or_none()

    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You must be a member of the channel to send messages"
        )

    # Create message
    new_message = Message(
        channel_id=message_data.channel_id,
        user_id=current_user.id,
        content=message_data.content,
        message_type=message_data.message_type,
        metadata=message_data.metadata
    )

    db.add(new_message)
    await db.commit()
    await db.refresh(new_message)

    # Publish message.created event to Kafka
    try:
        await kafka_producer.publish_message_event(
            event_type="message.created",
            message_data={
                "id": str(new_message.id),
                "channel_id": str(new_message.channel_id),
                "user_id": str(new_message.user_id),
                "content": new_message.content,
                "message_type": new_message.message_type,
                "metadata": new_message.metadata if isinstance(new_message.metadata, dict) or new_message.metadata is None else {},
                "created_at": new_message.created_at.isoformat(),
            }
        )
        logger.info(f"Published message.created event for message {new_message.id}")
    except Exception as e:
        logger.error(f"Failed to publish message event to Kafka: {e}")

    # TODO Phase 2: Broadcast message via Redis pub/sub for real-time delivery

    return new_message


@router.get("/channels/{channel_id}", response_model=List[MessageResponse])
async def get_channel_messages(
    channel_id: UUID,
    skip: int = 0,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get messages from a channel (paginated)

    - **channel_id**: ID of the channel
    - **skip**: Number of messages to skip (pagination)
    - **limit**: Maximum number of messages to return (default: 50, max: 100)
    """
    # Limit maximum page size
    if limit > 100:
        limit = 100

    # Check if channel exists
    result = await db.execute(
        select(Channel).filter(Channel.id == channel_id)
    )
    channel = result.scalar_one_or_none()

    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Channel not found"
        )

    # Check if user has access to channel
    if channel.is_private:
        result = await db.execute(
            select(ChannelMember).filter(
                ChannelMember.channel_id == channel_id,
                ChannelMember.user_id == current_user.id
            )
        )
        membership = result.scalar_one_or_none()

        if not membership:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to private channel"
            )
    else:
        # For public channels, check if user is a member
        result = await db.execute(
            select(ChannelMember).filter(
                ChannelMember.channel_id == channel_id,
                ChannelMember.user_id == current_user.id
            )
        )
        membership = result.scalar_one_or_none()

        if not membership:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You must be a member of the channel to view messages"
            )

    # Get messages (excluding soft-deleted)
    result = await db.execute(
        select(Message).filter(
            Message.channel_id == channel_id,
            Message.is_deleted == False
        ).order_by(desc(Message.created_at)).offset(skip).limit(limit)
    )
    messages = result.scalars().all()

    # Reverse to get chronological order
    messages = list(reversed(messages))

    return messages


@router.get("/{message_id}", response_model=MessageResponse)
async def get_message(
    message_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get a specific message by ID
    """
    result = await db.execute(
        select(Message).filter(
            Message.id == message_id,
            Message.is_deleted == False
        )
    )
    message = result.scalar_one_or_none()

    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found"
        )

    # Check if user has access to the channel
    result = await db.execute(
        select(Channel).filter(Channel.id == message.channel_id)
    )
    channel = result.scalar_one_or_none()

    if channel.is_private:
        result = await db.execute(
            select(ChannelMember).filter(
                ChannelMember.channel_id == message.channel_id,
                ChannelMember.user_id == current_user.id
            )
        )
        membership = result.scalar_one_or_none()

        if not membership:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )

    return message


@router.put("/{message_id}", response_model=MessageResponse)
async def update_message(
    message_id: UUID,
    message_update: MessageUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Update a message (author only)

    - **content**: New message content
    """
    result = await db.execute(
        select(Message).filter(
            Message.id == message_id,
            Message.is_deleted == False
        )
    )
    message = result.scalar_one_or_none()

    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found"
        )

    # Check if user is the message author
    if message.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only edit your own messages"
        )

    # Update message
    message.content = message_update.content
    message.is_edited = True

    await db.commit()
    await db.refresh(message)

    # Publish message.edited event to Kafka
    try:
        await kafka_producer.publish_message_event(
            event_type="message.edited",
            message_data={
                "id": str(message.id),
                "channel_id": str(message.channel_id),
                "user_id": str(message.user_id),
                "content": message.content,
                "message_type": message.message_type,
                "metadata": message.metadata if isinstance(message.metadata, dict) or message.metadata is None else {},
                "is_edited": message.is_edited,
                "updated_at": message.updated_at.isoformat() if message.updated_at else None,
            }
        )
        logger.info(f"Published message.edited event for message {message.id}")
    except Exception as e:
        logger.error(f"Failed to publish message update event to Kafka: {e}")

    # TODO Phase 2: Broadcast message update via WebSocket

    return message


@router.delete("/{message_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_message(
    message_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Delete a message (soft delete - author or channel admin/owner)
    """
    result = await db.execute(
        select(Message).filter(
            Message.id == message_id,
            Message.is_deleted == False
        )
    )
    message = result.scalar_one_or_none()

    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found"
        )

    # Check if user is the message author or channel admin/owner
    is_author = message.user_id == current_user.id

    result = await db.execute(
        select(ChannelMember).filter(
            ChannelMember.channel_id == message.channel_id,
            ChannelMember.user_id == current_user.id,
            ChannelMember.role.in_(['owner', 'admin'])
        )
    )
    membership = result.scalar_one_or_none()

    is_admin = membership is not None

    if not (is_author or is_admin):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete your own messages or you must be a channel admin"
        )

    # Soft delete
    message.is_deleted = True

    await db.commit()

    # Publish message.deleted event to Kafka
    try:
        await kafka_producer.publish_message_event(
            event_type="message.deleted",
            message_data={
                "id": str(message.id),
                "channel_id": str(message.channel_id),
                "user_id": str(message.user_id),
                "is_deleted": message.is_deleted,
                "deleted_at": message.updated_at.isoformat() if message.updated_at else None,
            }
        )
        logger.info(f"Published message.deleted event for message {message.id}")
    except Exception as e:
        logger.error(f"Failed to publish message deletion event to Kafka: {e}")

    # TODO Phase 2: Broadcast message deletion via WebSocket

    return None
