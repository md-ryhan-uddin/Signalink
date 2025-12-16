"""
Analytics Metrics API Endpoints
Provides access to aggregated metrics and insights
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from typing import List, Optional
from datetime import datetime, timedelta
from uuid import UUID

from ..database import get_db
from ..models import MessageMetrics, ChannelMetrics, UserMetrics
from ..schemas import (
    MessageMetricsResponse,
    ChannelMetricsResponse,
    UserMetricsResponse,
    SystemStatsResponse
)

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("/messages", response_model=List[MessageMetricsResponse])
async def get_message_metrics(
    hours: int = Query(default=1, ge=1, le=168, description="Number of hours to retrieve (max 7 days)"),
    limit: int = Query(default=100, ge=1, le=1000),
    db: Session = Depends(get_db)
):
    """
    Get aggregated message metrics for the specified time period

    - **hours**: Number of hours to retrieve (1-168)
    - **limit**: Maximum number of records to return
    """
    cutoff_time = datetime.utcnow() - timedelta(hours=hours)

    metrics = db.query(MessageMetrics).filter(
        MessageMetrics.time_window >= cutoff_time
    ).order_by(desc(MessageMetrics.time_window)).limit(limit).all()

    return metrics


@router.get("/channels/{channel_id}", response_model=List[ChannelMetricsResponse])
async def get_channel_metrics(
    channel_id: UUID,
    hours: int = Query(default=1, ge=1, le=168),
    db: Session = Depends(get_db)
):
    """
    Get metrics for a specific channel

    - **channel_id**: Channel UUID
    - **hours**: Number of hours to retrieve
    """
    cutoff_time = datetime.utcnow() - timedelta(hours=hours)

    metrics = db.query(ChannelMetrics).filter(
        ChannelMetrics.channel_id == channel_id,
        ChannelMetrics.time_window >= cutoff_time
    ).order_by(desc(ChannelMetrics.time_window)).all()

    if not metrics:
        raise HTTPException(
            status_code=404,
            detail=f"No metrics found for channel {channel_id}"
        )

    return metrics


@router.get("/users/{user_id}", response_model=List[UserMetricsResponse])
async def get_user_metrics(
    user_id: UUID,
    hours: int = Query(default=1, ge=1, le=168),
    db: Session = Depends(get_db)
):
    """
    Get metrics for a specific user

    - **user_id**: User UUID
    - **hours**: Number of hours to retrieve
    """
    cutoff_time = datetime.utcnow() - timedelta(hours=hours)

    metrics = db.query(UserMetrics).filter(
        UserMetrics.user_id == user_id,
        UserMetrics.time_window >= cutoff_time
    ).order_by(desc(UserMetrics.time_window)).all()

    if not metrics:
        raise HTTPException(
            status_code=404,
            detail=f"No metrics found for user {user_id}"
        )

    return metrics


@router.get("/channels/top/active", response_model=List[ChannelMetricsResponse])
async def get_top_active_channels(
    hours: int = Query(default=1, ge=1, le=168),
    limit: int = Query(default=10, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """
    Get top active channels by message count

    - **hours**: Time period to analyze
    - **limit**: Number of channels to return
    """
    cutoff_time = datetime.utcnow() - timedelta(hours=hours)

    # Aggregate message counts per channel
    top_channels = db.query(
        ChannelMetrics.channel_id,
        func.sum(ChannelMetrics.message_count).label('total_messages')
    ).filter(
        ChannelMetrics.time_window >= cutoff_time
    ).group_by(
        ChannelMetrics.channel_id
    ).order_by(
        desc('total_messages')
    ).limit(limit).all()

    # Get latest metrics for these channels
    result = []
    for channel_id, _ in top_channels:
        latest_metric = db.query(ChannelMetrics).filter(
            ChannelMetrics.channel_id == channel_id,
            ChannelMetrics.time_window >= cutoff_time
        ).order_by(desc(ChannelMetrics.time_window)).first()

        if latest_metric:
            result.append(latest_metric)

    return result


@router.get("/users/top/active", response_model=List[UserMetricsResponse])
async def get_top_active_users(
    hours: int = Query(default=1, ge=1, le=168),
    limit: int = Query(default=10, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """
    Get top active users by message count

    - **hours**: Time period to analyze
    - **limit**: Number of users to return
    """
    cutoff_time = datetime.utcnow() - timedelta(hours=hours)

    # Aggregate message counts per user
    top_users = db.query(
        UserMetrics.user_id,
        func.sum(UserMetrics.messages_sent).label('total_messages')
    ).filter(
        UserMetrics.time_window >= cutoff_time
    ).group_by(
        UserMetrics.user_id
    ).order_by(
        desc('total_messages')
    ).limit(limit).all()

    # Get latest metrics for these users
    result = []
    for user_id, _ in top_users:
        latest_metric = db.query(UserMetrics).filter(
            UserMetrics.user_id == user_id,
            UserMetrics.time_window >= cutoff_time
        ).order_by(desc(UserMetrics.time_window)).first()

        if latest_metric:
            result.append(latest_metric)

    return result


@router.get("/system/stats", response_model=SystemStatsResponse)
async def get_system_stats(
    hours: int = Query(default=1, ge=1, le=24),
    db: Session = Depends(get_db)
):
    """
    Get overall system statistics

    - **hours**: Time period to analyze (1-24 hours)
    """
    cutoff_time = datetime.utcnow() - timedelta(hours=hours)

    # Calculate total messages
    total_messages = db.query(
        func.sum(MessageMetrics.message_count)
    ).filter(
        MessageMetrics.time_window >= cutoff_time
    ).scalar() or 0

    # Calculate messages per second (average across windows)
    avg_mps = db.query(
        func.avg(MessageMetrics.messages_per_second)
    ).filter(
        MessageMetrics.time_window >= cutoff_time
    ).scalar() or 0.0

    # Get unique active users (max across windows - rough estimate)
    active_users = db.query(
        func.max(MessageMetrics.active_users_count)
    ).filter(
        MessageMetrics.time_window >= cutoff_time
    ).scalar() or 0

    # Get unique active channels (max across windows)
    active_channels = db.query(
        func.max(MessageMetrics.active_channels_count)
    ).filter(
        MessageMetrics.time_window >= cutoff_time
    ).scalar() or 0

    # Find most active channel
    most_active_channel = db.query(
        ChannelMetrics.channel_id,
        func.sum(ChannelMetrics.message_count).label('total')
    ).filter(
        ChannelMetrics.time_window >= cutoff_time
    ).group_by(
        ChannelMetrics.channel_id
    ).order_by(desc('total')).first()

    # Find most active user
    most_active_user = db.query(
        UserMetrics.user_id,
        func.sum(UserMetrics.messages_sent).label('total')
    ).filter(
        UserMetrics.time_window >= cutoff_time
    ).group_by(
        UserMetrics.user_id
    ).order_by(desc('total')).first()

    return SystemStatsResponse(
        total_messages_last_hour=total_messages,
        messages_per_second=float(avg_mps),
        active_users_last_hour=active_users,
        active_channels_last_hour=active_channels,
        most_active_channel_id=most_active_channel[0] if most_active_channel else None,
        most_active_user_id=most_active_user[0] if most_active_user else None
    )


@router.get("/system/timeseries")
async def get_timeseries_data(
    hours: int = Query(default=24, ge=1, le=168),
    db: Session = Depends(get_db)
):
    """
    Get time-series data for visualization
    Returns message counts over time

    - **hours**: Time period to retrieve
    """
    cutoff_time = datetime.utcnow() - timedelta(hours=hours)

    metrics = db.query(MessageMetrics).filter(
        MessageMetrics.time_window >= cutoff_time
    ).order_by(MessageMetrics.time_window).all()

    return {
        "time_series": [
            {
                "timestamp": m.time_window.isoformat(),
                "message_count": m.message_count,
                "messages_per_second": m.messages_per_second,
                "active_users": m.active_users_count,
                "active_channels": m.active_channels_count
            }
            for m in metrics
        ]
    }
