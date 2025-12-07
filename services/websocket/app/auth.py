"""
WebSocket authentication utilities
Validates JWT tokens for WebSocket connections
"""
from jose import JWTError, jwt
from fastapi import WebSocketException, status
from typing import Optional
from uuid import UUID

from .config import settings


def decode_token(token: str) -> dict:
    """
    Decode and validate JWT token

    Args:
        token: JWT token string

    Returns:
        dict: Decoded token payload

    Raises:
        WebSocketException: If token is invalid
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        return payload
    except JWTError:
        raise WebSocketException(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="Invalid authentication token"
        )


async def get_current_user_ws(token: str) -> dict:
    """
    Get current user from WebSocket token

    Args:
        token: JWT token from WebSocket query params

    Returns:
        dict: User info with user_id and username

    Raises:
        WebSocketException: If token is invalid or missing required fields
    """
    payload = decode_token(token)

    user_id: Optional[str] = payload.get("sub")
    username: Optional[str] = payload.get("username")

    if user_id is None or username is None:
        raise WebSocketException(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="Invalid token payload"
        )

    try:
        user_uuid = UUID(user_id)
    except ValueError:
        raise WebSocketException(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="Invalid user ID format"
        )

    return {
        "user_id": user_uuid,
        "username": username,
        "jti": payload.get("jti")
    }
