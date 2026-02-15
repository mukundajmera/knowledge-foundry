"""Tests for JWT Auth & RBAC middleware — src/api/middleware/auth.py."""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta

import jwt
import pytest

from src.api.middleware.auth import (
    Role,
    UserContext,
    create_access_token,
    decode_token,
)

SECRET = "test-secret-key-32-chars-minimum"
ALG = "HS256"


# ──────────────────────────────────────────────────
# Token creation & decoding
# ──────────────────────────────────────────────────

class TestCreateToken:
    def test_creates_valid_token(self) -> None:
        token = create_access_token(
            user_id="user-1",
            tenant_id="tenant-1",
            role="editor",
            email="test@example.com",
            secret_key=SECRET,
        )
        payload = jwt.decode(token, SECRET, algorithms=[ALG], issuer="knowledge-foundry")
        assert payload["sub"] == "user-1"
        assert payload["tenant_id"] == "tenant-1"
        assert payload["role"] == "editor"
        assert payload["email"] == "test@example.com"
        assert payload["iss"] == "knowledge-foundry"
        assert "exp" in payload
        assert "iat" in payload

    def test_custom_expiry(self) -> None:
        token = create_access_token(
            user_id="u", tenant_id="t", secret_key=SECRET, expire_minutes=1,
        )
        payload = jwt.decode(token, SECRET, algorithms=[ALG], issuer="knowledge-foundry")
        iat = payload["iat"]
        exp = payload["exp"]
        assert exp - iat == 60  # 1 minute

    def test_extra_claims(self) -> None:
        token = create_access_token(
            user_id="u", tenant_id="t", secret_key=SECRET,
            extra_claims={"custom_field": "value123"},
        )
        payload = jwt.decode(token, SECRET, algorithms=[ALG], issuer="knowledge-foundry")
        assert payload["custom_field"] == "value123"

    def test_permissions_included(self) -> None:
        token = create_access_token(
            user_id="u", tenant_id="t", secret_key=SECRET,
            permissions=["read:documents", "write:documents"],
        )
        payload = jwt.decode(token, SECRET, algorithms=[ALG], issuer="knowledge-foundry")
        assert payload["permissions"] == ["read:documents", "write:documents"]


class TestDecodeToken:
    def test_decode_valid(self) -> None:
        token = create_access_token(
            user_id="user-1", tenant_id="tenant-1", secret_key=SECRET,
        )
        payload = decode_token(token, secret_key=SECRET)
        assert payload["sub"] == "user-1"

    def test_expired_token_raises(self) -> None:
        token = create_access_token(
            user_id="u", tenant_id="t", secret_key=SECRET, expire_minutes=0,
        )
        # Token created with 0 minutes → already expired
        # Need to create a token with exp in the past
        now = datetime.now(UTC)
        payload = {
            "sub": "u", "tenant_id": "t", "role": "viewer",
            "iat": now - timedelta(hours=1),
            "exp": now - timedelta(minutes=1),
            "iss": "knowledge-foundry",
        }
        token = jwt.encode(payload, SECRET, algorithm=ALG)
        with pytest.raises(jwt.ExpiredSignatureError):
            decode_token(token, secret_key=SECRET)

    def test_wrong_secret_raises(self) -> None:
        token = create_access_token(
            user_id="u", tenant_id="t", secret_key=SECRET,
        )
        with pytest.raises(jwt.InvalidSignatureError):
            decode_token(token, secret_key="wrong-secret")

    def test_wrong_issuer_raises(self) -> None:
        now = datetime.now(UTC)
        payload = {
            "sub": "u", "tenant_id": "t", "role": "viewer",
            "iat": now, "exp": now + timedelta(hours=1),
            "iss": "wrong-issuer",
        }
        token = jwt.encode(payload, SECRET, algorithm=ALG)
        with pytest.raises(jwt.InvalidIssuerError):
            decode_token(token, secret_key=SECRET)


# ──────────────────────────────────────────────────
# UserContext & RBAC
# ──────────────────────────────────────────────────

class TestUserContext:
    def test_viewer_has_viewer_role(self) -> None:
        ctx = UserContext(user_id="u", tenant_id="t", role=Role.VIEWER)
        assert ctx.has_role(Role.VIEWER)
        assert not ctx.has_role(Role.EDITOR)
        assert not ctx.has_role(Role.ADMIN)

    def test_editor_has_editor_and_viewer(self) -> None:
        ctx = UserContext(user_id="u", tenant_id="t", role=Role.EDITOR)
        assert ctx.has_role(Role.VIEWER)
        assert ctx.has_role(Role.EDITOR)
        assert not ctx.has_role(Role.ADMIN)

    def test_admin_has_all_roles(self) -> None:
        ctx = UserContext(user_id="u", tenant_id="t", role=Role.ADMIN)
        assert ctx.has_role(Role.VIEWER)
        assert ctx.has_role(Role.EDITOR)
        assert ctx.has_role(Role.ADMIN)

    def test_frozen_dataclass(self) -> None:
        ctx = UserContext(user_id="u", tenant_id="t", role=Role.VIEWER)
        with pytest.raises(AttributeError):
            ctx.user_id = "other"  # type: ignore[misc]


class TestRoleEnum:
    def test_role_values(self) -> None:
        assert Role.VIEWER.value == "viewer"
        assert Role.EDITOR.value == "editor"
        assert Role.ADMIN.value == "admin"

    def test_role_from_string(self) -> None:
        assert Role("viewer") == Role.VIEWER
        assert Role("admin") == Role.ADMIN
