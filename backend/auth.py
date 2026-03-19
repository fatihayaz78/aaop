"""JWT authentication — login, refresh, logout, token verification."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from pydantic import BaseModel

from shared.utils.settings import get_settings

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

# In-memory revoked tokens (swap to Redis in production)
_revoked_tokens: set[str] = set()


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class UserPayload(BaseModel):
    user_id: str
    tenant_id: str
    username: str
    role: str


def _create_token(data: dict[str, Any], expires_delta: timedelta | None = None) -> str:
    settings = get_settings()
    expire = datetime.now(UTC) + (expires_delta or timedelta(minutes=settings.jwt_expire_minutes))
    to_encode = {**data, "exp": expire}
    return str(jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm))


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


async def get_current_user(token: str = Depends(oauth2_scheme)) -> UserPayload:
    settings = get_settings()
    if token in _revoked_tokens:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token revoked")
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        return UserPayload(
            user_id=payload["sub"],
            tenant_id=payload["tenant_id"],
            username=payload["username"],
            role=payload["role"],
        )
    except JWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc


@router.post("/login", response_model=TokenResponse)
async def login(form_data: OAuth2PasswordRequestForm = Depends()) -> TokenResponse:
    """Authenticate user and return JWT. DB lookup deferred to S03+."""
    # Placeholder: real user lookup will come from SQLite in later sprint
    logger.info("auth_login_attempt", username=form_data.username)
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="User DB not initialized yet")


@router.post("/refresh", response_model=TokenResponse)
async def refresh(current_user: UserPayload = Depends(get_current_user)) -> TokenResponse:
    settings = get_settings()
    token = _create_token(
        {
            "sub": current_user.user_id,
            "tenant_id": current_user.tenant_id,
            "username": current_user.username,
            "role": current_user.role,
        }
    )
    return TokenResponse(access_token=token, expires_in=settings.jwt_expire_minutes * 60)


@router.post("/logout")
async def logout(token: str = Depends(oauth2_scheme)) -> dict[str, str]:
    _revoked_tokens.add(token)
    return {"detail": "Logged out"}
