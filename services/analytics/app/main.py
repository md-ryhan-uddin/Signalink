"""
Signalink Analytics Service
Consumes Kafka events and provides analytics metrics API
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
import asyncio

from .config import settings
from .kafka_consumer import analytics_consumer
from .routers import metrics

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
    logger.info("Starting Signalink Analytics Service...")

    # Start Kafka consumer (non-fatal on failure)
    try:
        await analytics_consumer.start()
        logger.info("Analytics Kafka consumer initialized successfully")

        # Start consuming messages in background
        consumer_task = asyncio.create_task(analytics_consumer.start_consuming())
        logger.info("Analytics consumer task started")
    except Exception as e:
        logger.warning(f"Analytics consumer failed to start: {e}. Service will run without Kafka.")

    yield

    # Shutdown
    logger.info("Shutting down Signalink Analytics Service...")

    # Gracefully stop Kafka consumer
    try:
        await analytics_consumer.stop()
        logger.info("Analytics consumer stopped")
    except Exception as e:
        logger.error(f"Error stopping analytics consumer: {e}")


# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    description="Analytics service for Signalink - Real-time metrics and insights",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
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
        "environment": settings.environment,
        "service": "analytics"
    }


# ====================================
# Include Routers
# ====================================

# Include metrics router without prefix for simplicity in Phase 4
app.include_router(metrics.router)


# ====================================
# Development Entry Point
# ====================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.analytics_host,
        port=settings.analytics_port,
        reload=settings.debug
    )
