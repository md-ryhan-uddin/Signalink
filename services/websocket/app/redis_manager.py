"""
Redis pub/sub manager for real-time message broadcasting
Handles Redis connection, pub/sub, and presence tracking
"""
import json
import asyncio
import logging
from typing import Dict, Set, Optional, Callable
from uuid import UUID
import redis.asyncio as redis

from .config import settings

logger = logging.getLogger(__name__)


class RedisManager:
    """
    Manages Redis pub/sub for real-time message broadcasting across WebSocket servers
    Supports horizontal scaling with multiple WebSocket server instances
    """

    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None
        self.pubsub: Optional[redis.client.PubSub] = None
        self.subscription_tasks: Dict[str, asyncio.Task] = {}
        self.message_handlers: Dict[str, Set[Callable]] = {}

    async def connect(self):
        """Initialize Redis connection and pub/sub"""
        try:
            self.redis_client = await redis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
                max_connections=settings.REDIS_MAX_CONNECTIONS
            )
            self.pubsub = self.redis_client.pubsub()
            logger.info("✅ Redis connection established")
        except Exception as e:
            logger.error(f"❌ Failed to connect to Redis: {e}")
            raise

    async def disconnect(self):
        """Close Redis connection and cleanup"""
        # Cancel all subscription tasks
        for task in self.subscription_tasks.values():
            task.cancel()

        if self.pubsub:
            await self.pubsub.unsubscribe()
            await self.pubsub.close()

        if self.redis_client:
            await self.redis_client.close()

        logger.info("Redis connection closed")

    async def publish_message(self, channel_id: str, message_data: dict):
        """
        Publish message to Redis channel for broadcasting

        Args:
            channel_id: Channel UUID to publish to
            message_data: Message payload to broadcast
        """
        if not self.redis_client:
            logger.error("Redis client not connected")
            return

        try:
            channel_key = f"channel:{channel_id}"
            message_json = json.dumps(message_data)
            result = await self.redis_client.publish(channel_key, message_json)
            logger.info(f"Published message to {channel_key} (subscribers: {result})")
        except Exception as e:
            logger.error(f"Failed to publish message: {e}")

    async def subscribe_to_channel(self, channel_id: str, handler: Callable):
        """
        Subscribe to a Redis channel for real-time messages

        Args:
            channel_id: Channel UUID to subscribe to
            handler: Async callback function to handle messages
        """
        if not self.pubsub:
            logger.error("Redis pubsub not initialized")
            return

        channel_key = f"channel:{channel_id}"

        # Register handler
        if channel_key not in self.message_handlers:
            self.message_handlers[channel_key] = set()
        self.message_handlers[channel_key].add(handler)

        # Subscribe if not already subscribed
        if channel_key not in self.subscription_tasks:
            await self.pubsub.subscribe(channel_key)
            task = asyncio.create_task(self._listen_to_channel(channel_key))
            self.subscription_tasks[channel_key] = task
            logger.info(f"Subscribed to {channel_key}")

    async def unsubscribe_from_channel(self, channel_id: str, handler: Callable):
        """
        Unsubscribe from a Redis channel

        Args:
            channel_id: Channel UUID to unsubscribe from
            handler: Handler to remove
        """
        channel_key = f"channel:{channel_id}"

        # Remove handler
        if channel_key in self.message_handlers:
            self.message_handlers[channel_key].discard(handler)

            # If no more handlers, unsubscribe from Redis
            if not self.message_handlers[channel_key]:
                await self.pubsub.unsubscribe(channel_key)
                if channel_key in self.subscription_tasks:
                    self.subscription_tasks[channel_key].cancel()
                    del self.subscription_tasks[channel_key]
                del self.message_handlers[channel_key]
                logger.info(f"Unsubscribed from {channel_key}")

    async def _listen_to_channel(self, channel_key: str):
        """
        Background task to listen for messages on a subscribed channel

        Args:
            channel_key: Redis channel key to listen to
        """
        logger.info(f"Started listener task for {channel_key}")
        try:
            async for message in self.pubsub.listen():
                logger.debug(f"Received Redis message: type={message['type']}, channel={message.get('channel')}")
                if message["type"] == "message":
                    try:
                        # Get the actual channel the message was published to
                        msg_channel = message.get('channel')
                        if isinstance(msg_channel, bytes):
                            msg_channel = msg_channel.decode('utf-8')

                        data = json.loads(message["data"])
                        logger.info(f"Processing message from Redis on {msg_channel}")

                        # Call handlers for the ACTUAL channel the message came from
                        if msg_channel in self.message_handlers:
                            handlers_count = len(self.message_handlers[msg_channel])
                            logger.info(f"Calling {handlers_count} handler(s) for {msg_channel}")
                            for handler in self.message_handlers[msg_channel]:
                                await handler(data)
                        else:
                            logger.warning(f"No handlers for {msg_channel}")
                    except json.JSONDecodeError:
                        logger.error(f"Invalid JSON in message: {message['data']}")
                    except Exception as e:
                        logger.error(f"Error handling message: {e}")
        except asyncio.CancelledError:
            logger.info(f"Stopped listening to {channel_key}")

    # ========================================
    # Presence Tracking
    # ========================================

    async def set_user_online(self, user_id: UUID):
        """
        Mark user as online in Redis

        Args:
            user_id: User UUID
        """
        if not self.redis_client:
            return

        try:
            key = f"user:presence:{user_id}"
            # Set with 5-minute expiration (renewed by heartbeat)
            await self.redis_client.setex(key, 300, "online")
            logger.debug(f"User {user_id} marked as online")
        except Exception as e:
            logger.error(f"Failed to set user online: {e}")

    async def set_user_offline(self, user_id: UUID):
        """
        Mark user as offline in Redis

        Args:
            user_id: User UUID
        """
        if not self.redis_client:
            return

        try:
            key = f"user:presence:{user_id}"
            await self.redis_client.delete(key)
            logger.debug(f"User {user_id} marked as offline")
        except Exception as e:
            logger.error(f"Failed to set user offline: {e}")

    async def is_user_online(self, user_id: UUID) -> bool:
        """
        Check if user is online

        Args:
            user_id: User UUID

        Returns:
            bool: True if user is online
        """
        if not self.redis_client:
            return False

        try:
            key = f"user:presence:{user_id}"
            exists = await self.redis_client.exists(key)
            return bool(exists)
        except Exception as e:
            logger.error(f"Failed to check user online status: {e}")
            return False

    async def publish_presence_update(self, user_id: UUID, status: str):
        """
        Broadcast user presence update to all subscribers

        Args:
            user_id: User UUID
            status: Presence status (online/offline/away)
        """
        if not self.redis_client:
            return

        try:
            channel_key = "presence:updates"
            data = {
                "user_id": str(user_id),
                "status": status,
                "timestamp": asyncio.get_event_loop().time()
            }
            await self.redis_client.publish(channel_key, json.dumps(data))
            logger.debug(f"Published presence update for user {user_id}: {status}")
        except Exception as e:
            logger.error(f"Failed to publish presence update: {e}")

    # ========================================
    # Typing Indicators
    # ========================================

    async def set_user_typing(self, channel_id: str, user_id: UUID, username: str):
        """
        Mark user as typing in a channel

        Args:
            channel_id: Channel UUID
            user_id: User UUID
            username: Username for display
        """
        if not self.redis_client:
            return

        try:
            key = f"typing:{channel_id}"
            # Store typing users in a hash with 10-second expiration
            await self.redis_client.hset(key, str(user_id), username)
            await self.redis_client.expire(key, 10)

            # Broadcast typing indicator
            await self.publish_typing_indicator(channel_id, user_id, username, True)
        except Exception as e:
            logger.error(f"Failed to set user typing: {e}")

    async def remove_user_typing(self, channel_id: str, user_id: UUID):
        """
        Remove user from typing indicator

        Args:
            channel_id: Channel UUID
            user_id: User UUID
        """
        if not self.redis_client:
            return

        try:
            key = f"typing:{channel_id}"
            await self.redis_client.hdel(key, str(user_id))

            # Broadcast stopped typing
            await self.publish_typing_indicator(channel_id, user_id, None, False)
        except Exception as e:
            logger.error(f"Failed to remove user typing: {e}")

    async def publish_typing_indicator(
        self,
        channel_id: str,
        user_id: UUID,
        username: Optional[str],
        is_typing: bool
    ):
        """
        Broadcast typing indicator to channel subscribers

        Args:
            channel_id: Channel UUID
            user_id: User UUID
            username: Username (None if stopped typing)
            is_typing: Whether user is typing
        """
        if not self.redis_client:
            return

        try:
            channel_key = f"channel:{channel_id}:typing"
            data = {
                "type": "typing_indicator",
                "user_id": str(user_id),
                "username": username,
                "is_typing": is_typing,
                "channel_id": channel_id
            }
            await self.redis_client.publish(channel_key, json.dumps(data))
        except Exception as e:
            logger.error(f"Failed to publish typing indicator: {e}")


# Global Redis manager instance
redis_manager = RedisManager()
