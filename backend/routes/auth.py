from fastapi import APIRouter, Response, Request
from datetime import datetime, timezone
import logging

from db import db
from models import (
    LoginRequest, ChangePasswordRequest, CreateUserRequest,
    ResetPasswordRequest, APIResponse
)
from services.auth_service import (
    hash_password, verify_password, create_access_token, get_current_user
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/auth/login")
async def login(request: LoginRequest, response: Response):
    try:
        user = await db.users.find_one({"username": request.username}, {"_id": 0})
        if not user:
            return APIResponse(success=False, error="Invalid username or password")
        if not verify_password(request.password, user["password_hash"]):
            return APIResponse(success=False, error="Invalid username or password")

        token = create_access_token(user["username"], user["username"], user["role"])
        response.set_cookie(
            key="access_token", value=token,
            httponly=True, secure=False, samesite="lax",
            max_age=86400, path="/"
        )
        return APIResponse(
            success=True,
            message="Login successful",
            data={
                "username": user["username"],
                "name": user.get("name", ""),
                "role": user["role"],
                "token": token
            }
        )
    except Exception as e:
        logger.error(f"Login error: {e}")
        return APIResponse(success=False, error=str(e))


@router.get("/auth/me")
async def get_me(request: Request):
    try:
        user = await get_current_user(request, db)
        if not user:
            return APIResponse(success=False, error="Not authenticated")
        return APIResponse(success=True, data={
            "username": user["username"],
            "name": user.get("name", ""),
            "role": user["role"]
        })
    except Exception as e:
        return APIResponse(success=False, error=str(e))


@router.post("/auth/logout")
async def logout(response: Response):
    response.delete_cookie("access_token", path="/")
    return APIResponse(success=True, message="Logged out successfully")


@router.post("/auth/change-password")
async def change_password(req: ChangePasswordRequest, request: Request):
    try:
        user = await get_current_user(request, db)
        if not user:
            return APIResponse(success=False, error="Not authenticated")
        full_user = await db.users.find_one({"username": user["username"]})
        if not verify_password(req.current_password, full_user["password_hash"]):
            return APIResponse(success=False, error="Current password is incorrect")
        await db.users.update_one(
            {"username": user["username"]},
            {"$set": {"password_hash": hash_password(req.new_password)}}
        )
        return APIResponse(success=True, message="Password changed successfully")
    except Exception as e:
        logger.error(f"Change password error: {e}")
        return APIResponse(success=False, error=str(e))


@router.post("/auth/reset-password")
async def reset_password(req: ResetPasswordRequest, request: Request):
    try:
        user = await get_current_user(request, db)
        if not user or user["role"] != "admin":
            return APIResponse(success=False, error="Admin access required")
        target = await db.users.find_one({"username": req.username})
        if not target:
            return APIResponse(success=False, error="User not found")
        await db.users.update_one(
            {"username": req.username},
            {"$set": {"password_hash": hash_password(req.new_password)}}
        )
        return APIResponse(success=True, message=f"Password reset for {req.username}")
    except Exception as e:
        logger.error(f"Reset password error: {e}")
        return APIResponse(success=False, error=str(e))


@router.post("/auth/users")
async def create_user(req: CreateUserRequest, request: Request):
    try:
        user = await get_current_user(request, db)
        if not user or user["role"] != "admin":
            return APIResponse(success=False, error="Admin access required")
        existing = await db.users.find_one({"username": req.username})
        if existing:
            return APIResponse(success=False, error="Username already exists")
        await db.users.insert_one({
            "username": req.username,
            "password_hash": hash_password(req.password),
            "name": req.name,
            "role": req.role,
            "created_at": datetime.now(timezone.utc).isoformat()
        })
        return APIResponse(success=True, message=f"User '{req.username}' created", data={"username": req.username, "role": req.role})
    except Exception as e:
        logger.error(f"Create user error: {e}")
        return APIResponse(success=False, error=str(e))


@router.get("/auth/users")
async def list_users(request: Request):
    try:
        user = await get_current_user(request, db)
        if not user or user["role"] != "admin":
            return APIResponse(success=False, error="Admin access required")
        users = await db.users.find({}, {"_id": 0, "password_hash": 0}).to_list(100)
        return APIResponse(success=True, data={"users": users})
    except Exception as e:
        return APIResponse(success=False, error=str(e))


@router.delete("/auth/users/{username}")
async def delete_user(username: str, request: Request):
    try:
        user = await get_current_user(request, db)
        if not user or user["role"] != "admin":
            return APIResponse(success=False, error="Admin access required")
        if username == user["username"]:
            return APIResponse(success=False, error="Cannot delete yourself")
        result = await db.users.delete_one({"username": username})
        if result.deleted_count == 0:
            return APIResponse(success=False, error="User not found")
        return APIResponse(success=True, message=f"User '{username}' deleted")
    except Exception as e:
        return APIResponse(success=False, error=str(e))
