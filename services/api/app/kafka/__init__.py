"""
Kafka integration for event streaming
"""
from .producer import kafka_producer
from .consumer import kafka_consumer
from .events import MessageEvent, NotificationEvent, AnalyticsEvent, PresenceEvent

__all__ = [
    "kafka_producer",
    "kafka_consumer",
    "MessageEvent",
    "NotificationEvent",
    "AnalyticsEvent",
    "PresenceEvent",
]
