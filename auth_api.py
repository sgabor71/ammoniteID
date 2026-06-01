# ============================================================
# auth_api.py — User sync + tier endpoints
# AmmoniteID — 4-tier system: FREE, PREMIUM, EXPERT, ADMIN
# ============================================================

from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from typing import Optional
from pathlib import Path
from datetime import datetime, timedelta
import sqlite3
import os

auth_router = APIRouter(prefix="/api/auth", tags=["auth"])

# Permanent admin UID — always has ADMIN tier regardless of DB
PERMANENT_ADMIN_UID = "16fjKKd4XPOD8PMZhGQSHmSAdPO2"

VALID_TIERS = ("FREE", "PREMIUM", "EXPERT", "ADMIN")

def get_db_path():
    if os.getenv('DATABASE_PATH'):
        return Path(os.getenv('DATABASE_PATH'))
    elif os.getenv('RENDER'):
        return Path('/tmp/ammonite.db')
    elif os.path.exists('/data'):
        return Path('/data/ammonite.db')
    else:
        return Path(__file__).parent / 'ammonite.db'

DB_PATH = get_db_path()
DB_PATH.parent.mkdir(exist_ok=True, parents=True)

SERVICE_ACCOUNT = Path(__file__).parent / 'firebase_service_account.json'

_firebase_ready = False
try:
    if SERVICE_ACCOUNT.exists():
        import firebase_admin
        from firebase_admin import credentials, auth as fb_auth
        if not firebase_admin._apps:
            cred = credentials.Certificate(str(SERVICE_ACCOUNT))
            firebase_admin.initialize_app(cred)
        _firebase_ready = True
        print("✓ Firebase Admin SDK initialised")
    else:
        print("⚠️ Running in TRUST MODE — no token verification.")
except Exception as e:
    print(f"⚠️ Firebase Admin init failed ({e}) — TRUST MODE.")


def _db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def _verify_token(id_token: str) -> dict:
    if _firebase_ready and id_token:
        from firebase_admin import auth as fb_auth
        decoded = fb_auth.verify_id_token(id_token)
        return {"uid": decoded["uid"], "email": decoded.get("email"), "name": decoded.get("name")}
    return {}


def _resolve_tier(row) -> str:
    """
    Read tier from the unified 'tier' column.
    Falls back to premium_status/is_admin for migration safety.
    Permanent admin UID always returns ADMIN.
    """
    uid = row["firebase_uid"] if "firebase_uid" in row.keys() else None
    if uid == PERMANENT_ADMIN_UID:
        return "ADMIN"

    # New unified tier column
    tier = row["tier"] if "tier" in row.keys() else None
    if tier and tier in VALID_TIERS:
        return tier

    # Migration fallback: read old columns
    is_admin = row["is_admin"] if "is_admin" in row.keys() else 0
    if is_admin:
        return "ADMIN"

    premium_status = row["premium_status"] if "premium_status" in row.keys() else "FREE"
    if premium_status == "PREMIUM":
        return "PREMIUM"

    return "FREE"


# ── Request models ───────────────────────────────────────────
class SyncRequest(BaseModel):
    uid: Optional[str] = None
    email: Optional[str] = None
    display_name: Optional[str] = None


# ============================================================
# POST /api/auth/sync
# Called after Firebase login — creates/updates user record
# NEVER resets tier for existing users
# ============================================================
@auth_router.post("/sync")
async def sync_user(body: SyncRequest, authorization: Optional[str] = Header(None)):
    uid = email = name = None
    token = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1]

    try:
        verified = _verify_token(token) if token else {}
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid Firebase token.")

    if verified:
        uid = verified["uid"]
        email = verified.get("email")
        name = verified.get("name")
    else:
        uid, email, name = body.uid, body.email, body.display_name

    if not uid:
        raise HTTPException(status_code=400, detail="No user id provided.")

    # Permanent admin always gets ADMIN
    starting_tier = "ADMIN" if uid == PERMANENT_ADMIN_UID else "FREE"

    now = datetime.utcnow().isoformat()
    conn = _db()
    c = conn.cursor()

    c.execute("SELECT * FROM users WHERE firebase_uid = ?", (uid,))
    existing = c.fetchone()

    if existing:
        # Update profile only — NEVER change tier
        c.execute("""
            UPDATE users
            SET email = COALESCE(?, email),
                display_name = COALESCE(?, display_name),
                last_login = ?
            WHERE firebase_uid = ?
        """, (email, name, now, uid))

        # Ensure permanent admin has ADMIN tier
        if uid == PERMANENT_ADMIN_UID:
            c.execute("UPDATE users SET tier = 'ADMIN' WHERE firebase_uid = ?", (uid,))

        tier = _resolve_tier(existing)
        created = False
    else:
        c.execute("""
            INSERT INTO users
            (user_id, firebase_uid, email, display_name,
             tier, premium_status, premium_expires, created_at, last_login)
            VALUES (?, ?, ?, ?, ?, 'FREE', NULL, ?, ?)
        """, (uid, uid, email, name, starting_tier, now, now))
        tier = starting_tier
        created = True

    conn.commit()
    conn.close()

    return {
        "status": "ok",
        "created": created,
        "user": {
            "uid": uid,
            "email": email,
            "display_name": name,
            "tier": tier,
            "is_premium": tier in ("PREMIUM", "EXPERT", "ADMIN"),
            "is_expert": tier in ("EXPERT", "ADMIN"),
            "is_admin": tier == "ADMIN",
        },
        "verified": bool(verified),
    }


# ============================================================
# GET /api/auth/me/{uid}
# Returns current tier from DB — used by all pages on load
# ============================================================
@auth_router.get("/me/{uid}")
async def get_me(uid: str):
    # Permanent admin safety net
    conn = _db()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE firebase_uid = ?", (uid,))
    row = c.fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="User not found. Call /api/auth/sync first.")

    tier = _resolve_tier(row)

    # Auto-downgrade PREMIUM only if expired (EXPERT/ADMIN never expire)
    if tier == "PREMIUM":
        expires = row["premium_expires"] if "premium_expires" in row.keys() else None
        if expires:
            try:
                if datetime.fromisoformat(expires) < datetime.utcnow():
                    tier = "FREE"
            except Exception:
                pass

    return {
        "uid": row["firebase_uid"],
        "email": row["email"],
        "display_name": row["display_name"],
        "tier": tier,
        "is_premium": tier in ("PREMIUM", "EXPERT", "ADMIN"),
        "is_expert": tier in ("EXPERT", "ADMIN"),
        "is_admin": tier == "ADMIN",
        "created_at": row["created_at"],
    }


# ============================================================
# POST /api/auth/set-tier/{uid}
# Set any tier — called by Stripe webhook and admin panel
# ============================================================
@auth_router.post("/set-tier/{uid}")
async def set_tier(uid: str, tier: str, expires: Optional[str] = None):
    tier = tier.upper()
    if tier not in VALID_TIERS:
        raise HTTPException(status_code=400, detail=f"tier must be one of: {VALID_TIERS}")

    conn = _db()
    c = conn.cursor()
    c.execute("SELECT 1 FROM users WHERE firebase_uid = ?", (uid,))
    if not c.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="User not found.")

    c.execute("""
        UPDATE users SET tier = ?, premium_status = ?, premium_expires = ?
        WHERE firebase_uid = ?
    """, (tier, tier, expires, uid))
    conn.commit()
    conn.close()

    return {"status": "ok", "uid": uid, "tier": tier}


# ============================================================
# ADMIN: GET /api/auth/admin/users
# Returns all users with tier info for admin Users tab
# ============================================================
@auth_router.get("/admin/users")
async def admin_list_users():
    conn = _db()
    c = conn.cursor()

    c.execute("""
        SELECT user_id, firebase_uid, email, display_name,
               tier, premium_status, is_admin, premium_expires,
               created_at, last_login
        FROM users ORDER BY created_at DESC
    """)
    users = [dict(r) for r in c.fetchall()]

    counts = {}
    try:
        c.execute("""
            SELECT user_id, COUNT(*) AS n FROM identifications
            WHERE user_id IS NOT NULL GROUP BY user_id
        """)
        for r in c.fetchall():
            counts[r["user_id"]] = r["n"]
    except Exception:
        pass

    conn.close()

    now = datetime.utcnow()
    out = []
    for u in users:
        # Resolve tier using same logic
        class _FakeRow:
            def __init__(self, d): self._d = d
            def __getitem__(self, k): return self._d.get(k)
            def keys(self): return self._d.keys()

        tier = u.get("tier") or ("ADMIN" if u.get("is_admin") else None) or u.get("premium_status") or "FREE"
        if tier not in VALID_TIERS:
            tier = "FREE"
        if u.get("firebase_uid") == PERMANENT_ADMIN_UID:
            tier = "ADMIN"

        inactive = False
        if u["last_login"]:
            try:
                if (now - datetime.fromisoformat(u["last_login"])).days >= 30:
                    inactive = True
            except Exception:
                pass

        out.append({
            "uid": u["firebase_uid"],
            "email": u["email"] or "",
            "display_name": u["display_name"] or "",
            "tier": tier,
            "premium_expires": u["premium_expires"],
            "created_at": u["created_at"],
            "last_login": u["last_login"],
            "id_count": counts.get(u["user_id"], 0),
            "inactive": inactive,
        })

    total = len(out)
    tier_counts = {t: sum(1 for u in out if u["tier"] == t) for t in VALID_TIERS}

    return {
        "summary": {
            "total": total,
            **{t.lower(): tier_counts[t] for t in VALID_TIERS},
            "conversion": round((tier_counts["PREMIUM"] / total * 100), 1) if total else 0,
        },
        "users": out,
    }


# ============================================================
# ADMIN: GET /api/auth/admin/user/{uid}
# Full detail for one user
# ============================================================
@auth_router.get("/admin/user/{uid}")
async def admin_user_detail(uid: str):
    conn = _db()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE firebase_uid = ?", (uid,))
    row = c.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="User not found.")
    user = dict(row)

    recent = []
    total_ids = 0
    try:
        c.execute("""
            SELECT id, timestamp, top_family, top_genus, family_score, scenario
            FROM identifications WHERE user_id = ?
            ORDER BY timestamp DESC LIMIT 20
        """, (uid,))
        recent = [dict(r) for r in c.fetchall()]
        c.execute("SELECT COUNT(*) AS n FROM identifications WHERE user_id = ?", (uid,))
        total_ids = c.fetchone()["n"]
    except Exception:
        pass

    conn.close()

    tier = user.get("tier") or ("ADMIN" if user.get("is_admin") else None) or user.get("premium_status") or "FREE"
    if uid == PERMANENT_ADMIN_UID:
        tier = "ADMIN"

    return {
        "uid": user["firebase_uid"],
        "email": user["email"],
        "display_name": user["display_name"],
        "tier": tier,
        "premium_expires": user["premium_expires"],
        "created_at": user["created_at"],
        "last_login": user["last_login"],
        "total_identifications": total_ids,
        "recent_identifications": recent,
    }


# ============================================================
# ADMIN: POST /api/auth/admin/grant-trial/{uid}
# Give user N days PREMIUM trial
# ============================================================
@auth_router.post("/admin/grant-trial/{uid}")
async def admin_grant_trial(uid: str, days: int = 7):
    conn = _db()
    c = conn.cursor()
    c.execute("SELECT 1 FROM users WHERE firebase_uid = ?", (uid,))
    if not c.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="User not found.")
    expires = (datetime.utcnow() + timedelta(days=days)).isoformat()
    c.execute("""
        UPDATE users SET tier='PREMIUM', premium_status='PREMIUM', premium_expires=?
        WHERE firebase_uid=?
    """, (expires, uid))
    conn.commit()
    conn.close()
    return {"status": "ok", "uid": uid, "tier": "PREMIUM", "premium_expires": expires, "days": days}


# ============================================================
# ADMIN: DELETE /api/auth/admin/user/{uid}
# ============================================================
@auth_router.delete("/admin/user/{uid}")
async def admin_delete_user(uid: str):
    conn = _db()
    c = conn.cursor()
    c.execute("SELECT 1 FROM users WHERE firebase_uid = ?", (uid,))
    if not c.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="User not found.")
    c.execute("DELETE FROM users WHERE firebase_uid = ?", (uid,))
    try:
        c.execute("UPDATE identifications SET user_id = NULL WHERE user_id = ?", (uid,))
    except Exception:
        pass
    conn.commit()
    conn.close()
    return {"status": "ok", "deleted": uid}


# ============================================================
# ADMIN CHECK (kept for backward compat)
# ============================================================
@auth_router.get("/admin-check/{uid}")
async def check_admin_status(uid: str):
    if uid == PERMANENT_ADMIN_UID:
        return {"status": "ok", "is_admin": True, "tier": "ADMIN"}

    conn = _db()
    c = conn.cursor()
    c.execute("SELECT tier, is_admin FROM users WHERE firebase_uid = ?", (uid,))
    row = c.fetchone()
    conn.close()

    if not row:
        return {"status": "not_found", "is_admin": False, "tier": "FREE"}

    tier = row["tier"] if row["tier"] in VALID_TIERS else ("ADMIN" if row["is_admin"] else "FREE")
    return {"status": "ok", "is_admin": tier == "ADMIN", "tier": tier}


@auth_router.get("/admin-check/check-any")
async def check_if_any_admin_exists():
    conn = _db()
    c = conn.cursor()
    try:
        c.execute("SELECT COUNT(*) as count FROM users WHERE tier = 'ADMIN' OR is_admin = 1")
        row = c.fetchone()
        exists = row["count"] > 0 if row else False
    except Exception:
        exists = False
    conn.close()
    return {"exists": exists}


# ============================================================
# PROMOTE ADMIN (kept for emergency use)
# ============================================================
@auth_router.post("/promote-admin/{uid}")
async def promote_to_admin(uid: str, secret_key: Optional[str] = Header(None)):
    SETUP_KEY = os.getenv('ADMIN_SETUP_KEY', 'ammonite-admin-setup')
    if secret_key != SETUP_KEY:
        raise HTTPException(status_code=403, detail="Invalid setup key")

    now = datetime.utcnow().isoformat()
    conn = _db()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE firebase_uid = ?", (uid,))
    existing = c.fetchone()

    if existing:
        c.execute("UPDATE users SET tier = 'ADMIN', is_admin = 1 WHERE firebase_uid = ?", (uid,))
    else:
        c.execute("""
            INSERT INTO users
            (user_id, firebase_uid, email, display_name, tier, premium_status,
             premium_expires, created_at, last_login, is_admin)
            VALUES (?, ?, ?, ?, 'ADMIN', 'FREE', NULL, ?, ?, 1)
        """, (uid, uid, 'admin', 'Admin', now, now))

    conn.commit()
    conn.close()
    return {"status": "ok", "message": "User promoted to ADMIN"}


# ============================================================
# ADMIN TEST USER
# ============================================================
@auth_router.post("/admin/test-user")
async def admin_create_test_user(body: SyncRequest):
    email = body.email
    if not email:
        raise HTTPException(status_code=400, detail="Email required")

    test_uid = None
    try:
        if _firebase_ready:
            from firebase_admin import auth as fb_auth
            user = fb_auth.create_user(
                email=email,
                password=f"TestPass{int(datetime.utcnow().timestamp())}!",
                display_name=body.display_name or email.split('@')[0],
            )
            test_uid = user.uid
    except Exception as e:
        print(f"⚠️ Firebase Admin not available: {e}")
        test_uid = f"test_{int(datetime.utcnow().timestamp() * 1000)}"

    conn = _db()
    c = conn.cursor()
    now = datetime.utcnow().isoformat()
    try:
        c.execute("""
            INSERT INTO users
            (user_id, firebase_uid, email, display_name, tier, premium_status, created_at, last_login)
            VALUES (?, ?, ?, ?, 'FREE', 'FREE', ?, ?)
        """, (test_uid, test_uid, email, body.display_name or email.split('@')[0], now, now))
        conn.commit()
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=400, detail=f"User creation failed: {str(e)}")

    conn.close()
    return {
        "status": "ok",
        "created": True,
        "user": {"uid": test_uid, "email": email, "tier": "FREE"},
    }


# ── Helper other modules can import ──────────────────────────
def get_user_tier(uid: str) -> str:
    """Return tier for a uid (FREE if unknown). Used by other modules."""
    if not uid:
        return "FREE"
    if uid == PERMANENT_ADMIN_UID:
        return "ADMIN"
    try:
        conn = _db()
        c = conn.cursor()
        c.execute("SELECT tier, premium_status, is_admin, premium_expires FROM users WHERE firebase_uid = ?", (uid,))
        row = c.fetchone()
        conn.close()
        if not row:
            return "FREE"
        tier = row["tier"] if row["tier"] in VALID_TIERS else ("ADMIN" if row["is_admin"] else row["premium_status"] or "FREE")
        if tier == "PREMIUM" and row["premium_expires"]:
            if datetime.fromisoformat(row["premium_expires"]) < datetime.utcnow():
                return "FREE"
        return tier
    except Exception:
        return "FREE"
