"""
Authentication and Authorization Module
Handles JWT token generation and validation for API access.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from jose import JWTError, jwt
from pwdlib import PasswordHash
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel


# OAuth2 scheme for token URL
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Password hashing
password_hash = PasswordHash.recommended()


class Token(BaseModel):
    """OAuth2 token response model."""
    access_token: str
    token_type: str


class TokenData(BaseModel):
    """JWT token payload data."""
    username: Optional[str] = None
    api_key: Optional[str] = None


class User(BaseModel):
    """User model for authentication."""
    username: str
    disabled: bool = False


def hash_password(password: str) -> str:
    """Hash a password using Argon2."""
    return password_hash.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return password_hash.verify(plain_password, hashed_password)


def create_access_token(
    data: Dict[str, Any],
    secret_key: str,
    expires_delta: Optional[timedelta] = None,
    algorithm: str = "HS256"
) -> str:
    """
    Create a JWT access token.

    Args:
        data: Payload data to encode in the token
        secret_key: Secret key for JWT signing
        expires_delta: Token expiration time (default: 24 hours)
        algorithm: JWT algorithm (default: HS256)

    Returns:
        Encoded JWT token string
    """
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(hours=24)

    to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc)})

    encoded_jwt = jwt.encode(to_encode, secret_key, algorithm=algorithm)
    return encoded_jwt


def decode_access_token(
    token: str,
    secret_key: str,
    algorithm: str = "HS256"
) -> Dict[str, Any]:
    """
    Decode and verify a JWT access token.

    Args:
        token: JWT token string
        secret_key: Secret key for JWT verification
        algorithm: JWT algorithm (default: HS256)

    Returns:
        Decoded token payload

    Raises:
        JWTError: If token is invalid or expired
    """
    try:
        payload = jwt.decode(token, secret_key, algorithms=[algorithm])
        return payload
    except JWTError as e:
        raise JWTError(f"Token validation failed: {str(e)}")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    secret_key: str = None
) -> User:
    """
    Dependency to get the current authenticated user from JWT token.

    Args:
        token: JWT bearer token from Authorization header
        secret_key: JWT secret key (should be injected)

    Returns:
        User object with username and status

    Raises:
        HTTPException: If token is invalid or user not found
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if not secret_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="JWT secret not configured"
        )

    try:
        payload = decode_access_token(token, secret_key)
        username: str = payload.get("sub")
        api_key: str = payload.get("api_key")

        if username is None:
            raise credentials_exception

        token_data = TokenData(username=username, api_key=api_key)
    except JWTError:
        raise credentials_exception

    # In a real system, fetch user from database
    # For now, we trust the JWT token claims
    user = User(username=token_data.username, disabled=False)
    return user


def authenticate_api_key(api_key: str, stored_api_key: str) -> bool:
    """
    Authenticate an API key.

    Args:
        api_key: Provided API key
        stored_api_key: Stored API key from secrets

    Returns:
        True if API key is valid, False otherwise
    """
    return api_key == stored_api_key
