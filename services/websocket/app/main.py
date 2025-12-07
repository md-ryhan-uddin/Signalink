"""
WebSocket service main application
Real-time messaging with FastAPI WebSocket and Redis pub/sub
"""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, Query
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .auth import get_current_user_ws
from .database import get_db
from .redis_manager import redis_manager
from .connection_manager import connection_manager
from .websocket_handler import WebSocketHandler

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager
    Handles startup and shutdown events
    """
    # Startup
    logger.info("🚀 Starting WebSocket service...")
    try:
        await redis_manager.connect()
        logger.info("✅ WebSocket service started successfully")
    except Exception as e:
        logger.error(f"❌ Failed to start WebSocket service: {e}")
        raise

    yield

    # Shutdown
    logger.info("🛑 Shutting down WebSocket service...")
    await redis_manager.disconnect()
    logger.info("✅ WebSocket service shut down successfully")


# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    description="Real-time messaging service with WebSocket and Redis pub/sub",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Root endpoint with service information"""
    return {
        "name": settings.APP_NAME,
        "version": "1.0.0",
        "environment": settings.ENVIRONMENT,
        "status": "operational",
        "websocket_endpoint": "/ws"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    # Check Redis connection
    redis_healthy = redis_manager.redis_client is not None

    return {
        "status": "healthy" if redis_healthy else "degraded",
        "environment": settings.ENVIRONMENT,
        "redis": "connected" if redis_healthy else "disconnected",
        "active_connections": len(connection_manager.active_connections)
    }


@app.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(..., description="JWT authentication token"),
    db = Depends(get_db)
):
    """
    WebSocket endpoint for real-time messaging

    Connection URL: ws://localhost:8001/ws?token=<JWT_TOKEN>

    Client -> Server messages:
    - message.send: Send a message to a channel
    - channel.subscribe: Subscribe to channel updates
    - channel.unsubscribe: Unsubscribe from channel
    - typing.start: User started typing
    - typing.stop: User stopped typing
    - ping: Keep-alive ping

    Server -> Client messages:
    - message.receive: New message in subscribed channel
    - typing.indicator: Someone is typing
    - presence.update: User online/offline status changed
    - success: Operation successful
    - error: Operation failed
    - pong: Response to ping
    """
    user_info = None
    handler = None

    try:
        # Authenticate user
        user_info = await get_current_user_ws(token)
        user_id = user_info["user_id"]
        username = user_info["username"]

        # Accept connection and register user
        await connection_manager.connect(websocket, user_id, username)

        # Create message handler
        db_session = await anext(get_db())
        handler = WebSocketHandler(websocket, user_id, username, db_session)

        logger.info(f"WebSocket connected: {username} ({user_id})")

        # Message loop
        while True:
            # Receive message from client
            data = await websocket.receive_json()

            # Handle message
            await handler.handle_message(data)

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {user_info.get('username') if user_info else 'unknown'}")

    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
        try:
            await websocket.close(code=1011, reason=str(e))
        except:
            pass

    finally:
        # Cleanup on disconnect
        if handler:
            await handler.cleanup()
        await connection_manager.disconnect(websocket)


@app.get("/stats")
async def get_stats():
    """
    Get WebSocket service statistics

    Returns:
        dict: Service statistics
    """
    online_users = await connection_manager.get_online_users()

    return {
        "total_connections": sum(
            len(connections) for connections in connection_manager.active_connections.values()
        ),
        "unique_users_online": len(online_users),
        "active_channels": len(connection_manager.channel_members),
        "users_online": [str(user_id) for user_id in online_users]
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.WS_HOST,
        port=settings.WS_PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower()
    )
