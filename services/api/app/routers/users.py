"""
User management endpoints
Registration, profile management, user search
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from datetime import datetime, timedelta

from ..database import get_db
from ..models import User
from ..schemas import (
    UserCreate, UserResponse, UserUpdate, UserLogin, Token
)
from ..auth import (
    hash_password, authenticate_user, create_access_token,
    get_current_user, create_user_session
)
from ..config import settings

router = APIRouter(prefix="/users", tags=["users"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register_user(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    """
    Register a new user account

    - **username**: Unique username (3-50 characters)
    - **email**: Valid email address
    - **password**: Password (min 8 characters)
    - **full_name**: Optional full name
    """
    # Check if username already exists
    result = await db.execute(select(User).filter(User.username == user_data.username))
    existing_user = result.scalar_one_or_none()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered"
        )

    # Check if email already exists
    result = await db.execute(select(User).filter(User.email == user_data.email))
    existing_email = result.scalar_one_or_none()
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    # Create new user
    hashed_pwd = hash_password(user_data.password)
    new_user = User(
        username=user_data.username,
        email=user_data.email,
        hashed_password=hashed_pwd,
        full_name=user_data.full_name
    )

    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    return new_user


@router.post("/login", response_model=Token)
async def login(user_credentials: UserLogin, db: AsyncSession = Depends(get_db)):
    """
    Authenticate user and return JWT token

    - **username**: Username or email
    - **password**: User password
    """
    # Authenticate user
    user = await authenticate_user(db, user_credentials.username, user_credentials.password)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Create access token
    access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
    access_token, jti = create_access_token(
        user_id=user.id,
        username=user.username,
        expires_delta=access_token_expires
    )

    # Create session record
    await create_user_session(
        db=db,
        user_id=user.id,
        token_jti=jti,
        expires_at=datetime.utcnow() + access_token_expires
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": settings.access_token_expire_minutes * 60  # seconds
    }


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(current_user: User = Depends(get_current_user)):
    """
    Get current authenticated user's profile
    """
    return current_user


@router.put("/me", response_model=UserResponse)
async def update_current_user_profile(
    user_update: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Update current user's profile

    - **full_name**: Update full name
    - **avatar_url**: Update avatar URL
    """
    if user_update.full_name is not None:
        current_user.full_name = user_update.full_name

    if user_update.avatar_url is not None:
        current_user.avatar_url = user_update.avatar_url

    await db.commit()
    await db.refresh(current_user)

    return current_user


@router.get("/{username}", response_model=UserResponse)
async def get_user_by_username(
    username: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get user profile by username
    """
    result = await db.execute(select(User).filter(User.username == username))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    return user


@router.get("/", response_model=List[UserResponse])
async def search_users(
    query: str = "",
    skip: int = 0,
    limit: int = 20,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Search users by username or email

    - **query**: Search query (username or email)
    - **skip**: Number of records to skip (pagination)
    - **limit**: Maximum number of records to return
    """
    stmt = select(User)

    if query:
        search_pattern = f"%{query}%"
        stmt = stmt.filter(
            (User.username.ilike(search_pattern)) |
            (User.email.ilike(search_pattern))
        )

    stmt = stmt.offset(skip).limit(limit)
    result = await db.execute(stmt)
    users = result.scalars().all()

    return users
