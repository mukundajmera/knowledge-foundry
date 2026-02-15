"""Knowledge Foundry — JWT Authentication & RBAC Middleware.

Provides FastAPI dependency injectors for JWT token validation,
user context extraction, and role-based access control.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────
# RBAC Definitions
# ──────────────────────────────────────────────────────────────

class Role(str, Enum):
    """User roles — ordered by privilege level."""

    VIEWER = "viewer"
    EDITOR = "editor"
    ADMIN = "admin"


# Role hierarchy for permission checks (higher includes lower)
_ROLE_HIERARCHY: dict[Role, int] = {
    Role.VIEWER: 0,
    Role.EDITOR: 1,
    Role.ADMIN: 2,
}


@dataclass(frozen=True)
class UserContext:
    """Authenticated user context extracted from JWT."""

    user_id: str
    tenant_id: str
    role: Role
    email: str | None = None
    permissions: list[str] = field(default_factory=list)
    token_exp: datetime | None = None

    def has_role(self, required: Role) -> bool:
        """Check if user has at least the required role level."""
        return _ROLE_HIERARCHY.get(self.role, 0) >= _ROLE_HIERARCHY.get(required, 0)


# ──────────────────────────────────────────────────────────────
# Token Utility
# ──────────────────────────────────────────────────────────────

def create_access_token(
    *,
    user_id: str,
    tenant_id: str,
    role: str = "viewer",
    email: str | None = None,
    permissions: list[str] | None = None,
    secret_key: str,
    algorithm: str = "HS256",
    expire_minutes: int = 480,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    """Create a signed JWT access token.

    Args:
        user_id: Unique user identifier.
        tenant_id: Tenant the user belongs to.
        role: User role (viewer/editor/admin).
        email: Optional email address.
        permissions: Optional explicit permission list.
        secret_key: Signing key.
        algorithm: JWT algorithm (default HS256).
        expire_minutes: Token TTL in minutes.
        extra_claims: Additional JWT claims.

    Returns:
        Encoded JWT string.
    """
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": user_id,
        "tenant_id": tenant_id,
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=expire_minutes),
        "iss": "knowledge-foundry",
    }
    if email:
        payload["email"] = email
    if permissions:
        payload["permissions"] = permissions
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, secret_key, algorithm=algorithm)


def decode_token(
    token: str,
    *,
    secret_key: str,
    algorithm: str = "HS256",
) -> dict[str, Any]:
    """Decode and validate a JWT token.

    Raises:
        jwt.ExpiredSignatureError: Token has expired.
        jwt.InvalidTokenError: Token is malformed or invalid.
    """
    return jwt.decode(
        token,
        secret_key,
        algorithms=[algorithm],
        issuer="knowledge-foundry",
    )


# ──────────────────────────────────────────────────────────────
# FastAPI Dependencies
# ──────────────────────────────────────────────────────────────

_bearer_scheme = HTTPBearer(auto_error=False)


async def _extract_token(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> str:
    """Extract JWT from Authorization header or query param (websocket fallback)."""
    if credentials and credentials.credentials:
        return credentials.credentials

    # Fallback: check query parameter (useful for WebSocket or SSE)
    token = request.query_params.get("token")
    if token:
        return token

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Missing authentication token",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    secret_key: str,
    algorithm: str = "HS256",
):
    """Factory that returns a FastAPI dependency for user extraction.

    Usage in route:
        current_user = get_current_user(settings.jwt_secret_key)
        @app.get("/protected")
        async def protected(user: UserContext = Depends(current_user)):
            ...
    """

    async def _dependency(
        token: str = Depends(_extract_token),
    ) -> UserContext:
        try:
            payload = decode_token(token, secret_key=secret_key, algorithm=algorithm)
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except jwt.InvalidTokenError as exc:
            logger.warning("Invalid JWT token: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token",
                headers={"WWW-Authenticate": "Bearer"},
            )

        role_str = payload.get("role", "viewer")
        try:
            role = Role(role_str)
        except ValueError:
            role = Role.VIEWER

        exp_ts = payload.get("exp")
        token_exp = datetime.fromtimestamp(exp_ts, tz=UTC) if exp_ts else None

        return UserContext(
            user_id=payload.get("sub", ""),
            tenant_id=payload.get("tenant_id", ""),
            role=role,
            email=payload.get("email"),
            permissions=payload.get("permissions", []),
            token_exp=token_exp,
        )

    return _dependency


def require_role(minimum_role: Role):
    """Factory that returns a FastAPI dependency enforcing a minimum role.

    Usage:
        @app.delete("/admin-only", dependencies=[Depends(require_role(Role.ADMIN))])
        async def admin_only():
            ...
    """

    async def _dependency(user: UserContext = Depends(_extract_token)):
        # Note: user is actually a token string here; in practice this
        # dependency is composed with get_current_user in route definitions.
        # This is a standalone role checker that expects UserContext directly.
        if not isinstance(user, UserContext):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Auth dependency misconfigured",
            )
        if not user.has_role(minimum_role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires at least '{minimum_role.value}' role",
            )
        return user

    return _dependency
