"""
WebSocket service configuration
"""
from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    """WebSocket service settings"""

    # Application
    APP_NAME: str = "Signalink WebSocket"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"

    # WebSocket Configuration
    WS_HOST: str = "0.0.0.0"
    WS_PORT: int = 8001
    WS_PING_INTERVAL: int = 30
    WS_PING_TIMEOUT: int = 10

    # Database Configuration
    DATABASE_URL: str
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10

    # Redis Configuration
    REDIS_URL: str = "redis://redis-signalink:6379/0"
    REDIS_MAX_CONNECTIONS: int = 10

    # JWT Authentication
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # CORS Configuration
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:8000"]

    # Rate Limiting
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_PER_MINUTE: int = 60

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
