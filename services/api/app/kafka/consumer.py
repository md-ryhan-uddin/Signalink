"""
Kafka Consumer Manager
Consumes events from Kafka topics and processes them
"""
import asyncio
import json
import logging
from typing import Callable, Dict, Optional
from aiokafka import AIOKafkaConsumer
from aiokafka.errors import KafkaError

from ..config import settings

logger = logging.getLogger(__name__)


class KafkaConsumerManager:
    """
    Manages Kafka consumer for processing events from topics
    """

    def __init__(self):
        self.kafka_enabled = settings.KAFKA_ENABLED
        self.bootstrap_servers = settings.KAFKA_BOOTSTRAP_SERVERS
        self.consumer_group = settings.KAFKA_CONSUMER_GROUP
        self.consumers: Dict[str, AIOKafkaConsumer] = {}
        self.event_handlers: Dict[str, Callable] = {}
        self.running = False

        logger.info(f"Kafka consumer manager initialized (enabled={self.kafka_enabled})")

    def register_handler(self, event_type: str, handler: Callable):
        """
        Register an event handler for a specific event type

        Args:
            event_type: Type of event (e.g., "message.created")
            handler: Async function to handle the event
        """
        self.event_handlers[event_type] = handler
        logger.info(f"Registered handler for event type: {event_type}")

    async def start(self):
        """Initialize and start Kafka consumers for all topics"""
        if not self.kafka_enabled:
            logger.info("Kafka consumer disabled, skipping start")
            return

        try:
            # Create consumers for each topic
            topics = [
                settings.KAFKA_TOPIC_MESSAGES,
                settings.KAFKA_TOPIC_NOTIFICATIONS,
                settings.KAFKA_TOPIC_ANALYTICS,
                settings.KAFKA_TOPIC_PRESENCE,
            ]

            for topic in topics:
                consumer = AIOKafkaConsumer(
                    topic,
                    bootstrap_servers=self.bootstrap_servers,
                    group_id=self.consumer_group,
                    value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                    auto_offset_reset='earliest',  # Start from beginning if no offset
                    enable_auto_commit=True,
                    auto_commit_interval_ms=1000,
                )

                await consumer.start()
                self.consumers[topic] = consumer
                logger.info(f"Kafka consumer started for topic: {topic}")

            self.running = True
            logger.info(f"All Kafka consumers started successfully")

        except Exception as e:
            logger.error(f"Failed to start Kafka consumers: {e}")
            self.kafka_enabled = False
            raise

    async def stop(self):
        """Stop all Kafka consumers"""
        if not self.kafka_enabled:
            return

        self.running = False

        try:
            for topic, consumer in self.consumers.items():
                await consumer.stop()
                logger.info(f"Kafka consumer stopped for topic: {topic}")

            self.consumers.clear()
            logger.info("All Kafka consumers stopped")

        except Exception as e:
            logger.error(f"Error stopping Kafka consumers: {e}")

    async def consume_messages(self, topic: str):
        """
        Consume messages from a specific topic

        Args:
            topic: Kafka topic to consume from
        """
        if not self.kafka_enabled or topic not in self.consumers:
            return

        consumer = self.consumers[topic]
        logger.info(f"Starting message consumption for topic: {topic}")

        try:
            async for message in consumer:
                if not self.running:
                    break

                try:
                    event_data = message.value
                    event_type = event_data.get('event_type')

                    logger.info(f"Received event: {event_type} from topic: {topic}")

                    # Call registered handler if exists
                    if event_type in self.event_handlers:
                        handler = self.event_handlers[event_type]
                        await handler(event_data)
                    else:
                        logger.warning(f"No handler registered for event type: {event_type}")

                except Exception as e:
                    logger.error(f"Error processing message from {topic}: {e}", exc_info=True)
                    # Continue processing other messages

        except KafkaError as e:
            logger.error(f"Kafka error in consumer for {topic}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error in consumer for {topic}: {e}", exc_info=True)

    async def start_consuming(self):
        """Start consuming from all topics (runs in background)"""
        if not self.kafka_enabled:
            return

        tasks = []
        for topic in self.consumers.keys():
            task = asyncio.create_task(self.consume_messages(topic))
            tasks.append(task)
            logger.info(f"Started consumption task for topic: {topic}")

        # Wait for all consumer tasks
        await asyncio.gather(*tasks, return_exceptions=True)


# Global consumer instance
kafka_consumer = KafkaConsumerManager()
