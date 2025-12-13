"""
Signalink API - Main FastAPI Application
Real-time distributed messaging system
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging

from .config import settings
from .routers import users, channels, messages
from .kafka import kafka_producer, kafka_consumer
from .kafka.handlers import EVENT_HANDLERS

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Lifespan context manager for startup/shutdown events
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage application lifecycle - startup and shutdown events
    """
    # Startup
    logger.info("Starting Signalink API...")

    # Start Kafka producer (non-fatal on failure)
    try:
        await kafka_producer.start()
        logger.info("Kafka producer initialized successfully")
    except Exception as e:
        logger.warning(f"Kafka producer failed to start: {e}. API will run without Kafka.")

    # Start Kafka consumer and register event handlers (non-fatal on failure)
    try:
        for event_type, handler in EVENT_HANDLERS.items():
            kafka_consumer.register_handler(event_type, handler)

        await kafka_consumer.start()
        logger.info("Kafka consumer initialized successfully")

        # Start consuming messages in background
        import asyncio
        consumer_task = asyncio.create_task(kafka_consumer.start_consuming())
        logger.info("Kafka consumer tasks started")
    except Exception as e:
        logger.warning(f"Kafka consumer failed to start: {e}. API will run without Kafka.")

    yield

    # Shutdown
    logger.info("Shutting down Signalink API...")

    # Gracefully stop Kafka consumer
    try:
        await kafka_consumer.stop()
        logger.info("Kafka consumer stopped")
    except Exception as e:
        logger.error(f"Error stopping Kafka consumer: {e}")

    # Gracefully stop Kafka producer
    try:
        await kafka_producer.stop()
        logger.info("Kafka producer stopped")
    except Exception as e:
        logger.error(f"Error stopping Kafka producer: {e}")


# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    description="Real-time distributed messaging system - Learning project",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ====================================
# Health Check & Root Endpoints
# ====================================

@app.get("/", tags=["root"])
async def root():
    """
    Root endpoint - API information
    """
    return {
        "name": settings.app_name,
        "version": "1.0.0",
        "environment": settings.environment,
        "status": "operational",
        "docs": "/docs",
        "health": "/health"
    }


@app.get("/health", tags=["health"])
async def health_check():
    """
    Health check endpoint for monitoring
    """
    return {
        "status": "healthy",
        "environment": settings.environment
    }


# ====================================
# Include Routers
# ====================================

# API v1 routes
API_V1_PREFIX = "/api/v1"

app.include_router(users.router, prefix=API_V1_PREFIX)
app.include_router(channels.router, prefix=API_V1_PREFIX)
app.include_router(messages.router, prefix=API_V1_PREFIX)


# ====================================
# Exception Handlers
# ====================================

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """
    Global exception handler for unhandled errors
    """
    logger.error(f"Unhandled exception: {exc}", exc_info=True)

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "Internal server error",
            "type": "server_error"
        }
    )


# ====================================
# Startup & Shutdown Events
# ====================================

@app.on_event("startup")
async def startup_event():
    """
    Actions to perform on application startup
    """
    logger.info(f"Starting {settings.app_name} API")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"Debug mode: {settings.debug}")

    # TODO Phase 2: Initialize Redis connection
    # TODO Phase 3: Initialize Kafka producer


@app.on_event("shutdown")
async def shutdown_event():
    """
    Actions to perform on application shutdown
    """
    logger.info(f"Shutting down {settings.app_name} API")

    # TODO Phase 2: Close Redis connections
    # TODO Phase 3: Close Kafka producer connections


# ====================================
# Development Entry Point
# ====================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
        workers=settings.api_workers
    )
