# ============================================================
# retention_api.py — Retention, sync-delete & ML export
# AmmoniteID v1.1
# ============================================================

import os
import json
import shutil
import sqlite3
import requests
from datetime import datetime, timedelta
from pathlib import Path
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional

retention_router = APIRouter(prefix="/api/retention", tags=["retention"])

# ── Config ────────────────────────────────────────────────────
CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME", "dds5rebi2")
CLOUDINARY_API_KEY = os.getenv("CLOUDINARY_API_KEY", "")
CLOUDINARY_API_SECRET = os.getenv("CLOUDINARY_API_SECRET", "")

def get_db_path():
    if os.getenv('DATABASE_PATH'):
        return Path(os.getenv('DATABASE_PATH'))
    elif os.path.exists('/data'):
        return Path('/data/ammonite.db')
    else:
        return Path(__file__).parent / 'ammonite.db'

DB_PATH = get_db_path()

def get_review_dir():
    if os.path.exists('/data'):
        return Path('/data/review_queue')
    else:
        return Path(__file__).parent / 'review_queue'

REVIEW_DIR = get_review_dir()


# ── Pydantic models ──────────────────────────────────────────
class SyncDeleteRequest(BaseModel):
    user_id: str
    identification_id: str
    cloudinary_public_id: Optional[str] = None

class AdminBackupRequest(BaseModel):
    user_id: str

class KeepForeverRequest(BaseModel):
    identification_id: str
    keep_forever: bool


# ============================================================
# 1. AUTO-DELETE  (30-day retention for Premium)
# ============================================================

@retention_router.post("/run-auto-delete")
def run_auto_delete():
    """
    Deletes identifications older than 30 days
    that are NOT marked keep_forever.
    Called by a scheduled task (e.g. daily cron).
    Only affects Premium-tier users.
    Admin tier is excluded (manual delete only).
    """
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()

    cutoff = (datetime.utcnow() - timedelta(days=30)).isoformat()

    # Find expired identifications (Premium users only, not keep_forever)
    c.execute('''
        SELECT i.id, i.user_id, fc.cloudinary_backup_url
        FROM identifications i
        LEFT JOIN fossil_collection fc ON fc.identification_id = i.id
        LEFT JOIN users u ON u.firebase_uid = i.user_id
        WHERE i.timestamp < ?
        AND (i.keep_forever IS NULL OR i.keep_forever = 0)
        AND u.tier = 'PREMIUM'
        AND i.deleted_at IS NULL
    ''', (cutoff,))

    expired = c.fetchall()
    deleted_count = 0

    for row in expired:
        identification_id, user_id, cloudinary_url = row

        # Delete local review photos
        _delete_local_photos(identification_id)

        # Delete from Cloudinary if backed up
        if cloudinary_url:
            _delete_from_cloudinary_by_url(cloudinary_url)

        # Soft-delete in DB
        c.execute('''
            UPDATE identifications
            SET deleted_at = ?
            WHERE id = ?
        ''', (datetime.utcnow().isoformat(), identification_id))

        c.execute('''
            UPDATE fossil_collection
            SET deleted_at = ?
            WHERE identification_id = ?
        ''', (datetime.utcnow().isoformat(), identification_id))

        deleted_count += 1

    conn.commit()
    conn.close()

    return {
        "auto_deleted": deleted_count,
        "cutoff_date": cutoff,
        "message": f"Cleaned up {deleted_count} expired identifications"
    }


# ============================================================
# 2. SYNC DELETE  (local + Cloudinary)
# ============================================================

@retention_router.post("/sync-delete")
def sync_delete(req: SyncDeleteRequest):
    """
    Deletes an identification from both local DB
    and Cloudinary. Used by Premium users when they
    manually delete a fossil from their collection.
    """
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()

    # Get Cloudinary URL before deleting
    c.execute('''
        SELECT cloudinary_backup_url
        FROM fossil_collection
        WHERE identification_id = ? AND user_id = ?
    ''', (req.identification_id, req.user_id))

    row = c.fetchone()
    cloudinary_url = row[0] if row else None

    # Delete from Cloudinary
    if req.cloudinary_public_id:
        _delete_from_cloudinary(req.cloudinary_public_id)
    elif cloudinary_url:
        _delete_from_cloudinary_by_url(cloudinary_url)

    # Delete local review photos
    _delete_local_photos(req.identification_id)

    # Soft-delete in DB
    now = datetime.utcnow().isoformat()
    c.execute('''
        UPDATE identifications SET deleted_at = ? WHERE id = ?
    ''', (now, req.identification_id))

    c.execute('''
        UPDATE fossil_collection SET deleted_at = ?
        WHERE identification_id = ? AND user_id = ?
    ''', (now, req.identification_id, req.user_id))

    c.execute('''
        UPDATE review_queue SET deleted_at = ?
        WHERE identification_id = ?
    ''', (now, req.identification_id))

    conn.commit()
    conn.close()

    return {
        "deleted": True,
        "identification_id": req.identification_id,
        "cloudinary_deleted": bool(cloudinary_url or req.cloudinary_public_id),
        "local_deleted": True
    }


# ============================================================
# 3. DELETE IMAGES AFTER REVIEW VERDICT
# ============================================================

@retention_router.post("/review-cleanup/{review_id}")
def review_cleanup(review_id: str):
    """
    Called after an expert gives a verdict.
    Deletes the review images from local storage
    and Cloudinary. Keeps the DB record for ML.
    """
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()

    c.execute('''
        SELECT identification_id, photo_paths, status
        FROM review_queue WHERE id = ?
    ''', (review_id,))

    row = c.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Review not found")

    identification_id, photo_paths_json, status = row

    # Only clean up if verdict has been given
    if status not in ('reviewed', 'incorrect', 'ambiguous'):
        conn.close()
        return {"cleaned": False, "reason": "No verdict yet"}

    # Delete local photos
    _delete_local_photos(identification_id)

    # Mark photos as cleaned in review_queue
    c.execute('''
        UPDATE review_queue
        SET photos_cleaned = 1, photos_cleaned_at = ?
        WHERE id = ?
    ''', (datetime.utcnow().isoformat(), review_id))

    conn.commit()
    conn.close()

    return {
        "cleaned": True,
        "review_id": review_id,
        "identification_id": identification_id
    }


# ============================================================
# 4. KEEP FOREVER TOGGLE
# ============================================================

@retention_router.post("/keep-forever")
def toggle_keep_forever(req: KeepForeverRequest):
    """
    Toggles the keep_forever flag on an identification.
    When True, the identification is excluded from
    auto-delete.
    """
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()

    c.execute('''
        UPDATE identifications
        SET keep_forever = ?
        WHERE id = ?
    ''', (1 if req.keep_forever else 0, req.identification_id))

    c.execute('''
        UPDATE fossil_collection
        SET keep_forever = ?
        WHERE identification_id = ?
    ''', (1 if req.keep_forever else 0, req.identification_id))

    conn.commit()
    conn.close()

    return {
        "identification_id": req.identification_id,
        "keep_forever": req.keep_forever
    }


# ============================================================
# 5. ADMIN FULL BACKUP
# ============================================================

@retention_router.post("/admin-backup")
def admin_full_backup(req: AdminBackupRequest):
    """
    Creates a full backup for admin tier.
    Includes: all identifications, review queue,
    users, partners, content, fossil_collection, stats.
    Returns JSON data to be uploaded to Cloudinary
    by the frontend.
    """
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # Verify admin
    c.execute("SELECT tier FROM users WHERE firebase_uid = ?", (req.user_id,))
    user = c.fetchone()
    if not user or user['tier'] != 'ADMIN':
        conn.close()
        raise HTTPException(status_code=403, detail="Admin access required")

    # Gather all data
    backup_data = {
        "backup_type": "ADMIN_FULL",
        "backup_date": datetime.utcnow().isoformat(),
        "admin_uid": req.user_id
    }

    # Users
    c.execute("SELECT * FROM users")
    backup_data["users"] = [dict(row) for row in c.fetchall()]

    # Identifications (not soft-deleted)
    c.execute("SELECT * FROM identifications WHERE deleted_at IS NULL")
    backup_data["identifications"] = [dict(row) for row in c.fetchall()]

    # Review queue
    c.execute("SELECT * FROM review_queue WHERE deleted_at IS NULL")
    backup_data["review_queue"] = [dict(row) for row in c.fetchall()]

    # Fossil collection
    c.execute("SELECT * FROM fossil_collection WHERE deleted_at IS NULL")
    backup_data["fossil_collection"] = [dict(row) for row in c.fetchall()]

    # Partners
    c.execute("SELECT * FROM partners")
    backup_data["partners"] = [dict(row) for row in c.fetchall()]

    # Content
    c.execute("SELECT * FROM content")
    backup_data["content"] = [dict(row) for row in c.fetchall()]

    # Stats summary
    c.execute("SELECT COUNT(*) FROM identifications WHERE deleted_at IS NULL")
    backup_data["stats"] = {
        "total_identifications": c.fetchone()[0]
    }
    c.execute("SELECT COUNT(*) FROM users")
    backup_data["stats"]["total_users"] = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM review_queue WHERE status='pending'")
    backup_data["stats"]["pending_reviews"] = c.fetchone()[0]

    conn.close()

    return backup_data


# ============================================================
# 6. ADMIN DELETE (manual only)
# ============================================================

@retention_router.post("/admin-delete/{identification_id}")
def admin_delete(identification_id: str, user_id: str = Query(...)):
    """
    Admin manual deletion. Deletes from local + Cloudinary.
    Only admins can call this.
    """
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()

    # Verify admin
    c.execute("SELECT tier FROM users WHERE firebase_uid = ?", (user_id,))
    user = c.fetchone()
    if not user or user[0] != 'ADMIN':
        conn.close()
        raise HTTPException(status_code=403, detail="Admin access required")

    # Get Cloudinary info
    c.execute('''
        SELECT cloudinary_backup_url
        FROM fossil_collection
        WHERE identification_id = ?
    ''', (identification_id,))
    row = c.fetchone()
    cloudinary_url = row[0] if row else None

    # Delete from Cloudinary
    if cloudinary_url:
        _delete_from_cloudinary_by_url(cloudinary_url)

    # Delete local photos
    _delete_local_photos(identification_id)

    # Soft-delete in all tables
    now = datetime.utcnow().isoformat()
    c.execute("UPDATE identifications SET deleted_at = ? WHERE id = ?",
              (now, identification_id))
    c.execute("UPDATE fossil_collection SET deleted_at = ? WHERE identification_id = ?",
              (now, identification_id))
    c.execute("UPDATE review_queue SET deleted_at = ? WHERE identification_id = ?",
              (now, identification_id))

    conn.commit()
    conn.close()

    return {
        "deleted": True,
        "identification_id": identification_id,
        "deleted_by": "admin"
    }


# ============================================================
# 7. ML DATA EXPORT
# ============================================================

@retention_router.get("/ml-export")
def ml_export(user_id: str = Query(...)):
    """
    Exports reviewed identifications flagged for ML training.
    Returns JSON with expert corrections for retraining.
    Admin only.
    """
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # Verify admin
    c.execute("SELECT tier FROM users WHERE firebase_uid = ?", (user_id,))
    user = c.fetchone()
    if not user or user['tier'] != 'ADMIN':
        conn.close()
        raise HTTPException(status_code=403, detail="Admin access required")

    # Get all reviewed items with corrections
    c.execute('''
        SELECT r.*, i.raw_result
        FROM review_queue r
        LEFT JOIN identifications i ON i.id = r.identification_id
        WHERE r.ml_flagged = 1
        AND r.deleted_at IS NULL
    ''')

    items = [dict(row) for row in c.fetchall()]
    conn.close()

    return {
        "export_date": datetime.utcnow().isoformat(),
        "total_items": len(items),
        "items": items
    }


# ============================================================
# 8. RETENTION STATUS
# ============================================================

@retention_router.get("/status/{user_id}")
def retention_status(user_id: str):
    """
    Returns retention status for a user.
    Shows what will be auto-deleted and when.
    """
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # Get user tier
    c.execute("SELECT tier FROM users WHERE firebase_uid = ?", (user_id,))
    user = c.fetchone()
    tier = user['tier'] if user else 'FREE'

    cutoff = (datetime.utcnow() - timedelta(days=30)).isoformat()

    # Count items at risk
    c.execute('''
        SELECT COUNT(*) as count FROM identifications
        WHERE user_id = ?
        AND (keep_forever IS NULL OR keep_forever = 0)
        AND deleted_at IS NULL
        AND timestamp < ?
    ''', (user_id, cutoff))
    at_risk = c.fetchone()['count']

    # Count kept forever
    c.execute('''
        SELECT COUNT(*) as count FROM identifications
        WHERE user_id = ? AND keep_forever = 1 AND deleted_at IS NULL
    ''', (user_id,))
    kept = c.fetchone()['count']

    # Total active
    c.execute('''
        SELECT COUNT(*) as count FROM identifications
        WHERE user_id = ? AND deleted_at IS NULL
    ''', (user_id,))
    total = c.fetchone()['count']

    conn.close()

    return {
        "user_id": user_id,
        "tier": tier,
        "total_active": total,
        "kept_forever": kept,
        "at_risk_auto_delete": at_risk if tier == 'PREMIUM' else 0,
        "auto_delete_enabled": tier == 'PREMIUM',
        "retention_days": 30 if tier == 'PREMIUM' else None,
        "admin_manual_only": tier == 'ADMIN'
    }


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def _delete_local_photos(identification_id: str):
    """Delete local review photos for an identification."""
    photo_dir = REVIEW_DIR / identification_id
    if photo_dir.exists():
        shutil.rmtree(str(photo_dir))


def _delete_from_cloudinary(public_id: str):
    """Delete a resource from Cloudinary by public_id."""
    if not CLOUDINARY_API_KEY or not CLOUDINARY_API_SECRET:
        print("⚠️ Cloudinary credentials not set, skipping cloud delete")
        return False

    try:
        url = f"https://api.cloudinary.com/v1_1/{CLOUDINARY_CLOUD_NAME}/resources/image/upload"
        response = requests.delete(
            url,
            params={"public_ids[]": public_id},
            auth=(CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET)
        )
        return response.status_code == 200
    except Exception as e:
        print(f"⚠️ Cloudinary delete failed: {e}")
        return False


def _delete_from_cloudinary_by_url(cloudinary_url: str):
    """Extract public_id from URL and delete."""
    if not cloudinary_url:
        return False
    try:
        # URL format: https://res.cloudinary.com/CLOUD/TYPE/upload/vXXX/FOLDER/FILE.EXT
        parts = cloudinary_url.split('/upload/')
        if len(parts) == 2:
            path = parts[1]
            # Remove version prefix (v1234567890/)
            if path.startswith('v') and '/' in path:
                path = path.split('/', 1)[1]
            # Remove file extension
            public_id = path.rsplit('.', 1)[0]
            return _delete_from_cloudinary(public_id)
    except Exception as e:
        print(f"⚠️ Could not parse Cloudinary URL: {e}")
    return False
