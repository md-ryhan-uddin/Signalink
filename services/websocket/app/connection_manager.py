"""
WebSocket connection manager
Handles active connections, message routing, and presence tracking
"""
import logging
from typing import Dict, Set, Optional
from uuid import UUID
from fastapi import WebSocket
from datetime import datetime

from .redis_manager import redis_manager

logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    Manages active WebSocket connections and message routing
    Supports multiple connections per user (different devices/tabs)
    """

    def __init__(self):
        # Map of user_id -> set of WebSocket connections
        self.active_connections: Dict[UUID, Set[WebSocket]] = {}
        # Map of channel_id -> set of user_ids (for quick channel broadcasting)
        self.channel_members: Dict[str, Set[UUID]] = {}
        # Map of WebSocket -> user_id (for quick lookup on disconnect)
        self.websocket_to_user: Dict[WebSocket, UUID] = {}

    async def connect(self, websocket: WebSocket, user_id: UUID, username: str):
        """
        Accept new WebSocket connection and register user

        Args:
            websocket: WebSocket connection
            user_id: User UUID
            username: Username for logging
        """
        await websocket.accept()

        # Add to active connections
        if user_id not in self.active_connections:
            self.active_connections[user_id] = set()
        self.active_connections[user_id].add(websocket)
        self.websocket_to_user[websocket] = user_id

        # Mark user as online in Redis
        await redis_manager.set_user_online(user_id)
        await redis_manager.publish_presence_update(user_id, "online")

        logger.info(f"✅ User {username} ({user_id}) connected. Total connections: {len(self.active_connections[user_id])}")

    async def disconnect(self, websocket: WebSocket):
        """
        Remove WebSocket connection and cleanup

        Args:
            websocket: WebSocket connection to remove
        """
        # Find user_id for this websocket
        user_id = self.websocket_to_user.get(websocket)
        if not user_id:
            return

        # Remove from active connections
        if user_id in self.active_connections:
            self.active_connections[user_id].discard(websocket)

            # If user has no more connections, mark offline
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
                await redis_manager.set_user_offline(user_id)
                await redis_manager.publish_presence_update(user_id, "offline")
                logger.info(f"User {user_id} fully disconnected")

        # Remove from websocket lookup
        if websocket in self.websocket_to_user:
            del self.websocket_to_user[websocket]

        # Remove from all channel subscriptions
        for channel_id, members in list(self.channel_members.items()):
            if user_id in members:
                members.discard(user_id)
                if not members:
                    del self.channel_members[channel_id]

    async def subscribe_to_channel(self, user_id: UUID, channel_id: str):
        """
        Subscribe user to a channel for receiving messages

        Args:
            user_id: User UUID
            channel_id: Channel UUID to subscribe to
        """
        if channel_id not in self.channel_members:
            self.channel_members[channel_id] = set()

        self.channel_members[channel_id].add(user_id)
        logger.debug(f"User {user_id} subscribed to channel {channel_id}")

    async def unsubscribe_from_channel(self, user_id: UUID, channel_id: str):
        """
        Unsubscribe user from a channel

        Args:
            user_id: User UUID
            channel_id: Channel UUID to unsubscribe from
        """
        if channel_id in self.channel_members:
            self.channel_members[channel_id].discard(user_id)
            if not self.channel_members[channel_id]:
                del self.channel_members[channel_id]
        logger.debug(f"User {user_id} unsubscribed from channel {channel_id}")

    async def send_personal_message(self, message: dict, user_id: UUID):
        """
        Send message to a specific user (all their connections)

        Args:
            message: Message data to send
            user_id: Target user UUID
        """
        if user_id not in self.active_connections:
            logger.debug(f"User {user_id} not connected, skipping message")
            return

        # Send to all user's connections
        disconnected_sockets = []
        for websocket in self.active_connections[user_id]:
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.error(f"Error sending to websocket: {e}")
                disconnected_sockets.append(websocket)

        # Cleanup disconnected sockets
        for ws in disconnected_sockets:
            await self.disconnect(ws)

    async def broadcast_to_channel(self, message: dict, channel_id: str, exclude_user: Optional[UUID] = None):
        """
        Broadcast message to all users in a channel

        Args:
            message: Message data to broadcast
            channel_id: Channel UUID
            exclude_user: Optional user_id to exclude from broadcast (e.g., sender)
        """
        if channel_id not in self.channel_members:
            logger.debug(f"No active members in channel {channel_id}")
            return

        # Get all users subscribed to this channel
        members = self.channel_members[channel_id].copy()

        if exclude_user:
            members.discard(exclude_user)

        # Send to all members
        for user_id in members:
            await self.send_personal_message(message, user_id)

        logger.debug(f"Broadcasted to {len(members)} users in channel {channel_id}")

    async def get_online_users(self) -> Set[UUID]:
        """
        Get set of all online user IDs

        Returns:
            Set[UUID]: Set of online user UUIDs
        """
        return set(self.active_connections.keys())

    async def is_user_online(self, user_id: UUID) -> bool:
        """
        Check if user has any active connections

        Args:
            user_id: User UUID

        Returns:
            bool: True if user is online
        """
        return user_id in self.active_connections

    async def get_channel_online_users(self, channel_id: str) -> Set[UUID]:
        """
        Get online users in a specific channel

        Args:
            channel_id: Channel UUID

        Returns:
            Set[UUID]: Set of online user UUIDs in channel
        """
        if channel_id not in self.channel_members:
            return set()

        # Filter to only online users
        online_users = set()
        for user_id in self.channel_members[channel_id]:
            if await self.is_user_online(user_id):
                online_users.add(user_id)

        return online_users


# Global connection manager instance
connection_manager = ConnectionManager()
