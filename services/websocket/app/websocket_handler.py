"""
WebSocket message handler
Routes incoming WebSocket messages to appropriate handlers
"""
import logging
import json
from datetime import datetime
from uuid import UUID
from fastapi import WebSocket
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .schemas import (
    WSMessageSend,
    WSMessageReceive,
    WSChannelSubscribe,
    WSChannelUnsubscribe,
    WSTypingStart,
    WSTypingStop,
    WSTypingIndicator,
    WSError,
    WSSuccess,
    WSPong,
)
from .connection_manager import connection_manager
from .redis_manager import redis_manager

logger = logging.getLogger(__name__)


class WebSocketHandler:
    """Handles WebSocket message routing and processing"""

    def __init__(self, websocket: WebSocket, user_id: UUID, username: str, db: AsyncSession):
        self.websocket = websocket
        self.user_id = user_id
        self.username = username
        self.db = db
        self.subscribed_channels: set = set()

    async def handle_message(self, data: dict):
        """
        Route incoming message to appropriate handler

        Args:
            data: Parsed JSON message from client
        """
        message_type = data.get("type")

        try:
            if message_type == "message.send":
                await self.handle_send_message(data)
            elif message_type == "channel.subscribe":
                await self.handle_channel_subscribe(data)
            elif message_type == "channel.unsubscribe":
                await self.handle_channel_unsubscribe(data)
            elif message_type == "typing.start":
                await self.handle_typing_start(data)
            elif message_type == "typing.stop":
                await self.handle_typing_stop(data)
            elif message_type == "ping":
                await self.handle_ping()
            else:
                await self.send_error(f"Unknown message type: {message_type}")
        except Exception as e:
            logger.error(f"Error handling message: {e}", exc_info=True)
            await self.send_error(f"Error processing message: {str(e)}")

    async def handle_send_message(self, data: dict):
        """
        Handle message.send: Save message to DB and broadcast to channel

        Args:
            data: Message data from client
        """
        try:
            msg = WSMessageSend(**data)

            # Import here to avoid circular dependency
            from .models import Message, User

            # Verify user is member of channel
            # This would require checking channel_members table
            # For now, we'll proceed with message creation

            # Create message in database
            new_message = Message(
                channel_id=UUID(msg.channel_id),
                user_id=self.user_id,
                content=msg.content,
                message_type=msg.message_type,
                message_metadata=msg.metadata,
            )

            self.db.add(new_message)
            await self.db.commit()
            await self.db.refresh(new_message)

            # Prepare broadcast message
            broadcast_msg = WSMessageReceive(
                message_id=str(new_message.id),
                channel_id=msg.channel_id,
                user_id=str(self.user_id),
                username=self.username,
                content=msg.content,
                message_type=msg.message_type,
                metadata=msg.metadata,
                created_at=new_message.created_at,
            )

            # Publish to Redis for broadcasting across all WebSocket servers
            await redis_manager.publish_message(
                msg.channel_id,
                broadcast_msg.model_dump(mode='json')
            )

            logger.info(f"Message {new_message.id} from {self.username} broadcasted to channel {msg.channel_id}")

        except Exception as e:
            logger.error(f"Error sending message: {e}", exc_info=True)
            await self.send_error(f"Failed to send message: {str(e)}")

    async def handle_channel_subscribe(self, data: dict):
        """
        Handle channel.subscribe: Subscribe to channel messages

        Args:
            data: Subscribe request data
        """
        try:
            msg = WSChannelSubscribe(**data)

            # TODO: Verify user has permission to access channel
            # Check channel_members table

            # Subscribe to local connection manager
            await connection_manager.subscribe_to_channel(self.user_id, msg.channel_id)

            # Subscribe to Redis pub/sub for this channel
            await redis_manager.subscribe_to_channel(
                msg.channel_id,
                self.create_channel_message_handler(msg.channel_id)
            )

            # Track subscribed channels
            self.subscribed_channels.add(msg.channel_id)

            # Send success confirmation
            await self.send_success(
                f"Subscribed to channel {msg.channel_id}",
                {"channel_id": msg.channel_id}
            )

            logger.info(f"User {self.username} subscribed to channel {msg.channel_id}")

        except Exception as e:
            logger.error(f"Error subscribing to channel: {e}", exc_info=True)
            await self.send_error(f"Failed to subscribe: {str(e)}")

    async def handle_channel_unsubscribe(self, data: dict):
        """
        Handle channel.unsubscribe: Unsubscribe from channel

        Args:
            data: Unsubscribe request data
        """
        try:
            msg = WSChannelUnsubscribe(**data)

            # Unsubscribe from local connection manager
            await connection_manager.unsubscribe_from_channel(self.user_id, msg.channel_id)

            # Unsubscribe from Redis pub/sub
            handler = self.create_channel_message_handler(msg.channel_id)
            await redis_manager.unsubscribe_from_channel(msg.channel_id, handler)

            # Remove from tracked channels
            self.subscribed_channels.discard(msg.channel_id)

            # Send success confirmation
            await self.send_success(
                f"Unsubscribed from channel {msg.channel_id}",
                {"channel_id": msg.channel_id}
            )

            logger.info(f"User {self.username} unsubscribed from channel {msg.channel_id}")

        except Exception as e:
            logger.error(f"Error unsubscribing from channel: {e}", exc_info=True)
            await self.send_error(f"Failed to unsubscribe: {str(e)}")

    async def handle_typing_start(self, data: dict):
        """
        Handle typing.start: User started typing

        Args:
            data: Typing start data
        """
        try:
            msg = WSTypingStart(**data)

            # Set typing status in Redis
            await redis_manager.set_user_typing(msg.channel_id, self.user_id, self.username)

            # Broadcast typing indicator to channel
            typing_msg = WSTypingIndicator(
                channel_id=msg.channel_id,
                user_id=str(self.user_id),
                username=self.username,
                is_typing=True,
            )

            await connection_manager.broadcast_to_channel(
                typing_msg.model_dump(mode='json'),
                msg.channel_id,
                exclude_user=self.user_id  # Don't send back to sender
            )

        except Exception as e:
            logger.error(f"Error handling typing start: {e}")

    async def handle_typing_stop(self, data: dict):
        """
        Handle typing.stop: User stopped typing

        Args:
            data: Typing stop data
        """
        try:
            msg = WSTypingStop(**data)

            # Remove typing status from Redis
            await redis_manager.remove_user_typing(msg.channel_id, self.user_id)

            # Broadcast stopped typing to channel
            typing_msg = WSTypingIndicator(
                channel_id=msg.channel_id,
                user_id=str(self.user_id),
                username=self.username,
                is_typing=False,
            )

            await connection_manager.broadcast_to_channel(
                typing_msg.model_dump(mode='json'),
                msg.channel_id,
                exclude_user=self.user_id
            )

        except Exception as e:
            logger.error(f"Error handling typing stop: {e}")

    async def handle_ping(self):
        """Handle ping: Respond with pong for connection health check"""
        pong = WSPong()
        await self.websocket.send_json(pong.model_dump(mode='json'))

        # Renew user online status
        await redis_manager.set_user_online(self.user_id)

    def create_channel_message_handler(self, channel_id: str):
        """
        Create a handler function for Redis pub/sub messages

        Args:
            channel_id: Channel UUID

        Returns:
            Async handler function
        """
        async def handler(message_data: dict):
            """Handle message from Redis pub/sub"""
            try:
                # Check if WebSocket is still connected before sending
                if self.websocket.client_state.name == "CONNECTED":
                    await self.websocket.send_json(message_data)
                else:
                    logger.debug(f"Skipping message send - WebSocket not connected (state: {self.websocket.client_state.name})")
            except Exception as e:
                logger.error(f"Error sending message from Redis: {e}")

        return handler

    async def send_error(self, error_message: str, code: str = None):
        """
        Send error message to client

        Args:
            error_message: Error description
            code: Optional error code
        """
        error = WSError(error=error_message, code=code)
        try:
            await self.websocket.send_json(error.model_dump(mode='json'))
        except Exception as e:
            logger.error(f"Failed to send error message: {e}")

    async def send_success(self, message: str, data: dict = None):
        """
        Send success message to client

        Args:
            message: Success message
            data: Optional additional data
        """
        success = WSSuccess(message=message, data=data)
        try:
            await self.websocket.send_json(success.model_dump(mode='json'))
        except Exception as e:
            logger.error(f"Failed to send success message: {e}")

    async def cleanup(self):
        """Cleanup handler on disconnect"""
        # Unsubscribe from all channels
        for channel_id in list(self.subscribed_channels):
            handler = self.create_channel_message_handler(channel_id)
            await redis_manager.unsubscribe_from_channel(channel_id, handler)

        self.subscribed_channels.clear()
