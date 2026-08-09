"""
Authentication Router
"""
from fastapi import APIRouter, HTTPException, Depends, Header
from datetime import datetime, timezone
import os
import uuid

from .dependencies import (
    UserCreate, UserLogin, UserResponse, TokenResponse, RoleUpdate,
    hash_password, verify_password, create_token, get_current_user,
    get_db, check_permission, ROLES
)

# Optional auth security services
try:
    from backend.services.boundary_control import BoundaryControl
except ImportError:
    BoundaryControl = None

try:
    from backend.services.replay_guard import ReplayGuard
except ImportError:
    ReplayGuard = None

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.get("/bootstrap-status")
async def bootstrap_status():
    """Return public first-run authentication state for the login UI."""
    db = get_db()
    user_count = await db.users.count_documents({})
    admin_count = await db.users.count_documents({"role": "admin"})
    required_token = os.environ.get("SETUP_TOKEN", "").strip()
    return {
        "user_count": user_count,
        "admin_count": admin_count,
        "setup_required": admin_count == 0,
        "setup_token_required": bool(required_token),
    }

@router.post("/register", response_model=TokenResponse)
async def register(user_data: UserCreate):
    db = get_db()
    normalized_email = user_data.email.strip().lower()
    existing = await db.users.find_one({"email": normalized_email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # First user ever registered becomes an admin automatically.
    # We check both total user count and existing admin count so the
    # role assignment is correct even if a non-admin seed account
    # was somehow created out-of-band before the first real registration.
    user_count = await db.users.count_documents({})
    admin_count = await db.users.count_documents({"role": "admin"})
    role = "admin" if (user_count == 0 or admin_count == 0) else "analyst"

    user_id = str(uuid.uuid4())
    user_doc = {
        "id": user_id,
        "email": normalized_email,
        "password": hash_password(user_data.password),
        "name": user_data.name,
        "role": role,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.users.insert_one(user_doc)
    
    token = create_token(user_id, normalized_email)
    return TokenResponse(
        access_token=token,
        user=UserResponse(
            id=user_id,
            email=normalized_email,
            name=user_data.name,
            role=role,
            created_at=user_doc["created_at"]
        )
    )

@router.post("/login", response_model=TokenResponse)
async def login(credentials: UserLogin):
    db = get_db()
    normalized_email = credentials.email.strip().lower()
    user = await db.users.find_one({"email": normalized_email}, {"_id": 0})
    if not user or not verify_password(credentials.password, user["password"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    token = create_token(user["id"], user["email"])
    return TokenResponse(
        access_token=token,
        user=UserResponse(
            id=user["id"],
            email=user["email"],
            name=user["name"],
            role=user.get("role", "analyst"),
            created_at=user["created_at"]
        )
    )

@router.get("/me", response_model=UserResponse)
async def get_me(current_user: dict = Depends(get_current_user)):
    return UserResponse(**current_user)


@router.post("/setup", response_model=TokenResponse)
async def setup_admin(
    user_data: UserCreate,
    x_setup_token: str = Header(default="", alias="X-Setup-Token"),
):
    """
    One-time endpoint to create the initial admin account.

    When the SETUP_TOKEN environment variable is set, the matching value must
    be supplied in the ``X-Setup-Token`` request header – providing an extra
    layer of protection before the first admin account has been created.

    Returns 409 if any admin account already exists, ensuring this endpoint
    cannot be used to add more admins after initial setup.
    """
    # Optional setup token guard
    required_token = os.environ.get("SETUP_TOKEN", "").strip()
    if required_token:
        if not x_setup_token or x_setup_token != required_token:
            raise HTTPException(status_code=403, detail="Invalid or missing X-Setup-Token header")

    db = get_db()
    existing_admin = await db.users.find_one({"role": "admin"})
    if existing_admin:
        raise HTTPException(
            status_code=409,
            detail="Admin account already exists. Use /auth/login to sign in."
        )

    normalized_email = user_data.email.strip().lower()
    existing_user = await db.users.find_one({"email": normalized_email})
    if existing_user:
        # Promote the already-registered account to admin
        await db.users.update_one(
            {"email": normalized_email},
            {"$set": {"role": "admin"}}
        )
        user_id = existing_user["id"]
        name = existing_user["name"]
        created_at = existing_user["created_at"]
    else:
        user_id = str(uuid.uuid4())
        created_at = datetime.now(timezone.utc).isoformat()
        name = user_data.name
        await db.users.insert_one({
            "id": user_id,
            "email": normalized_email,
            "password": hash_password(user_data.password),
            "name": name,
            "role": "admin",
            "created_at": created_at,
        })

    token = create_token(user_id, normalized_email)
    return TokenResponse(
        access_token=token,
        user=UserResponse(
            id=user_id,
            email=normalized_email,
            name=name,
            role="admin",
            created_at=created_at,
        )
    )

# User management endpoints (admin)
users_router = APIRouter(prefix="/users", tags=["Users"])

@users_router.patch("/{user_id}/role")
async def update_user_role(user_id: str, role_update: RoleUpdate, current_user: dict = Depends(check_permission("manage_users"))):
    """Update user role (admin only)"""
    db = get_db()
    if role_update.role not in ROLES:
        raise HTTPException(status_code=400, detail=f"Invalid role. Valid roles: {list(ROLES.keys())}")
    
    result = await db.users.update_one(
        {"id": user_id},
        {"$set": {"role": role_update.role}}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    return {"message": "Role updated", "role": role_update.role}

@users_router.get("")
async def list_users(current_user: dict = Depends(check_permission("manage_users"))):
    """List all users (admin only)"""
    db = get_db()
    users = await db.users.find({}, {"_id": 0, "password": 0}).to_list(100)
    return users


@router.post("/boundary/enforce")
async def enforce_access_boundary(
    principal_id: str,
    resource_type: str,
    action: str,
    current_user: dict = Depends(check_permission("write")),
):
    """Enforce access boundary for a principal."""
    if not BoundaryControl:
        raise HTTPException(status_code=501, detail="Boundary control not available")
    
    try:
        bc = BoundaryControl()
        decision = await bc.enforce_boundary(principal_id, resource_type, action)
        return {
            "success": True,
            "principal_id": principal_id,
            "allowed": decision.get("allowed", False),
            "reason": decision.get("reason"),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Boundary enforcement failed: {str(e)}")


@router.post("/replay/guard")
async def guard_against_replay(
    request_hash: str,
    timestamp: int,
    current_user: dict = Depends(check_permission("write")),
):
    """Guard against replay attacks."""
    if not ReplayGuard:
        raise HTTPException(status_code=501, detail="Replay guard not available")
    
    try:
        guard = ReplayGuard()
        is_replay = await guard.is_replay(request_hash, timestamp)
        return {
            "success": True,
            "is_replay": is_replay,
            "request_hash": request_hash,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Replay guard check failed: {str(e)}")
