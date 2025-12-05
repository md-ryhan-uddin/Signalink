"""
Authentication and security utilities
JWT token creation, password hashing, and user authentication
"""
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
import uuid

from .config import settings
from .database import get_db
from .models import User, UserSession
from .schemas import TokenData

# OAuth2 scheme for token authentication
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login")


def hash_password(password: str) -> str:
    """
    Hash a password using bcrypt

    Args:
        password: Plain text password

    Returns:
        Hashed password
    """
    password_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against a hash

    Args:
        plain_password: Plain text password
        hashed_password: Hashed password to verify against

    Returns:
        True if password matches, False otherwise
    """
    password_bytes = plain_password.encode('utf-8')
    hashed_bytes = hashed_password.encode('utf-8')
    return bcrypt.checkpw(password_bytes, hashed_bytes)


def create_access_token(
    user_id: uuid.UUID,
    username: str,
    expires_delta: Optional[timedelta] = None
) -> tuple[str, str]:
    """
    Create a JWT access token

    Args:
        user_id: User's UUID
        username: User's username
        expires_delta: Optional custom expiration time

    Returns:
        Tuple of (token, jti)
    """
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)

    # Generate unique JWT ID for token tracking
    jti = str(uuid.uuid4())

    to_encode = {
        "sub": str(user_id),
        "username": username,
        "exp": expire,
        "iat": datetime.utcnow(),
        "jti": jti
    }

    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)

    return encoded_jwt, jti


def decode_access_token(token: str) -> TokenData:
    """
    Decode and validate a JWT token

    Args:
        token: JWT token string

    Returns:
        TokenData with user information

    Raises:
        HTTPException: If token is invalid or expired
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        user_id_str: str = payload.get("sub")
        username: str = payload.get("username")
        jti: str = payload.get("jti")

        if user_id_str is None or username is None:
            raise credentials_exception

        user_id = uuid.UUID(user_id_str)
        token_data = TokenData(user_id=user_id, username=username, jti=jti)

    except JWTError:
        raise credentials_exception
    except ValueError:  # Invalid UUID
        raise credentials_exception

    return token_data


def authenticate_user(db: Session, username: str, password: str) -> Optional[User]:
    """
    Authenticate a user with username and password

    Args:
        db: Database session
        username: Username or email
        password: Plain text password

    Returns:
        User object if authentication successful, None otherwise
    """
    # Try to find user by username or email
    user = db.query(User).filter(
        (User.username == username) | (User.email == username)
    ).first()

    if not user:
        return None

    if not verify_password(password, user.hashed_password):
        return None

    if not user.is_active:
        return None

    return user


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    """
    Dependency to get the current authenticated user

    Args:
        token: JWT token from Authorization header
        db: Database session

    Returns:
        Current authenticated User

    Raises:
        HTTPException: If authentication fails
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # Decode token
    token_data = decode_access_token(token)

    # Get user from database
    user = db.query(User).filter(User.id == token_data.user_id).first()

    if user is None:
        raise credentials_exception

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive"
        )

    # Check if token is revoked (optional - for future implementation)
    if token_data.jti:
        session = db.query(UserSession).filter(
            UserSession.token_jti == token_data.jti,
            UserSession.is_revoked == False
        ).first()

        if not session:
            raise credentials_exception

    # Update last seen
    user.last_seen_at = datetime.utcnow()
    db.commit()

    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Dependency to get current active user
    Wrapper around get_current_user with additional active check

    Args:
        current_user: User from get_current_user dependency

    Returns:
        Current active User

    Raises:
        HTTPException: If user is not active
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive"
        )
    return current_user


def create_user_session(
    db: Session,
    user_id: uuid.UUID,
    token_jti: str,
    expires_at: datetime,
    user_agent: Optional[str] = None,
    ip_address: Optional[str] = None
) -> UserSession:
    """
    Create a user session record for token tracking

    Args:
        db: Database session
        user_id: User's UUID
        token_jti: JWT ID
        expires_at: Token expiration time
        user_agent: Optional user agent string
        ip_address: Optional IP address

    Returns:
        Created UserSession
    """
    session = UserSession(
        user_id=user_id,
        token_jti=token_jti,
        expires_at=expires_at,
        user_agent=user_agent,
        ip_address=ip_address
    )

    db.add(session)
    db.commit()
    db.refresh(session)

    return session


def revoke_token(db: Session, token_jti: str) -> bool:
    """
    Revoke a JWT token by its JTI

    Args:
        db: Database session
        token_jti: JWT ID to revoke

    Returns:
        True if token was revoked, False if not found
    """
    session = db.query(UserSession).filter(UserSession.token_jti == token_jti).first()

    if session:
        session.is_revoked = True
        db.commit()
        return True

    return False
