from __future__ import annotations

import logging

import bcrypt as _bcrypt
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.models.documents import UserDocument

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["auth"])


class SignupRequest(BaseModel):
    name: str
    email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


class AuthResponse(BaseModel):
    user_id: str
    name: str
    email: str


@router.post("/signup", response_model=AuthResponse)
async def signup(body: SignupRequest):
    if not body.email or not body.password:
        raise HTTPException(status_code=400, detail="Email and password are required.")

    existing = await UserDocument.find_one(UserDocument.email == body.email)
    if existing:
        raise HTTPException(status_code=409, detail="An account with this email already exists.")

    hashed = _bcrypt.hashpw(body.password.encode("utf-8"), _bcrypt.gensalt()).decode("utf-8")
    user = UserDocument(
        name=body.name.strip() or "Guest",
        email=body.email.strip().lower(),
        password_hash=hashed,
    )
    await user.insert()
    log.info("New user signed up: %s (%s)", user.user_id, user.email)

    return AuthResponse(user_id=user.user_id, name=user.name, email=user.email)


@router.post("/login", response_model=AuthResponse)
async def login(body: LoginRequest):
    if not body.email or not body.password:
        raise HTTPException(status_code=400, detail="Email and password are required.")

    user = await UserDocument.find_one(UserDocument.email == body.email.strip().lower())
    if not user or not user.password_hash:
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    if not _bcrypt.checkpw(body.password.encode("utf-8"), user.password_hash.encode("utf-8")):
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    log.info("User logged in: %s (%s)", user.user_id, user.email)
    return AuthResponse(user_id=user.user_id, name=user.name, email=user.email)
