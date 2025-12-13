"""
Kafka producer for publishing events to topics
"""
import json
import logging
from typing import Optional
from uuid import uuid4
from aiokafka import AIOKafkaProducer
from aiokafka.errors import KafkaError

from ..config import settings
from .events import BaseEvent

logger = logging.getLogger(__name__)


class KafkaProducerManager:
    """
    Manages Kafka producer lifecycle and message publishing
    """

    def __init__(self):
        self.producer: Optional[AIOKafkaProducer] = None
        self.kafka_enabled = settings.KAFKA_ENABLED
        self.bootstrap_servers = settings.KAFKA_BOOTSTRAP_SERVERS

    async def start(self):
        """Initialize and start the Kafka producer"""
        if not self.kafka_enabled:
            logger.info("Kafka is disabled, skipping producer initialization")
            return

        try:
            self.producer = AIOKafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                # Reliability settings
                acks='all',  # Wait for all replicas
                # Performance settings
                compression_type='gzip',
            )
            await self.producer.start()
            logger.info(f"Kafka producer started successfully: {self.bootstrap_servers}")
        except Exception as e:
            logger.error(f"Failed to start Kafka producer: {e}")
            self.kafka_enabled = False

    async def stop(self):
        """Stop the Kafka producer"""
        if self.producer:
            try:
                await self.producer.stop()
                logger.info("Kafka producer stopped")
            except Exception as e:
                logger.error(f"Error stopping Kafka producer: {e}")

    async def publish_event(
        self,
        topic: str,
        event: BaseEvent,
        key: Optional[str] = None
    ) -> bool:
        """
        Publish an event to a Kafka topic

        Args:
            topic: Kafka topic name
            event: Event object to publish
            key: Optional partition key for ordering

        Returns:
            bool: True if published successfully, False otherwise
        """
        if not self.kafka_enabled or not self.producer:
            logger.debug(f"Kafka disabled, skipping event publish to {topic}")
            return False

        try:
            # Convert event to dict for serialization
            event_data = event.model_dump(mode='json')

            # Use key for partition assignment (e.g., user_id for ordered events)
            key_bytes = key.encode('utf-8') if key else None

            # Send to Kafka
            await self.producer.send_and_wait(
                topic,
                value=event_data,
                key=key_bytes
            )

            logger.info(f"Published event to {topic}: {event.event_type}")
            return True

        except KafkaError as e:
            logger.error(f"Kafka error publishing event to {topic}: {e}", exc_info=True)
            return False
        except Exception as e:
            logger.error(f"Unexpected error publishing event to {topic}: {e}", exc_info=True)
            return False

    async def publish_message_event(self, event_type: str, message_data: dict) -> bool:
        """
        Publish a message event to signalink.messages topic

        Args:
            event_type: Type of event (message.created, message.edited, message.deleted)
            message_data: Message data

        Returns:
            bool: True if published successfully
        """
        from .events import MessageEvent

        try:
            logger.info(f"Creating {event_type} event for message {message_data.get('id')}")
            event = MessageEvent(
                event_id=str(uuid4()),
                event_type=event_type,
                message_id=message_data["id"],
                channel_id=message_data["channel_id"],
                user_id=message_data["user_id"],
                content=message_data.get("content"),
                message_type=message_data.get("message_type", "text"),
                metadata=message_data.get("metadata"),
                is_edited=message_data.get("is_edited", False),
                is_deleted=message_data.get("is_deleted", False),
            )

            # Use channel_id as key for ordering within channel
            key = str(message_data["channel_id"])

            logger.info(f"Publishing {event_type} event to Kafka...")
            result = await self.publish_event("signalink.messages", event, key)
            logger.info(f"Publish result for {event_type}: {result}")
            return result

        except Exception as e:
            logger.error(f"Error creating message event: {e}", exc_info=True)
            return False

    async def publish_notification_event(self, notification_data: dict) -> bool:
        """
        Publish a notification event to signalink.notifications topic

        Args:
            notification_data: Notification data

        Returns:
            bool: True if published successfully
        """
        from .events import NotificationEvent

        try:
            event = NotificationEvent(
                event_id=str(uuid4()),
                event_type=notification_data["event_type"],
                user_id=notification_data.get("sender_user_id"),
                recipient_user_id=notification_data["recipient_user_id"],
                notification_type=notification_data["notification_type"],
                title=notification_data["title"],
                body=notification_data["body"],
                data=notification_data.get("data"),
                channel_id=notification_data.get("channel_id"),
                message_id=notification_data.get("message_id"),
            )

            # Use recipient_user_id as key for ordering
            key = str(notification_data["recipient_user_id"])

            return await self.publish_event("signalink.notifications", event, key)

        except Exception as e:
            logger.error(f"Error creating notification event: {e}")
            return False

    async def publish_analytics_event(self, analytics_data: dict) -> bool:
        """
        Publish an analytics event to signalink.analytics topic

        Args:
            analytics_data: Analytics event data

        Returns:
            bool: True if published successfully
        """
        from .events import AnalyticsEvent

        try:
            event = AnalyticsEvent(
                event_id=str(uuid4()),
                event_type=analytics_data["event_type"],
                user_id=analytics_data.get("user_id"),
                action=analytics_data["action"],
                entity_type=analytics_data["entity_type"],
                entity_id=analytics_data.get("entity_id"),
                properties=analytics_data.get("properties"),
                session_id=analytics_data.get("session_id"),
                ip_address=analytics_data.get("ip_address"),
                user_agent=analytics_data.get("user_agent"),
            )

            # Use user_id as key if available
            key = str(analytics_data["user_id"]) if analytics_data.get("user_id") else None

            return await self.publish_event("signalink.analytics", event, key)

        except Exception as e:
            logger.error(f"Error creating analytics event: {e}")
            return False


# Global Kafka producer instance
kafka_producer = KafkaProducerManager()
