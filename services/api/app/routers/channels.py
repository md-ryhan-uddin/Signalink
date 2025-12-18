"""
Channel management endpoints
Create, read, update, delete channels and manage memberships
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select
from typing import List
from uuid import UUID

from ..database import get_db
from ..models import User, Channel, ChannelMember
from ..schemas import (
    ChannelCreate, ChannelResponse, ChannelUpdate,
    ChannelMemberCreate, ChannelMemberResponse
)
from ..auth import get_current_user

router = APIRouter(prefix="/channels", tags=["channels"])


@router.post("/", response_model=ChannelResponse, status_code=status.HTTP_201_CREATED)
async def create_channel(
    channel_data: ChannelCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new channel

    - **name**: Unique channel name (2-100 characters)
    - **description**: Optional channel description
    - **is_private**: Whether channel is private (default: false)
    """
    # Check if channel name already exists
    result = await db.execute(select(Channel).filter(Channel.name == channel_data.name))
    existing_channel = result.scalar_one_or_none()
    if existing_channel:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Channel name already exists"
        )

    # Create channel
    new_channel = Channel(
        name=channel_data.name,
        description=channel_data.description,
        is_private=channel_data.is_private,
        created_by=current_user.id
    )

    db.add(new_channel)
    await db.commit()
    await db.refresh(new_channel)

    return new_channel


@router.get("/", response_model=List[ChannelResponse])
async def list_channels(
    skip: int = 0,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    List all channels accessible to the current user

    - **skip**: Number of records to skip (pagination)
    - **limit**: Maximum number of records to return
    """
    # Get channels where user is a member or public channels
    stmt = select(Channel).join(
        ChannelMember,
        (Channel.id == ChannelMember.channel_id) & (ChannelMember.user_id == current_user.id),
        isouter=True
    ).filter(
        (Channel.is_private == False) | (ChannelMember.user_id == current_user.id)
    ).distinct().offset(skip).limit(limit)

    result = await db.execute(stmt)
    channels = result.scalars().all()

    # Add member and message counts
    for channel in channels:
        count_result = await db.execute(
            select(func.count(ChannelMember.id)).filter(
                ChannelMember.channel_id == channel.id
            )
        )
        channel.member_count = count_result.scalar()

        # Message count would require Message model - placeholder for now
        channel.message_count = 0

    return channels


@router.get("/{channel_id}", response_model=ChannelResponse)
async def get_channel(
    channel_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get channel details by ID
    """
    result = await db.execute(select(Channel).filter(Channel.id == channel_id))
    channel = result.scalar_one_or_none()

    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Channel not found"
        )

    # Check if user has access to private channel
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

    # Add counts
    count_result = await db.execute(
        select(func.count(ChannelMember.id)).filter(
            ChannelMember.channel_id == channel.id
        )
    )
    channel.member_count = count_result.scalar()
    channel.message_count = 0

    return channel


@router.put("/{channel_id}", response_model=ChannelResponse)
async def update_channel(
    channel_id: UUID,
    channel_update: ChannelUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Update channel details (owner/admin only)

    - **name**: Update channel name
    - **description**: Update description
    - **is_private**: Change privacy setting
    """
    result = await db.execute(select(Channel).filter(Channel.id == channel_id))
    channel = result.scalar_one_or_none()

    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Channel not found"
        )

    # Check if user is owner or admin
    result = await db.execute(
        select(ChannelMember).filter(
            ChannelMember.channel_id == channel_id,
            ChannelMember.user_id == current_user.id,
            ChannelMember.role.in_(['owner', 'admin'])
        )
    )
    membership = result.scalar_one_or_none()

    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only channel owner or admin can update channel"
        )

    # Update fields
    if channel_update.name is not None:
        # Check if new name is unique
        result = await db.execute(
            select(Channel).filter(
                Channel.name == channel_update.name,
                Channel.id != channel_id
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Channel name already exists"
            )
        channel.name = channel_update.name

    if channel_update.description is not None:
        channel.description = channel_update.description

    if channel_update.is_private is not None:
        channel.is_private = channel_update.is_private

    await db.commit()
    await db.refresh(channel)

    return channel


@router.delete("/{channel_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_channel(
    channel_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Delete a channel (owner only)
    """
    result = await db.execute(select(Channel).filter(Channel.id == channel_id))
    channel = result.scalar_one_or_none()

    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Channel not found"
        )

    # Check if user is owner
    if channel.created_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only channel owner can delete channel"
        )

    await db.delete(channel)
    await db.commit()

    return None


# ====================================
# Channel Membership Endpoints
# ====================================

@router.post("/{channel_id}/members", response_model=ChannelMemberResponse, status_code=status.HTTP_201_CREATED)
async def add_channel_member(
    channel_id: UUID,
    member_data: ChannelMemberCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Add a member to a channel

    - **user_id**: ID of user to add
    - **role**: Role to assign (member, admin) - default: member
    """
    result = await db.execute(select(Channel).filter(Channel.id == channel_id))
    channel = result.scalar_one_or_none()

    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Channel not found"
        )

    # Check if current user has permission to add members
    result = await db.execute(
        select(ChannelMember).filter(
            ChannelMember.channel_id == channel_id,
            ChannelMember.user_id == current_user.id,
            ChannelMember.role.in_(['owner', 'admin'])
        )
    )
    current_membership = result.scalar_one_or_none()

    if not current_membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only channel owner or admin can add members"
        )

    # Check if user exists
    result = await db.execute(select(User).filter(User.id == member_data.user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Check if already a member
    result = await db.execute(
        select(ChannelMember).filter(
            ChannelMember.channel_id == channel_id,
            ChannelMember.user_id == member_data.user_id
        )
    )
    existing_membership = result.scalar_one_or_none()

    if existing_membership:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is already a member of this channel"
        )

    # Add member
    new_membership = ChannelMember(
        channel_id=channel_id,
        user_id=member_data.user_id,
        role=member_data.role
    )

    db.add(new_membership)
    await db.commit()
    await db.refresh(new_membership)

    return new_membership


@router.get("/{channel_id}/members", response_model=List[ChannelMemberResponse])
async def list_channel_members(
    channel_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    List all members of a channel
    """
    result = await db.execute(select(Channel).filter(Channel.id == channel_id))
    channel = result.scalar_one_or_none()

    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Channel not found"
        )

    # Check if user has access
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
                detail="Access denied"
            )

    result = await db.execute(
        select(ChannelMember).filter(
            ChannelMember.channel_id == channel_id
        )
    )
    members = result.scalars().all()

    return members


@router.delete("/{channel_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_channel_member(
    channel_id: UUID,
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Remove a member from a channel
    """
    result = await db.execute(select(Channel).filter(Channel.id == channel_id))
    channel = result.scalar_one_or_none()

    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Channel not found"
        )

    # Check if current user has permission
    result = await db.execute(
        select(ChannelMember).filter(
            ChannelMember.channel_id == channel_id,
            ChannelMember.user_id == current_user.id,
            ChannelMember.role.in_(['owner', 'admin'])
        )
    )
    current_membership = result.scalar_one_or_none()

    # Allow users to remove themselves
    if not current_membership and user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied"
        )

    # Find membership to remove
    result = await db.execute(
        select(ChannelMember).filter(
            ChannelMember.channel_id == channel_id,
            ChannelMember.user_id == user_id
        )
    )
    membership = result.scalar_one_or_none()

    if not membership:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User is not a member of this channel"
        )

    # Don't allow removing the owner
    if membership.role == 'owner':
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot remove channel owner"
        )

    await db.delete(membership)
    await db.commit()

    return None
