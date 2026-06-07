# ============================================================
# features_api.py — Feature gating (Free vs Premium switches)
# AmmoniteID
# ============================================================
#
# WHAT THIS DOES
#   Stores a simple rule for each app feature: who can use it?
#     'everyone'  -> all logged-in users (Free and Premium)
#     'premium'   -> Premium only (Free sees it locked)
#     'free'      -> Free only (rare, but supported)
#     'off'       -> nobody / disabled for everyone
#
#   You edit these from the admin page. They survive restarts
#   (stored in the feature_flags table). No code changes needed
#   to move a feature between Free and Premium.
#
# HOW PAGES USE IT
#   The frontend fetches /api/features once, then for each feature
#   checks: does this user's tier satisfy the rule? If not, the
#   feature is shown locked with "Upgrade to Premium to unlock".
# ============================================================

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict
from pathlib import Path
import sqlite3
import os

# Import shared database configuration
from database import DB_PATH

features_router = APIRouter(prefix="/api", tags=["features"])


# ── The full list of gateable features + sensible defaults ───
# key: short id used in code/HTML.  label: shown in admin.
# rule: default audience.  desc: helper text in admin.
DEFAULT_FEATURES = [
    ("save_collection", "Save to My Collection", "premium",
     "Let users save identified fossils to their personal collection (stored on their device)."),
    ("manage_collection", "Manage Collection", "premium",
     "Edit, organise, favourite and delete saved fossils."),
    ("offline_mode", "Offline Mode", "premium",
     "Download the model and identify with no signal."),
    ("export_pdf", "Export to PDF", "premium",
     "Export the collection as a PDF ('My Fossil Collection')."),
    ("export_csv", "Export to CSV", "premium",
     "Export the collection as a CSV file (also the backup method)."),
    ("map_view", "Location Map View", "premium",
     "Show finds on a map (Free users get text location only)."),
    ("advanced_stats", "Advanced Stats", "premium",
     "Rarity scores and deeper insights."),
    ("photo_editing", "Photo Editing", "premium",
     "Crop, rotate, brightness tools."),
    ("comparison_mode", "Comparison Mode", "premium",
     "Side-by-side reference comparison."),
    ("theme_switcher", "Theme Switcher", "premium",
     "Switch between Natural and Modern themes."),
    ("keep_forever", "Keep Forever", "premium",
     "Disable the 30-day auto-delete for saved fossils."),
    ("custom_location", "Custom Location Naming", "premium",
     "Name locations manually."),
    ("show_ads", "Show Ads", "everyone",
     "Who sees partner ad banners. Set to 'everyone' for ads for all, or 'free' to make Premium ad-free."),
]


def _db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_feature_flags():
    """Create the table and seed defaults (safe to call repeatedly)."""
    conn = _db()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS feature_flags (
            feature_key TEXT PRIMARY KEY,
            label       TEXT NOT NULL,
            rule        TEXT NOT NULL DEFAULT 'premium',
            description TEXT,
            updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    for key, label, rule, desc in DEFAULT_FEATURES:
        c.execute("""
            INSERT OR IGNORE INTO feature_flags (feature_key, label, rule, description)
            VALUES (?, ?, ?, ?)
        """, (key, label, rule, desc))
    conn.commit()
    conn.close()


# Run on import so the table always exists
try:
    init_feature_flags()
except Exception as e:
    print(f"⚠️ feature_flags init: {e}")


# ── Models ───────────────────────────────────────────────────
class FlagUpdate(BaseModel):
    rule: str  # 'everyone' | 'premium' | 'free' | 'off'


# ============================================================
# PUBLIC: pages read this to know the rules
# ============================================================
@features_router.get("/features")
async def get_features():
    """Return all feature rules as a simple {key: rule} map plus full details."""
    conn = _db()
    c = conn.cursor()
    c.execute("SELECT feature_key, label, rule, description FROM feature_flags ORDER BY feature_key")
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return {
        "rules": {r["feature_key"]: r["rule"] for r in rows},
        "features": rows,
    }


@features_router.get("/features/check/{feature_key}")
async def check_feature(feature_key: str, tier: str = "FREE"):
    """
    Convenience: can a user of `tier` use `feature_key`?
    Returns {allowed: bool, rule: '...'}.
    """
    conn = _db()
    c = conn.cursor()
    c.execute("SELECT rule FROM feature_flags WHERE feature_key = ?", (feature_key,))
    row = c.fetchone()
    conn.close()
    if not row:
        return {"allowed": True, "rule": "everyone", "unknown": True}
    rule = row["rule"]
    allowed = _is_allowed(rule, tier)
    return {"allowed": allowed, "rule": rule}


def _is_allowed(rule: str, tier: str) -> bool:
    tier = (tier or "FREE").upper()
    if rule == "everyone":
        return True
    if rule == "off":
        return False
    if rule == "premium":
        return tier == "PREMIUM"
    if rule == "free":
        return tier == "FREE"
    return True


# ============================================================
# ADMIN: edit the rules (used by the Feature Gating tab)
# ============================================================
@features_router.get("/admin/features")
async def admin_get_features():
    """Same as /features but explicit admin route."""
    return await get_features()


@features_router.post("/admin/features/{feature_key}")
async def admin_update_feature(feature_key: str, body: FlagUpdate):
    """Update a single feature's rule."""
    rule = body.rule.lower()
    if rule not in ("everyone", "premium", "free", "off"):
        raise HTTPException(status_code=400, detail="rule must be everyone, premium, free, or off")
    conn = _db()
    c = conn.cursor()
    c.execute("SELECT 1 FROM feature_flags WHERE feature_key = ?", (feature_key,))
    if not c.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Unknown feature")
    c.execute("UPDATE feature_flags SET rule = ?, updated_at = CURRENT_TIMESTAMP WHERE feature_key = ?",
              (rule, feature_key))
    conn.commit()
    conn.close()
    return {"status": "ok", "feature_key": feature_key, "rule": rule}


@features_router.post("/admin/features/reset")
async def admin_reset_features():
    """Reset all features back to their default rules."""
    conn = _db()
    c = conn.cursor()
    for key, label, rule, desc in DEFAULT_FEATURES:
        c.execute("UPDATE feature_flags SET rule = ?, updated_at = CURRENT_TIMESTAMP WHERE feature_key = ?",
                  (rule, key))
    conn.commit()
    conn.close()
    return {"status": "ok", "message": "Features reset to defaults"}


# ── Helper for other backend modules ─────────────────────────
def feature_allowed(feature_key: str, tier: str) -> bool:
    """Backend-side gate check (e.g. to block a premium-only API for Free users)."""
    try:
        conn = _db()
        c = conn.cursor()
        c.execute("SELECT rule FROM feature_flags WHERE feature_key = ?", (feature_key,))
        row = c.fetchone()
        conn.close()
        if not row:
            return True
        return _is_allowed(row["rule"], tier)
    except Exception:
        return True


# ── Wire into main.py ────────────────────────────────────────
"""
from features_api import features_router
app.include_router(features_router)
"""
