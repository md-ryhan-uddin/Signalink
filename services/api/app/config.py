"""
Configuration management for Signalink API
Uses pydantic-settings for environment variable validation
"""
from pydantic_settings import BaseSettings
from typing import List
import json


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # Application
    app_name: str = "Signalink"
    environment: str = "development"
    debug: bool = True
    log_level: str = "INFO"

    # API Configuration
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_workers: int = 1

    # Database Configuration
    database_url: str
    db_pool_size: int = 5
    db_max_overflow: int = 10

    # JWT Authentication
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    # Redis Configuration
    redis_url: str
    redis_max_connections: int = 10

    # Kafka Configuration (Phase 3)
    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_topic_messages: str = "signalink-messages"
    kafka_topic_notifications: str = "signalink-notifications"
    kafka_topic_analytics: str = "signalink-analytics"
    kafka_consumer_group: str = "signalink-consumers"

    # CORS Configuration
    cors_origins: str = '["http://localhost:3000","http://localhost:8000"]'

    # Rate Limiting
    rate_limit_enabled: bool = True
    rate_limit_per_minute: int = 60

    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS origins from JSON string"""
        return json.loads(self.cors_origins)

    class Config:
        env_file = ".env"
        case_sensitive = False


# Global settings instance
settings = Settings()
