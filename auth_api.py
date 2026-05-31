# ============================================================
# auth_api.py — User sync + tier endpoints
# AmmoniteID
# ============================================================
#
# WHAT THIS DOES
#   The frontend logs in with Firebase (client-side). After login,
#   it sends the Firebase ID token here. We verify it, then create
#   or update a matching row in our `users` table.
#
#   We store ONLY identity + tier. No photos, no collection data.
#
# SECURITY
#   We verify the Firebase ID token with the Firebase Admin SDK so a
#   user cannot impersonate someone else or flip themselves to PREMIUM.
#   If the Admin SDK isn't configured yet, we fall back to "trust mode"
#   (uses the uid/email the client sends) so you can develop locally.
#   ⚠️ Turn verification ON before going live (see SETUP below).
#
# SETUP (to enable real verification)
#   1. pip install firebase-admin
#   2. In Firebase console → Project settings → Service accounts →
#      "Generate new private key" → save as  firebase_service_account.json
#      in this folder.
#   3. Restart the server. It will auto-detect the file.
# ============================================================

from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from typing import Optional
from pathlib import Path
from datetime import datetime
import sqlite3
import os

auth_router = APIRouter(prefix="/api/auth", tags=["auth"])

# DB path (mirror main.py's logic)
def get_db_path():
    """Determine database path based on environment (same as main.py)."""
    # Check for explicit DATABASE_PATH (Hostim)
    if os.getenv('DATABASE_PATH'):
        return Path(os.getenv('DATABASE_PATH'))
    # Check for Render environment
    elif os.getenv('RENDER'):
        return Path('/tmp/ammonite.db')
    # Check for /data mount (Hostim fallback)
    elif os.path.exists('/data'):
        return Path('/data/ammonite.db')
    # Local development
    else:
        return Path(__file__).parent / 'ammonite.db'

DB_PATH = get_db_path()

# Ensure parent directory exists
DB_PATH.parent.mkdir(exist_ok=True, parents=True)

SERVICE_ACCOUNT = Path(__file__).parent / 'firebase_service_account.json'

# ── Try to initialise Firebase Admin (optional) ──────────────
_firebase_ready = False
try:
    if SERVICE_ACCOUNT.exists():
        import firebase_admin
        from firebase_admin import credentials, auth as fb_auth
        if not firebase_admin._apps:
            cred = credentials.Certificate(str(SERVICE_ACCOUNT))
            firebase_admin.initialize_app(cred)
        _firebase_ready = True
        print("✓ Firebase Admin SDK initialised — ID token verification ON")
    else:
        print("⚠️ firebase_service_account.json not found — running in TRUST MODE "
              "(no token verification). Fine for local dev, NOT for production.")
except Exception as e:
    print(f"⚠️ Firebase Admin init failed ({e}) — running in TRUST MODE.")


def _db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def _verify_token(id_token: str) -> dict:
    """
    Returns a dict with at least 'uid', and 'email'/'name' if available.
    In trust mode (no Admin SDK), we cannot verify — caller must supply
    uid/email in the request body instead.
    """
    if _firebase_ready and id_token:
        from firebase_admin import auth as fb_auth
        decoded = fb_auth.verify_id_token(id_token)
        return {
            "uid": decoded["uid"],
            "email": decoded.get("email"),
            "name": decoded.get("name"),
        }
    return {}


# ── Request models ───────────────────────────────────────────
class SyncRequest(BaseModel):
    # In trust mode the client sends these directly.
    # In verified mode they're ignored in favour of the token.
    uid: Optional[str] = None
    email: Optional[str] = None
    display_name: Optional[str] = None


# ============================================================
# ENDPOINTS
# ============================================================

@auth_router.post("/sync")
async def sync_user(body: SyncRequest, authorization: Optional[str] = Header(None)):
    """
    Create or update the user record after Firebase login.
    Frontend calls this once after a successful sign-in.

    Header:  Authorization: Bearer <firebase_id_token>   (preferred)
    Body:    { uid, email, display_name }                (trust-mode fallback)

    Returns the user's current tier so the UI can gate features immediately.
    """
    # Resolve identity — verified token wins; otherwise use body.
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
        # trust mode
        uid = body.uid
        email = body.email
        name = body.display_name

    if not uid:
        raise HTTPException(status_code=400, detail="No user id provided.")

    now = datetime.utcnow().isoformat()
    conn = _db()
    c = conn.cursor()

    c.execute("SELECT * FROM users WHERE firebase_uid = ?", (uid,))
    existing = c.fetchone()

    if existing:
        # Update profile bits + last login. NEVER change tier here.
        c.execute("""
            UPDATE users
            SET email = COALESCE(?, email),
                display_name = COALESCE(?, display_name),
                last_login = ?
            WHERE firebase_uid = ?
        """, (email, name, now, uid))
        tier = existing["premium_status"] or "FREE"
        expires = existing["premium_expires"]
        created = False
    else:
        # New user — always starts FREE.
        c.execute("""
            INSERT INTO users
            (user_id, firebase_uid, email, display_name,
             premium_status, premium_expires, created_at, last_login)
            VALUES (?, ?, ?, ?, 'FREE', NULL, ?, ?)
        """, (uid, uid, email, name, now, now))
        tier = "FREE"
        expires = None
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
            "premium_expires": expires,
            "is_premium": tier == "PREMIUM",
        },
        "verified": bool(verified),
    }


@auth_router.get("/me/{uid}")
async def get_me(uid: str):
    """
    Look up a user's tier/profile by Firebase uid.
    Used by pages to decide what to show (e.g. enable My Collection).
    """
    conn = _db()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE firebase_uid = ?", (uid,))
    row = c.fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="User not found. Call /api/auth/sync first.")

    # Auto-downgrade if premium has expired
    tier = row["premium_status"] or "FREE"
    expires = row["premium_expires"]
    if tier == "PREMIUM" and expires:
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
        "premium_expires": expires,
        "is_premium": tier == "PREMIUM",
        "created_at": row["created_at"],
    }


@auth_router.post("/set-tier/{uid}")
async def set_tier(uid: str, tier: str, expires: Optional[str] = None):
    """
    ADMIN/INTERNAL: set a user's tier.
    Later, Stripe webhooks will call this to flip FREE <-> PREMIUM.
    NOT exposed to normal users in the UI.

    tier: 'FREE' or 'PREMIUM'
    expires: ISO datetime string (optional, for premium end date)
    """
    tier = tier.upper()
    if tier not in ("FREE", "PREMIUM"):
        raise HTTPException(status_code=400, detail="tier must be FREE or PREMIUM.")

    conn = _db()
    c = conn.cursor()
    c.execute("SELECT 1 FROM users WHERE firebase_uid = ?", (uid,))
    if not c.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="User not found.")

    c.execute("""
        UPDATE users SET premium_status = ?, premium_expires = ?
        WHERE firebase_uid = ?
    """, (tier, expires, uid))
    conn.commit()
    conn.close()

    return {"status": "ok", "uid": uid, "tier": tier, "premium_expires": expires}


# ============================================================
# ADMIN USER MANAGEMENT (for admin.html Users tab)
# ============================================================

@auth_router.get("/admin/users")
async def admin_list_users():
    """
    Return all users with activity stats for the admin Users tab.
    Includes identification counts and computed flags (expiring soon,
    inactive) so the front-end can highlight them.
    """
    conn = _db()
    c = conn.cursor()

    # Pull users
    c.execute("""
        SELECT user_id, firebase_uid, email, display_name,
               premium_status, premium_expires, created_at, last_login
        FROM users
        ORDER BY created_at DESC
    """)
    users = [dict(r) for r in c.fetchall()]

    # Identification counts per user (one query, then map)
    counts = {}
    try:
        c.execute("""
            SELECT user_id, COUNT(*) AS n
            FROM identifications
            WHERE user_id IS NOT NULL
            GROUP BY user_id
        """)
        for r in c.fetchall():
            counts[r["user_id"]] = r["n"]
    except Exception:
        pass

    conn.close()

    now = datetime.utcnow()
    out = []
    for u in users:
        tier = u["premium_status"] or "FREE"
        expires = u["premium_expires"]

        expiring_soon = False
        expired = False
        if tier == "PREMIUM" and expires:
            try:
                exp = datetime.fromisoformat(expires)
                days_left = (exp - now).days
                if exp < now:
                    expired = True
                    tier = "FREE"  # auto-downgrade view
                elif days_left <= 7:
                    expiring_soon = True
            except Exception:
                pass

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
            "premium_expires": expires,
            "created_at": u["created_at"],
            "last_login": u["last_login"],
            "id_count": counts.get(u["user_id"], 0),
            "expiring_soon": expiring_soon,
            "expired": expired,
            "inactive": inactive,
        })

    # Summary
    total = len(out)
    premium = sum(1 for u in out if u["tier"] == "PREMIUM")
    free = total - premium
    week_ago = now.replace(microsecond=0)
    new_week = 0
    for u in out:
        if u["created_at"]:
            try:
                if (now - datetime.fromisoformat(u["created_at"])).days <= 7:
                    new_week += 1
            except Exception:
                pass

    return {
        "summary": {
            "total": total,
            "free": free,
            "premium": premium,
            "new_this_week": new_week,
            "conversion": round((premium / total * 100), 1) if total else 0,
            "expiring_soon": sum(1 for u in out if u["expiring_soon"]),
            "inactive": sum(1 for u in out if u["inactive"]),
        },
        "users": out,
    }


@auth_router.get("/admin/user/{uid}")
async def admin_user_detail(uid: str):
    """Full detail for one user (for the detail popup)."""
    conn = _db()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE firebase_uid = ?", (uid,))
    row = c.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="User not found.")

    user = dict(row)

    # Recent identifications by this user
    recent = []
    try:
        c.execute("""
            SELECT id, timestamp, top_family, top_genus, family_score, scenario
            FROM identifications
            WHERE user_id = ?
            ORDER BY timestamp DESC
            LIMIT 20
        """, (uid,))
        recent = [dict(r) for r in c.fetchall()]
        c.execute("SELECT COUNT(*) AS n FROM identifications WHERE user_id = ?", (uid,))
        total_ids = c.fetchone()["n"]
    except Exception:
        total_ids = 0

    conn.close()
    return {
        "uid": user["firebase_uid"],
        "email": user["email"],
        "display_name": user["display_name"],
        "tier": user["premium_status"] or "FREE",
        "premium_expires": user["premium_expires"],
        "created_at": user["created_at"],
        "last_login": user["last_login"],
        "total_identifications": total_ids,
        "recent_identifications": recent,
    }


@auth_router.post("/admin/grant-trial/{uid}")
async def admin_grant_trial(uid: str, days: int = 7):
    """Give a user N days of PREMIUM from now (trials, comps, refunds)."""
    from datetime import timedelta
    conn = _db()
    c = conn.cursor()
    c.execute("SELECT 1 FROM users WHERE firebase_uid = ?", (uid,))
    if not c.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="User not found.")
    expires = (datetime.utcnow() + timedelta(days=days)).isoformat()
    c.execute("UPDATE users SET premium_status='PREMIUM', premium_expires=? WHERE firebase_uid=?",
              (expires, uid))
    conn.commit()
    conn.close()
    return {"status": "ok", "uid": uid, "tier": "PREMIUM", "premium_expires": expires, "days": days}


@auth_router.delete("/admin/user/{uid}")
async def admin_delete_user(uid: str):
    """
    Delete a user record (GDPR 'delete my data' requests).
    Note: this removes the backend record only. Their on-device
    collection is theirs to delete on the device. Firebase Auth
    account should also be deleted separately in the Firebase console
    or via Admin SDK if you want a full wipe.
    """
    conn = _db()
    c = conn.cursor()
    c.execute("SELECT 1 FROM users WHERE firebase_uid = ?", (uid,))
    if not c.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="User not found.")
    c.execute("DELETE FROM users WHERE firebase_uid = ?", (uid,))
    # Optionally null out their identifications' user_id (keep the stats, drop the link)
    try:
        c.execute("UPDATE identifications SET user_id = NULL WHERE user_id = ?", (uid,))
    except Exception:
        pass
    c.execute("DELETE FROM sessions WHERE user_id = ?", (uid,))
    conn.commit()
    conn.close()
    return {"status": "ok", "deleted": uid}


@auth_router.post("/admin/test-user")
async def admin_create_test_user(body: SyncRequest):
    """
    ADMIN ONLY: Create a test user directly (for testing, demos, etc).
    
    ⚠️ LIMITATION: This creates a DB record but NOT a Firebase account.
    The test user cannot actually log in via Firebase.
    
    TO FIX THIS (requires Firebase Admin SDK):
    1. pip install firebase-admin
    2. Download firebase_service_account.json (see auth_api.py setup docs)
    3. Uncomment the Firebase Admin SDK code below
    4. Restart server
    
    Then test users can actually authenticate.
    """
    email = body.email
    name = body.display_name
    if not email:
        raise HTTPException(status_code=400, detail="Email required")

    # Try to use Firebase Admin SDK if available
    test_uid = None
    try:
        if _firebase_ready:
            from firebase_admin import auth as fb_auth
            # Create Firebase user
            user = fb_auth.create_user(
                email=email,
                password=f"TestPass{int(datetime.utcnow().timestamp())}!",
                display_name=name or email.split('@')[0],
            )
            test_uid = user.uid
    except Exception as e:
        print(f"⚠️ Firebase Admin SDK not available for test user: {e}")
        # Fallback: generate a fake UID (test user won't be able to log in)
        test_uid = f"test_{int(datetime.utcnow().timestamp() * 1000)}"

    conn = _db()
    c = conn.cursor()
    now = datetime.utcnow().isoformat()

    try:
        c.execute("""
            INSERT INTO users
            (user_id, firebase_uid, email, display_name, premium_status, created_at, last_login)
            VALUES (?, ?, ?, ?, 'FREE', ?, ?)
        """, (test_uid, test_uid, email, name or email.split('@')[0], now, now))
        conn.commit()
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=400, detail=f"User creation failed: {str(e)}")

    conn.close()
    return {
        "status": "ok",
        "created": True,
        "firebase_admin_available": _firebase_ready,
        "user": {
            "uid": test_uid,
            "email": email,
            "display_name": name or email.split('@')[0],
            "tier": "FREE",
        },
        "note": "If firebase_admin not available, UID is fake and user cannot log in via Firebase."
    }


# ============================================================
# ADMIN ROLE
# ============================================================

@auth_router.get("/admin-check/check-any")
async def check_if_any_admin_exists():
    """Check if any admin exists (used by setup page)."""
    conn = _db()
    c = conn.cursor()
    c.execute("PRAGMA table_info(users)")
    columns = [col[1] for col in c.fetchall()]
    
    if "is_admin" not in columns:
        return {"exists": False}
    
    c.execute("SELECT COUNT(*) as count FROM users WHERE is_admin = 1")
    row = c.fetchone()
    conn.close()
    
    exists = row["count"] > 0 if row else False
    return {"exists": exists}


@auth_router.get("/admin-check/{uid}")
async def check_admin_status(uid: str):
    """Check if user has admin role."""
    conn = _db()
    c = conn.cursor()
    c.execute("PRAGMA table_info(users)")
    columns = [col[1] for col in c.fetchall()]
    
    if "is_admin" not in columns:
        c.execute("ALTER TABLE users ADD COLUMN is_admin INTEGER DEFAULT 0")
        conn.commit()
    
    c.execute("SELECT is_admin FROM users WHERE firebase_uid = ?", (uid,))
    row = c.fetchone()
    conn.close()

    if not row:
        return {"status": "not_found", "is_admin": False}
    
    is_admin = bool(row["is_admin"])
    return {"status": "ok", "is_admin": is_admin}


@auth_router.post("/promote-admin/{uid}")
async def promote_to_admin(uid: str, secret_key: Optional[str] = Header(None)):
    """Promote user to admin (requires secret key for security)."""
    SETUP_KEY = os.getenv('ADMIN_SETUP_KEY', 'ammonite-admin-setup')
    
    if secret_key != SETUP_KEY:
        raise HTTPException(status_code=403, detail="Invalid setup key")
    
    now = datetime.utcnow().isoformat()
    conn = _db()
    c = conn.cursor()
    
    # Ensure is_admin column exists
    c.execute("PRAGMA table_info(users)")
    columns = [col[1] for col in c.fetchall()]
    if "is_admin" not in columns:
        c.execute("ALTER TABLE users ADD COLUMN is_admin INTEGER DEFAULT 0")
    
    # Check if user exists in DB
    c.execute("SELECT * FROM users WHERE firebase_uid = ?", (uid,))
    existing = c.fetchone()
    
    if existing:
        # User exists — just flip admin flag
        c.execute("UPDATE users SET is_admin = 1 WHERE firebase_uid = ?", (uid,))
    else:
        # User doesn't exist — create them AND set admin
        c.execute("""
            INSERT INTO users
            (user_id, firebase_uid, email, display_name,
             premium_status, premium_expires, created_at, last_login, is_admin)
            VALUES (?, ?, ?, ?, 'FREE', NULL, ?, ?, 1)
        """, (uid, uid, 'admin', 'Admin', now, now))
    
    conn.commit()
    conn.close()
    
    return {"status": "ok", "message": "User promoted to admin"}

# ── Helper other modules can import ──────────────────────────
def get_user_tier(uid: str) -> str:
    """Return 'FREE' or 'PREMIUM' for a uid (FREE if unknown/expired)."""
    if not uid:
        return "FREE"
    try:
        conn = _db()
        c = conn.cursor()
        c.execute("SELECT premium_status, premium_expires FROM users WHERE firebase_uid = ?", (uid,))
        row = c.fetchone()
        conn.close()
        if not row:
            return "FREE"
        tier = row["premium_status"] or "FREE"
        if tier == "PREMIUM" and row["premium_expires"]:
            if datetime.fromisoformat(row["premium_expires"]) < datetime.utcnow():
                return "FREE"
        return tier
    except Exception:
        return "FREE"


# ── To wire into main.py ─────────────────────────────────────
"""
from auth_api import auth_router
app.include_router(auth_router)
"""
