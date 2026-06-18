"""Aggregate router for API v1."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import ws
from app.api.v1.endpoints import admin, auth, public, push

api_router = APIRouter()
api_router.include_router(public.router)
api_router.include_router(auth.router)
api_router.include_router(push.router)
api_router.include_router(admin.router)
api_router.include_router(ws.router)
