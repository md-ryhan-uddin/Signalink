"""
Message management endpoints
Send, retrieve, update, and delete messages
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import List
from uuid import UUID

from ..database import get_db
from ..models import User, Message, Channel, ChannelMember
from ..schemas import MessageCreate, MessageResponse, MessageUpdate
from ..auth import get_current_user

router = APIRouter(prefix="/messages", tags=["messages"])


@router.post("/", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def send_message(
    message_data: MessageCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Send a message to a channel

    - **channel_id**: ID of the channel
    - **content**: Message content (1-10000 characters)
    - **message_type**: Type of message (text, image, file, system) - default: text
    - **metadata**: Optional metadata (JSON)
    """
    # Check if channel exists
    channel = db.query(Channel).filter(Channel.id == message_data.channel_id).first()

    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Channel not found"
        )

    # Check if user is a member of the channel
    membership = db.query(ChannelMember).filter(
        ChannelMember.channel_id == message_data.channel_id,
        ChannelMember.user_id == current_user.id
    ).first()

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
    db.commit()
    db.refresh(new_message)

    # TODO Phase 3: Publish message to Kafka
    # TODO Phase 2: Broadcast message via Redis pub/sub for real-time delivery

    return new_message


@router.get("/channels/{channel_id}", response_model=List[MessageResponse])
async def get_channel_messages(
    channel_id: UUID,
    skip: int = 0,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
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
    channel = db.query(Channel).filter(Channel.id == channel_id).first()

    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Channel not found"
        )

    # Check if user has access to channel
    if channel.is_private:
        membership = db.query(ChannelMember).filter(
            ChannelMember.channel_id == channel_id,
            ChannelMember.user_id == current_user.id
        ).first()

        if not membership:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to private channel"
            )
    else:
        # For public channels, check if user is a member
        membership = db.query(ChannelMember).filter(
            ChannelMember.channel_id == channel_id,
            ChannelMember.user_id == current_user.id
        ).first()

        if not membership:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You must be a member of the channel to view messages"
            )

    # Get messages (excluding soft-deleted)
    messages = db.query(Message).filter(
        Message.channel_id == channel_id,
        Message.is_deleted == False
    ).order_by(desc(Message.created_at)).offset(skip).limit(limit).all()

    # Reverse to get chronological order
    messages.reverse()

    return messages


@router.get("/{message_id}", response_model=MessageResponse)
async def get_message(
    message_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get a specific message by ID
    """
    message = db.query(Message).filter(
        Message.id == message_id,
        Message.is_deleted == False
    ).first()

    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found"
        )

    # Check if user has access to the channel
    channel = db.query(Channel).filter(Channel.id == message.channel_id).first()

    if channel.is_private:
        membership = db.query(ChannelMember).filter(
            ChannelMember.channel_id == message.channel_id,
            ChannelMember.user_id == current_user.id
        ).first()

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
    db: Session = Depends(get_db)
):
    """
    Update a message (author only)

    - **content**: New message content
    """
    message = db.query(Message).filter(
        Message.id == message_id,
        Message.is_deleted == False
    ).first()

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

    db.commit()
    db.refresh(message)

    # TODO Phase 2: Broadcast message update via WebSocket
    # TODO Phase 3: Publish update event to Kafka

    return message


@router.delete("/{message_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_message(
    message_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete a message (soft delete - author or channel admin/owner)
    """
    message = db.query(Message).filter(
        Message.id == message_id,
        Message.is_deleted == False
    ).first()

    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found"
        )

    # Check if user is the message author or channel admin/owner
    is_author = message.user_id == current_user.id

    membership = db.query(ChannelMember).filter(
        ChannelMember.channel_id == message.channel_id,
        ChannelMember.user_id == current_user.id,
        ChannelMember.role.in_(['owner', 'admin'])
    ).first()

    is_admin = membership is not None

    if not (is_author or is_admin):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete your own messages or you must be a channel admin"
        )

    # Soft delete
    message.is_deleted = True

    db.commit()

    # TODO Phase 2: Broadcast message deletion via WebSocket
    # TODO Phase 3: Publish deletion event to Kafka

    return None
