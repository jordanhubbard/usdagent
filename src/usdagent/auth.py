"""Authentication utilities for usdagent."""
from __future__ import annotations

import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import Depends, HTTPException, Header, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext

_JWT_SECRET = os.environ.get("USDAGENT_JWT_SECRET") or secrets.token_hex(32)
_JWT_ALGORITHM = "HS256"
_JWT_EXPIRE_MINUTES = 60

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")


def _load_api_keys() -> set[str]:
    raw = os.environ.get("USDAGENT_API_KEYS", "")
    if not raw:
        return set()
    return {k.strip() for k in raw.split(",") if k.strip()}


def _load_users() -> dict[str, str]:
    """Return {username: hashed_password}."""
    raw = os.environ.get("USDAGENT_USERS", "admin:changeme")
    users: dict[str, str] = {}
    for entry in raw.split(","):
        entry = entry.strip()
        if ":" in entry:
            username, password = entry.split(":", 1)
            users[username.strip()] = _pwd_context.hash(password.strip())
    return users


def verify_api_key(x_api_key: str = Header(...)) -> str:
    """FastAPI dependency — validates X-API-Key header."""
    keys = _load_api_keys()
    if not keys:
        # No keys configured — open/dev mode, accept any key
        return x_api_key
    if x_api_key in keys:
        return x_api_key
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid API key",
    )


def _create_access_token(username: str) -> str:
    expire = datetime.now(tz=timezone.utc) + timedelta(minutes=_JWT_EXPIRE_MINUTES)
    payload = {"sub": username, "exp": expire}
    return jwt.encode(payload, _JWT_SECRET, algorithm=_JWT_ALGORITHM)


def authenticate_user(username: str, password: str) -> str | None:
    """Return username if credentials are valid, else None."""
    users = _load_users()
    hashed = users.get(username)
    if hashed is None:
        return None
    if not _pwd_context.verify(password, hashed):
        return None
    return username


def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]) -> str:
    """FastAPI dependency — validates Bearer token, returns username."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, _JWT_SECRET, algorithms=[_JWT_ALGORITHM])
        username: str | None = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    return username
