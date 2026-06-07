# ============================================================
# collection_api.py — Fossil Collection API
# AmmoniteID
# ============================================================
# Endpoints:
#   POST   /api/collection/save        — save fossil after identification
#   GET    /api/collection/{uid}       — get user's full collection
#   PATCH  /api/collection/{entry_id}  — update favorite/keep_forever/notes
#   DELETE /api/collection/{entry_id}  — delete fossil + image from Hostim
#   DELETE /api/collection/{uid}/all   — delete all fossils for a user
#   GET    /api/storage/stats          — image storage stats for admin
#   POST   /api/storage/cleanup        — admin bulk delete images
# ============================================================

import os
import json
import sqlite3
import shutil
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, List
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# Import shared database configuration
from database import DB_PATH, REVIEW_DIR

collection_router = APIRouter(tags=["collection"])


def _db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


# ── Models ───────────────────────────────────────────────────
class FossilSave(BaseModel):
    user_id: str
    identification_id: str
    family: str
    genus: str
    family_label: Optional[str] = ''
    confidence: Optional[int] = 0
    scenario: Optional[str] = ''
    formatted_output: Optional[str] = ''
    genus_breakdown: Optional[list] = []
    notes: Optional[str] = ''

class StorageCleanup(BaseModel):
    mode: str             # 'ambiguous' or 'older_than_days'
    days: Optional[int] = None
    confirm: bool = False

class FossilUpdate(BaseModel):
    favorite: Optional[bool] = None
    keep_forever: Optional[bool] = None
    notes: Optional[str] = None


# ============================================================
# POST /api/collection/save
# Called by test.html after identification (PREMIUM+ users)
# ============================================================
@collection_router.post("/api/collection/save")
async def save_fossil(body: FossilSave):
    conn = _db()
    c = conn.cursor()

    # Check user exists
    c.execute("SELECT 1 FROM users WHERE firebase_uid = ?", (body.user_id,))
    if not c.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="User not found.")

    # Get photo paths from review_queue for this identification
    photo_paths = []
    try:
        c.execute(
            "SELECT photo_paths FROM review_queue WHERE identification_id = ?",
            (body.identification_id,)
        )
        row = c.fetchone()
        if row and row["photo_paths"]:
            stored_paths = json.loads(row["photo_paths"])
            # Convert server paths to API URLs
            for path in stored_paths:
                fname = Path(path).name
                photo_paths.append(f"/photo/{body.identification_id}/{fname}")
    except Exception:
        pass

    now = datetime.utcnow().isoformat()
    entry_id = f"{body.user_id}_{body.identification_id}"

    try:
        c.execute("""
            INSERT OR REPLACE INTO fossil_collection
            (id, user_id, identification_id, family, genus, family_label,
             confidence, scenario, formatted_output, genus_breakdown,
             photo_paths, notes, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            entry_id,
            body.user_id,
            body.identification_id,
            body.family,
            body.genus,
            body.family_label,
            body.confidence,
            body.scenario,
            body.formatted_output,
            json.dumps(body.genus_breakdown),
            json.dumps(photo_paths),
            body.notes,
            now
        ))
        conn.commit()
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=str(e))

    conn.close()
    return {"status": "ok", "id": entry_id, "photos": photo_paths}


# ============================================================
# GET /api/collection/{uid}
# Load user's full fossil collection
# ============================================================
@collection_router.get("/api/collection/{uid}")
async def get_collection(uid: str):
    conn = _db()
    c = conn.cursor()

    try:
        c.execute("""
            SELECT id, identification_id, family, genus, family_label,
                   confidence, scenario, formatted_output, genus_breakdown,
                   photo_paths, notes, created_at, favorite, keep_forever
            FROM fossil_collection
            WHERE user_id = ? AND (deleted_at IS NULL OR deleted_at = '')
            ORDER BY created_at DESC
        """, (uid,))
        rows = c.fetchall()
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=str(e))

    conn.close()

    fossils = []
    for row in rows:
        fossils.append({
            "id": row["id"],
            "identification_id": row["identification_id"],
            "family": row["family"],
            "genus": row["genus"],
            "family_label": row["family_label"] or "",
            "confidence": row["confidence"] or 0,
            "scenario": row["scenario"] or "",
            "formatted_output": row["formatted_output"] or "",
            "genus_breakdown": json.loads(row["genus_breakdown"] or "[]"),
            "photos": json.loads(row["photo_paths"] or "[]"),
            "notes": row["notes"] or "",
            "date": row["created_at"],
            "favorite": bool(row["favorite"]),
            "keepForever": bool(row["keep_forever"]),
        })

    return {"status": "ok", "count": len(fossils), "fossils": fossils}


# ============================================================
# PATCH /api/collection/{entry_id}
# Update fossil fields: favorite, keep_forever, notes
# ============================================================
@collection_router.patch("/api/collection/{entry_id}")
async def update_fossil(entry_id: str, body: FossilUpdate):
    conn = _db()
    c = conn.cursor()

    # Check fossil exists
    c.execute("SELECT id FROM fossil_collection WHERE id = ?", (entry_id,))
    if not c.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Fossil not found.")

    # Build dynamic update
    updates = []
    values = []

    if body.favorite is not None:
        updates.append("favorite = ?")
        values.append(1 if body.favorite else 0)

    if body.keep_forever is not None:
        updates.append("keep_forever = ?")
        values.append(1 if body.keep_forever else 0)

    if body.notes is not None:
        updates.append("notes = ?")
        values.append(body.notes)

    if not updates:
        conn.close()
        return {"status": "ok", "updated": False, "reason": "No fields to update"}

    values.append(entry_id)
    sql = f"UPDATE fossil_collection SET {', '.join(updates)} WHERE id = ?"

    try:
        c.execute(sql, values)
        conn.commit()
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=str(e))

    conn.close()
    return {"status": "ok", "updated": True, "id": entry_id}


# ============================================================
# DELETE /api/collection/{entry_id}
# Delete fossil from collection + image from Hostim
# ============================================================
@collection_router.delete("/api/collection/{entry_id}")
async def delete_fossil(entry_id: str):
    conn = _db()
    c = conn.cursor()

    # Get the identification_id before deleting
    c.execute(
        "SELECT identification_id FROM fossil_collection WHERE id = ?",
        (entry_id,)
    )
    row = c.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Fossil not found.")

    identification_id = row["identification_id"]

    # Delete from fossil_collection table
    c.execute("DELETE FROM fossil_collection WHERE id = ?", (entry_id,))
    conn.commit()
    conn.close()

    # Delete image files from Hostim
    deleted_files = []
    image_folder = REVIEW_DIR / identification_id
    if image_folder.exists():
        try:
            shutil.rmtree(str(image_folder))
            deleted_files.append(str(image_folder))
        except Exception as e:
            print(f"⚠️ Could not delete images for {identification_id}: {e}")

    return {
        "status": "ok",
        "deleted": entry_id,
        "images_deleted": len(deleted_files) > 0
    }


# ============================================================
# DELETE /api/collection/{uid}/all
# Delete all fossils for a user
# ============================================================
@collection_router.delete("/api/collection/{uid}/all")
async def delete_all_fossils(uid: str):
    conn = _db()
    c = conn.cursor()

    # Get all identification IDs first
    c.execute(
        "SELECT identification_id FROM fossil_collection WHERE user_id = ?",
        (uid,)
    )
    rows = c.fetchall()
    identification_ids = [row["identification_id"] for row in rows]

    # Delete all from DB
    c.execute("DELETE FROM fossil_collection WHERE user_id = ?", (uid,))
    conn.commit()
    conn.close()

    # Delete image folders
    deleted = 0
    for identification_id in identification_ids:
        folder = REVIEW_DIR / identification_id
        if folder.exists():
            try:
                shutil.rmtree(str(folder))
                deleted += 1
            except Exception:
                pass

    return {
        "status": "ok",
        "fossils_deleted": len(identification_ids),
        "image_folders_deleted": deleted
    }


# ============================================================
# GET /api/storage/stats
# Admin: image storage statistics
# ============================================================
@collection_router.get("/api/storage/stats")
async def get_storage_stats():
    stats = {
        "total_folders": 0,
        "total_images": 0,
        "total_size_mb": 0,
        "oldest_date": None,
    }

    if not REVIEW_DIR.exists():
        return stats

    total_size = 0
    oldest = None

    for folder in REVIEW_DIR.iterdir():
        if folder.is_dir():
            stats["total_folders"] += 1
            for f in folder.iterdir():
                if f.is_file():
                    stats["total_images"] += 1
                    total_size += f.stat().st_size
                    mtime = datetime.fromtimestamp(f.stat().st_mtime)
                    if oldest is None or mtime < oldest:
                        oldest = mtime

    stats["total_size_mb"] = round(total_size / (1024 * 1024), 2)
    stats["oldest_date"] = oldest.isoformat() if oldest else None

    return stats


# ============================================================
# POST /api/storage/cleanup
# Admin: manually bulk delete images
# NEVER auto-deletes — requires explicit admin action + confirm
# ============================================================
@collection_router.post("/api/storage/cleanup")
async def storage_cleanup(body: StorageCleanup):
    if not body.confirm:
        raise HTTPException(
            status_code=400,
            detail="Must set confirm=true to delete. This cannot be undone."
        )

    if not REVIEW_DIR.exists():
        return {"status": "ok", "deleted": 0}

    conn = _db()
    c = conn.cursor()
    deleted = 0
    folders_to_delete = []

    if body.mode == "ambiguous":
        # Find all identifications marked ambiguous in review_queue
        c.execute(
            "SELECT identification_id FROM review_queue WHERE status = 'ambiguous'"
        )
        rows = c.fetchall()
        folders_to_delete = [row["identification_id"] for row in rows]

    elif body.mode == "older_than_days":
        if not body.days or body.days < 1:
            conn.close()
            raise HTTPException(
                status_code=400,
                detail="Must specify days > 0 for older_than_days mode."
            )
        cutoff = datetime.utcnow() - timedelta(days=body.days)
        c.execute(
            "SELECT identification_id FROM review_queue WHERE timestamp < ?",
            (cutoff.isoformat(),)
        )
        rows = c.fetchall()
        folders_to_delete = [row["identification_id"] for row in rows]

    else:
        conn.close()
        raise HTTPException(status_code=400, detail="mode must be 'ambiguous' or 'older_than_days'")

    conn.close()

    # Delete image folders
    for identification_id in folders_to_delete:
        folder = REVIEW_DIR / identification_id
        if folder.exists():
            try:
                shutil.rmtree(str(folder))
                deleted += 1
            except Exception as e:
                print(f"⚠️ Could not delete {folder}: {e}")

    return {
        "status": "ok",
        "mode": body.mode,
        "days": body.days,
        "deleted_folders": deleted,
        "total_candidates": len(folders_to_delete)
    }
