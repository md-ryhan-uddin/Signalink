"""
Analytics Service Configuration
"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # Application
    app_name: str = "Signalink Analytics"
    environment: str = "development"
    debug: bool = True
    log_level: str = "INFO"

    # Analytics Service
    analytics_host: str = "0.0.0.0"
    analytics_port: int = 8002

    # Database Configuration
    database_url: str = "postgresql://signalink:signalink123@postgres-signalink:5432/signalink"

    # Kafka Configuration
    kafka_enabled: bool = True
    kafka_bootstrap_servers: str = "kafka-signalink:9092"
    kafka_topic_messages: str = "signalink.messages"
    kafka_topic_analytics: str = "signalink.analytics"
    kafka_consumer_group: str = "analytics-consumers"

    # Metrics Configuration
    metrics_window_seconds: int = 60  # 1 minute rolling window
    metrics_retention_days: int = 30  # Keep metrics for 30 days

    class Config:
        env_file = ".env"
        case_sensitive = False


# Global settings instance
settings = Settings()
