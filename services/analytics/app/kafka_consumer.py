"""
Analytics Kafka Consumer
Consumes message events from Kafka and aggregates metrics
"""
import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Set
from collections import defaultdict
from aiokafka import AIOKafkaConsumer
from aiokafka.errors import KafkaError
from sqlalchemy.orm import Session

from .config import settings
from .database import SessionLocal
from .models import MessageMetrics, ChannelMetrics, UserMetrics

logger = logging.getLogger(__name__)


class AnalyticsConsumer:
    """
    Analytics Kafka Consumer
    Consumes message events and aggregates metrics in real-time
    """

    def __init__(self):
        self.consumer: AIOKafkaConsumer = None
        self.running = False

        # In-memory aggregation buffers (reset every window)
        self.current_window_start: datetime = None
        self.window_duration = timedelta(seconds=settings.metrics_window_seconds)

        # Metrics buffers
        self.message_count = 0
        self.active_users: Set[str] = set()
        self.unique_senders: Set[str] = set()
        self.active_channels: Set[str] = set()
        self.message_types: Dict[str, int] = defaultdict(int)

        # Per-channel metrics
        self.channel_metrics: Dict[str, Dict] = defaultdict(lambda: {
            'message_count': 0,
            'unique_senders': set(),
            'created': 0,
            'edited': 0,
            'deleted': 0
        })

        # Per-user metrics
        self.user_metrics: Dict[str, Dict] = defaultdict(lambda: {
            'messages_sent': 0,
            'messages_edited': 0,
            'messages_deleted': 0,
            'channels': set()
        })

    async def start(self):
        """Initialize and start Kafka consumer"""
        try:
            self.consumer = AIOKafkaConsumer(
                settings.kafka_topic_messages,
                bootstrap_servers=settings.kafka_bootstrap_servers,
                group_id=settings.kafka_consumer_group,
                auto_offset_reset='latest',
                enable_auto_commit=True,
                value_deserializer=lambda m: json.loads(m.decode('utf-8'))
            )

            await self.consumer.start()
            logger.info(f"Analytics consumer started for topic: {settings.kafka_topic_messages}")

            # Initialize first window
            self.current_window_start = self._get_window_start(datetime.utcnow())

        except Exception as e:
            logger.error(f"Failed to start analytics consumer: {e}")
            raise

    async def stop(self):
        """Stop Kafka consumer gracefully"""
        try:
            self.running = False
            if self.consumer:
                await self.consumer.stop()
                logger.info("Analytics consumer stopped")
        except Exception as e:
            logger.error(f"Error stopping analytics consumer: {e}")

    def _get_window_start(self, timestamp: datetime) -> datetime:
        """Get the start of the current time window"""
        window_seconds = settings.metrics_window_seconds
        epoch = datetime(1970, 1, 1)
        seconds_since_epoch = (timestamp - epoch).total_seconds()
        window_number = int(seconds_since_epoch // window_seconds)
        return epoch + timedelta(seconds=window_number * window_seconds)

    def _should_flush_window(self, event_timestamp: datetime) -> bool:
        """Check if we should flush the current window and start a new one"""
        window_start = self._get_window_start(event_timestamp)
        return window_start > self.current_window_start

    async def _flush_metrics_to_db(self):
        """Flush aggregated metrics to database"""
        db: Session = SessionLocal()
        try:
            # Calculate messages per second
            messages_per_second = self.message_count / settings.metrics_window_seconds if self.message_count > 0 else 0.0

            # Save overall message metrics
            message_metrics = MessageMetrics(
                time_window=self.current_window_start,
                window_duration_seconds=settings.metrics_window_seconds,
                message_count=self.message_count,
                messages_per_second=messages_per_second,
                active_users_count=len(self.active_users),
                unique_senders_count=len(self.unique_senders),
                active_channels_count=len(self.active_channels),
                text_messages_count=self.message_types.get('text', 0),
                image_messages_count=self.message_types.get('image', 0),
                file_messages_count=self.message_types.get('file', 0),
                system_messages_count=self.message_types.get('system', 0)
            )
            db.add(message_metrics)

            # Save per-channel metrics
            for channel_id, metrics in self.channel_metrics.items():
                channel_metric = ChannelMetrics(
                    channel_id=channel_id,
                    time_window=self.current_window_start,
                    window_duration_seconds=settings.metrics_window_seconds,
                    message_count=metrics['message_count'],
                    unique_senders_count=len(metrics['unique_senders']),
                    messages_per_second=metrics['message_count'] / settings.metrics_window_seconds,
                    created_count=metrics['created'],
                    edited_count=metrics['edited'],
                    deleted_count=metrics['deleted']
                )
                db.add(channel_metric)

            # Save per-user metrics
            for user_id, metrics in self.user_metrics.items():
                user_metric = UserMetrics(
                    user_id=user_id,
                    time_window=self.current_window_start,
                    window_duration_seconds=settings.metrics_window_seconds,
                    messages_sent=metrics['messages_sent'],
                    messages_edited=metrics['messages_edited'],
                    messages_deleted=metrics['messages_deleted'],
                    channels_active=len(metrics['channels'])
                )
                db.add(user_metric)

            db.commit()
            logger.info(f"Flushed metrics for window {self.current_window_start}: {self.message_count} messages")

        except Exception as e:
            logger.error(f"Error flushing metrics to database: {e}")
            db.rollback()
        finally:
            db.close()

    async def _periodic_flush_task(self):
        """Background task to periodically flush metrics"""
        try:
            while self.running:
                # Check every 10 seconds instead of waiting full window
                await asyncio.sleep(10)
                
                # Check if we have data and the window has passed
                if self.message_count > 0:
                    current_time = datetime.utcnow()
                    window_age = (current_time - self.current_window_start).total_seconds()
                    
                    # If current window is older than window duration, flush it
                    if window_age >= settings.metrics_window_seconds:
                        await self._flush_metrics_to_db()
                        self._reset_buffers()
                        self.current_window_start = self._get_window_start(current_time)
                        logger.info("Periodic flush completed")
        except asyncio.CancelledError:
            logger.info("Periodic flush task cancelled")
        except Exception as e:
            logger.error(f"Error in periodic flush task: {e}")

    def _reset_buffers(self):
        """Reset in-memory aggregation buffers"""
        self.message_count = 0
        self.active_users.clear()
        self.unique_senders.clear()
        self.active_channels.clear()
        self.message_types.clear()
        self.channel_metrics.clear()
        self.user_metrics.clear()

    async def process_event(self, event: dict):
        """Process a single Kafka event and update metrics"""
        try:
            event_type = event.get('event_type')

            # Extract common fields (fields are at top level, not in 'data')
            user_id = event.get('user_id')
            channel_id = event.get('channel_id')
            message_type = event.get('message_type', 'text')

            # Parse event timestamp
            event_timestamp = datetime.utcnow()  # Use current time for now

            # Check if we need to flush current window
            if self._should_flush_window(event_timestamp):
                await self._flush_metrics_to_db()
                self._reset_buffers()
                self.current_window_start = self._get_window_start(event_timestamp)

            # Skip events with missing required fields
            if not user_id or not channel_id:
                logger.warning(f"Skipping event {event_type} with missing fields: user_id={user_id}, channel_id={channel_id}")
                return

            # Update metrics based on event type
            if event_type == 'message.created':
                self.message_count += 1
                self.active_users.add(str(user_id))
                self.unique_senders.add(str(user_id))
                self.active_channels.add(str(channel_id))
                self.message_types[message_type] += 1

                # Update channel metrics
                self.channel_metrics[str(channel_id)]['message_count'] += 1
                self.channel_metrics[str(channel_id)]['unique_senders'].add(str(user_id))
                self.channel_metrics[str(channel_id)]['created'] += 1

                # Update user metrics
                self.user_metrics[str(user_id)]['messages_sent'] += 1
                self.user_metrics[str(user_id)]['channels'].add(str(channel_id))

            elif event_type == 'message.edited':
                self.channel_metrics[str(channel_id)]['edited'] += 1
                self.user_metrics[str(user_id)]['messages_edited'] += 1

            elif event_type == 'message.deleted':
                self.channel_metrics[str(channel_id)]['deleted'] += 1
                self.user_metrics[str(user_id)]['messages_deleted'] += 1

        except Exception as e:
            logger.error(f"Error processing event: {e}")

    async def start_consuming(self):
        """Start consuming messages from Kafka"""
        self.running = True
        logger.info("Analytics consumer started consuming messages")

        # Start periodic flush task
        flush_task = asyncio.create_task(self._periodic_flush_task())

        try:
            async for message in self.consumer:
                if not self.running:
                    break

                try:
                    event = message.value
                    await self.process_event(event)
                except Exception as e:
                    logger.error(f"Error processing Kafka message: {e}")

        except Exception as e:
            logger.error(f"Error in consumer loop: {e}")
        finally:
            # Cancel periodic flush task
            flush_task.cancel()
            try:
                await flush_task
            except asyncio.CancelledError:
                pass
            
            # Flush remaining metrics
            if self.message_count > 0:
                await self._flush_metrics_to_db()


# Global analytics consumer instance
analytics_consumer = AnalyticsConsumer()
