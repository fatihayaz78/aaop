"""JWT authentication — multi-tenant login, switch-service, token verification.

S-MT-02: 3-tier hierarchy (super_admin → tenant_admin → service_user).
Login by email + tenant_id (optional for super_admin).
"""

from __future__ import annotations

import json
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


# ── Models ──────────────────────────────────────────────────────

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    tenant_id: str | None = None
    tenant_name: str | None = None
    active_service_id: str | None = None
    service_ids: list[str] = []
    services: list[dict[str, str]] = []
    role: str = "service_user"


class LoginRequest(BaseModel):
    tenant_id: str | None = None
    email: str
    password: str


class SwitchServiceRequest(BaseModel):
    service_id: str


class TenantInfo(BaseModel):
    id: str
    name: str


class UserPayload(BaseModel):
    user_id: str
    tenant_id: str
    username: str
    role: str
    service_ids: list[str] = []
    active_service_id: str | None = None


# ── Helpers ─────────────────────────────────────────────────────

def _create_token(data: dict[str, Any], expires_delta: timedelta | None = None) -> str:
    settings = get_settings()
    expire = datetime.now(UTC) + (expires_delta or timedelta(minutes=settings.jwt_expire_minutes))
    to_encode = {**data, "exp": expire, "iat": datetime.now(UTC)}
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
        service_ids = payload.get("service_ids", [])
        if isinstance(service_ids, str):
            service_ids = json.loads(service_ids)
        return UserPayload(
            user_id=payload["sub"],
            tenant_id=payload.get("tenant_id", ""),
            username=payload.get("username", payload.get("email", "")),
            role=payload.get("role", "service_user"),
            service_ids=service_ids,
            active_service_id=payload.get("active_service_id"),
        )
    except JWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc


# ── Endpoints ───────────────────────────────────────────────────

@router.get("/tenants", response_model=list[TenantInfo])
async def list_tenants() -> list[TenantInfo]:
    """Public endpoint — returns active tenants for login page dropdown."""
    from backend.dependencies import get_sqlite
    sqlite = get_sqlite()
    rows = await sqlite.fetch_all(
        "SELECT id, name FROM tenants WHERE status = 'active' AND id NOT IN ('system') ORDER BY name",
    )
    return [TenantInfo(id=r["id"], name=r["name"]) for r in rows]


@router.post("/login", response_model=LoginResponse)
async def login_json(body: LoginRequest) -> LoginResponse:
    """Multi-tenant login: email + tenant_id (optional for super_admin)."""
    from backend.dependencies import get_sqlite
    sqlite = get_sqlite()

    logger.info("auth_login_attempt", email=body.email, tenant_id=body.tenant_id)

    # Find user by email
    if body.tenant_id:
        user = await sqlite.fetch_one(
            "SELECT id, tenant_id, username, password_hash, role, is_active, service_ids, active_service_id "
            "FROM users WHERE username = ? AND tenant_id = ?",
            (body.email, body.tenant_id),
        )
    else:
        # Super admin — no tenant required
        user = await sqlite.fetch_one(
            "SELECT id, tenant_id, username, password_hash, role, is_active, service_ids, active_service_id "
            "FROM users WHERE username = ? AND role = 'super_admin'",
            (body.email,),
        )

    if not user or not user.get("is_active", 1):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    if not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    service_ids = json.loads(user.get("service_ids", "[]") or "[]")
    active_service = user.get("active_service_id") or (service_ids[0] if service_ids else None)
    tenant_id = user.get("tenant_id", "")

    # Fetch tenant name
    tenant_row = await sqlite.fetch_one("SELECT name FROM tenants WHERE id = ?", (tenant_id,))
    tenant_name = tenant_row["name"] if tenant_row else ""

    # Fetch service details
    services = []
    for sid in service_ids:
        svc = await sqlite.fetch_one("SELECT id, name FROM services WHERE id = ?", (sid,))
        if svc:
            services.append({"id": svc["id"], "name": svc["name"]})

    settings = get_settings()
    token = _create_token({
        "sub": user["id"],
        "tenant_id": tenant_id,
        "username": user["username"],
        "email": user["username"],
        "role": user["role"],
        "service_ids": service_ids,
        "active_service_id": active_service,
    })

    # Update last_login
    await sqlite.execute("UPDATE users SET last_login = datetime('now') WHERE id = ?", (user["id"],))

    return LoginResponse(
        access_token=token,
        tenant_id=tenant_id,
        tenant_name=tenant_name,
        active_service_id=active_service,
        service_ids=service_ids,
        services=services,
        role=user["role"],
    )


@router.post("/switch-service", response_model=LoginResponse)
async def switch_service(
    body: SwitchServiceRequest,
    current_user: UserPayload = Depends(get_current_user),
) -> LoginResponse:
    """Switch active service — returns new JWT with updated active_service_id."""
    from backend.dependencies import get_sqlite

    # Authorization check
    if current_user.role != "super_admin" and body.service_id not in current_user.service_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Service '{body.service_id}' not in your authorized services",
        )

    sqlite = get_sqlite()

    # Verify service exists
    svc = await sqlite.fetch_one("SELECT id, name FROM services WHERE id = ?", (body.service_id,))
    if not svc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found")

    # Update user's active_service_id
    await sqlite.execute(
        "UPDATE users SET active_service_id = ? WHERE id = ?",
        (body.service_id, current_user.user_id),
    )

    # Fetch tenant + services for response
    tenant_row = await sqlite.fetch_one("SELECT name FROM tenants WHERE id = ?", (current_user.tenant_id,))
    services = []
    for sid in current_user.service_ids:
        s = await sqlite.fetch_one("SELECT id, name FROM services WHERE id = ?", (sid,))
        if s:
            services.append({"id": s["id"], "name": s["name"]})

    settings = get_settings()
    token = _create_token({
        "sub": current_user.user_id,
        "tenant_id": current_user.tenant_id,
        "username": current_user.username,
        "email": current_user.username,
        "role": current_user.role,
        "service_ids": current_user.service_ids,
        "active_service_id": body.service_id,
    })

    return LoginResponse(
        access_token=token,
        tenant_id=current_user.tenant_id,
        tenant_name=tenant_row["name"] if tenant_row else "",
        active_service_id=body.service_id,
        service_ids=current_user.service_ids,
        services=services,
        role=current_user.role,
    )


# ── Legacy OAuth2 form login (backward compat) ─────────────────

@router.post("/login/form", response_model=TokenResponse)
async def login_form(form_data: OAuth2PasswordRequestForm = Depends()) -> TokenResponse:
    """Legacy form login — kept for backward compatibility with OAuth2PasswordBearer."""
    from backend.dependencies import get_sqlite
    sqlite = get_sqlite()

    user = await sqlite.fetch_one(
        "SELECT id, tenant_id, username, password_hash, role, is_active, service_ids, active_service_id "
        "FROM users WHERE username = ?",
        (form_data.username,),
    )

    if not user or not user.get("is_active", 1):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    if not verify_password(form_data.password, user["password_hash"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    service_ids = json.loads(user.get("service_ids", "[]") or "[]")
    settings = get_settings()
    token = _create_token({
        "sub": user["id"],
        "tenant_id": user.get("tenant_id", ""),
        "username": user["username"],
        "role": user["role"],
        "service_ids": service_ids,
        "active_service_id": user.get("active_service_id"),
    })
    return TokenResponse(access_token=token, expires_in=settings.jwt_expire_minutes * 60)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(current_user: UserPayload = Depends(get_current_user)) -> TokenResponse:
    settings = get_settings()
    token = _create_token({
        "sub": current_user.user_id,
        "tenant_id": current_user.tenant_id,
        "username": current_user.username,
        "role": current_user.role,
        "service_ids": current_user.service_ids,
        "active_service_id": current_user.active_service_id,
    })
    return TokenResponse(access_token=token, expires_in=settings.jwt_expire_minutes * 60)


@router.post("/logout")
async def logout(token: str = Depends(oauth2_scheme)) -> dict[str, str]:
    _revoked_tokens.add(token)
    return {"detail": "Logged out"}


# ── Password change (S-SETTINGS-01) ────────────────────────────

class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str


def _validate_password_strength(password: str) -> str | None:
    if len(password) < 8:
        return "Password must be at least 8 characters"
    if not any(c.isupper() for c in password):
        return "Password must contain at least one uppercase letter"
    if not any(c.islower() for c in password):
        return "Password must contain at least one lowercase letter"
    if not any(c.isdigit() for c in password):
        return "Password must contain at least one digit"
    return None


@router.patch("/password")
async def change_password(
    body: PasswordChangeRequest,
    current_user: UserPayload = Depends(get_current_user),
) -> dict[str, str]:
    """Change password — verifies current, validates new, updates hash."""
    from backend.dependencies import get_sqlite
    sqlite = get_sqlite()

    user = await sqlite.fetch_one("SELECT password_hash FROM users WHERE id = ?", (current_user.user_id,))
    if not user or not verify_password(body.current_password, user["password_hash"]):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password incorrect")

    weakness = _validate_password_strength(body.new_password)
    if weakness:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=weakness)

    new_hash = hash_password(body.new_password)
    await sqlite.execute("UPDATE users SET password_hash = ? WHERE id = ?", (new_hash, current_user.user_id))
    logger.info("password_changed", user_id=current_user.user_id)

    return {"message": "Password updated"}
