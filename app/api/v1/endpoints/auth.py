"""Authentication: login, refresh-token rotation, logout, profile, password."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import jwt
from fastapi import APIRouter, Cookie, HTTPException, Request, Response, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbDep
from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    needs_rehash,
    verify_password,
)
from app.db.base import utcnow
from app.models.auth import RefreshToken, User
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    TokenResponse,
    UserOut,
)
from app.services.audit import record_audit

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE = "biolympics_refresh"
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_MINUTES = 15


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        REFRESH_COOKIE,
        token,
        max_age=settings.refresh_token_ttl_days * 86400,
        httponly=True,
        secure=settings.is_production,
        samesite="lax",
        path="/api/v1/auth",
    )


async def _issue_tokens(db: DbDep, response: Response, user: User) -> TokenResponse:
    access = create_access_token(str(user.id), user.role_names)
    refresh, jti, expires_at = create_refresh_token(str(user.id))
    db.add(
        RefreshToken(
            jti=jti,
            user_id=user.id,
            expires_at=expires_at,
            created_at=utcnow(),
        )
    )
    await db.flush()
    _set_refresh_cookie(response, refresh)
    return TokenResponse(access_token=access, expires_in=settings.access_token_ttl_minutes * 60)


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, response: Response, db: DbDep) -> TokenResponse:
    user = (
        await db.execute(select(User).where(User.email == payload.email.lower()))
    ).scalar_one_or_none()

    # Uniform error to avoid user enumeration.
    invalid = HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")

    if user is None:
        raise invalid
    if user.locked_until and user.locked_until > datetime.now(UTC):
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Account temporarily locked due to failed logins. Try again later.",
        )
    if not user.is_active:
        raise invalid

    if not verify_password(payload.password, user.hashed_password):
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= MAX_FAILED_ATTEMPTS:
            user.locked_until = datetime.now(UTC) + timedelta(minutes=LOCKOUT_MINUTES)
            user.failed_login_attempts = 0
        await db.commit()
        raise invalid

    # Success — reset counters, opportunistically upgrade hash.
    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login_at = utcnow()
    if needs_rehash(user.hashed_password):
        user.hashed_password = hash_password(payload.password)

    tokens = await _issue_tokens(db, response, user)
    await db.commit()
    return tokens


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    response: Response,
    db: DbDep,
    biolympics_refresh: str | None = Cookie(default=None),
) -> TokenResponse:
    if not biolympics_refresh:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing refresh token")
    try:
        payload = decode_token(biolympics_refresh, "refresh")
        jti = payload["jti"]
        user_id = uuid.UUID(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError) as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid refresh token") from exc

    stored = (
        await db.execute(select(RefreshToken).where(RefreshToken.jti == jti))
    ).scalar_one_or_none()
    if stored is None or stored.revoked or stored.expires_at < datetime.now(UTC):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Refresh token revoked")

    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Unknown user")

    # Rotate: revoke the old token and issue a fresh pair.
    stored.revoked = True
    tokens = await _issue_tokens(db, response, user)
    await db.commit()
    return tokens


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    db: DbDep,
    biolympics_refresh: str | None = Cookie(default=None),
) -> Response:
    if biolympics_refresh:
        try:
            jti = decode_token(biolympics_refresh, "refresh")["jti"]
            stored = (
                await db.execute(select(RefreshToken).where(RefreshToken.jti == jti))
            ).scalar_one_or_none()
            if stored:
                stored.revoked = True
                await db.commit()
        except (jwt.PyJWTError, KeyError):
            pass
    response.delete_cookie(REFRESH_COOKIE, path="/api/v1/auth")
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/me", response_model=UserOut)
async def me(user: CurrentUser) -> UserOut:
    return UserOut(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        roles=user.role_names,
    )


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    payload: ChangePasswordRequest,
    user: CurrentUser,
    db: DbDep,
    request: Request,
) -> Response:
    if not verify_password(payload.current_password, user.hashed_password):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Current password is incorrect")
    user.hashed_password = hash_password(payload.new_password)
    # Revoke all refresh tokens — force re-login elsewhere.
    tokens = (
        (await db.execute(select(RefreshToken).where(RefreshToken.user_id == user.id)))
        .scalars()
        .all()
    )
    for t in tokens:
        t.revoked = True
    await record_audit(
        db,
        action="password.changed",
        entity_type="user",
        entity_id=user.id,
        actor_id=user.id,
        actor_email=user.email,
        request_id=getattr(request.state, "request_id", None),
    )
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
