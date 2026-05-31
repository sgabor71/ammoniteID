# ============================================================
# main.py — FastAPI web server (Hostim-ready)
# AmmoniteID v1.0 with Admin Panel
# ============================================================
# Run locally: py -3.11 -m uvicorn main:app --reload
# Deploy to Hostim: Git push, Hostim auto-deploys via Docker
# ============================================================

import os
os.environ['TF_XLA_FLAGS'] = '--tf_xla_enable_xla_devices=false'

from fastapi import (
    FastAPI, File, UploadFile, HTTPException, Form
)
from fastapi.staticfiles import StaticFiles
from admin_api import router as admin_api_router
from admin_content_api import content_router
from auth_api import auth_router, get_user_tier
from features_api import features_router
from stripe_api import stripe_router
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from typing import List
import uuid
import os
import json
import sqlite3
from datetime import datetime
from pathlib import Path

from config import (
    UPLOAD_DIR, REVIEW_DIR,
    MAX_PHOTOS, MAX_FILE_MB,
    MODEL_VERSION, APP_VERSION
)
from identifier import identify_from_bytes_list

# ── Create the app ───────────────────────────────────────────
app = FastAPI(
    title="AmmoniteID API",
    description="Ammonite fossil identification backend",
    version=APP_VERSION
)

# ── Service worker must be at root path, not /static/ ────────
@app.get("/service-worker.js")
async def service_worker():
    return FileResponse("service-worker.js", media_type="application/javascript")

@app.get("/manifest.json")
async def manifest():
    return FileResponse("static/manifest.json", media_type="application/json")

app.mount("/static", StaticFiles(directory="static"), name="static")
app.include_router(admin_api_router)
app.include_router(content_router)
app.include_router(auth_router)
app.include_router(features_router)
app.include_router(stripe_router)

# ── Add CORS middleware ──────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Database setup ───────────────────────────────────────────
# Database location - supports Hostim /data, Render /tmp, or local
def get_db_path():
    """Determine database path based on environment."""
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

def init_db():
    """
    Creates the SQLite database and tables
    if they do not already exist.
    """
    conn = sqlite3.connect(str(DB_PATH))
    c    = conn.cursor()

    # Every identification is logged here
    c.execute('''
        CREATE TABLE IF NOT EXISTS identifications (
            id               TEXT PRIMARY KEY,
            timestamp        TEXT,
            num_photos       INTEGER,
            scenario         TEXT,
            top_family       TEXT,
            family_score     INTEGER,
            top_genus        TEXT,
            formatted_output TEXT,
            raw_result       TEXT,
            user_id          TEXT
        )
    ''')

    # Safety: if an older DB exists without user_id, add it.
    c.execute("PRAGMA table_info(identifications)")
    _id_cols = [row[1] for row in c.fetchall()]
    if 'user_id' not in _id_cols:
        c.execute("ALTER TABLE identifications ADD COLUMN user_id TEXT")

    # Images awaiting expert review
    c.execute('''
        CREATE TABLE IF NOT EXISTS review_queue (
            id                TEXT PRIMARY KEY,
            identification_id TEXT,
            timestamp         TEXT,
            ai_family         TEXT,
            ai_genus          TEXT,
            ai_confidence     INTEGER,
            status            TEXT DEFAULT 'pending',
            expert_family     TEXT,
            expert_genus      TEXT,
            expert_notes      TEXT,
            reviewed_at       TEXT,
            reviewed_by       TEXT,
            photo_paths       TEXT
        )
    ''')

    # Ensure photo_paths column exists
    c.execute("PRAGMA table_info(review_queue)")
    columns = [col[1] for col in c.fetchall()]
    if 'photo_paths' not in columns:
        c.execute("ALTER TABLE review_queue ADD COLUMN photo_paths TEXT")

    conn.commit()
    conn.close()

# Initialize database when server starts
init_db()


# ── Helper functions ─────────────────────────────────────────

def save_identification(
    identification_id: str,
    result: dict,
    num_photos: int,
    user_id: str = None
):
    """Saves an identification result to the database."""
    top_genus = (
        result['genus_breakdown'][0]['genus']
        if result['genus_breakdown'] else None
    )

    conn = sqlite3.connect(str(DB_PATH))
    c    = conn.cursor()
    c.execute('''
        INSERT INTO identifications
        (id, timestamp, num_photos, scenario, top_family,
         family_score, top_genus, formatted_output, raw_result, user_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        identification_id,
        datetime.utcnow().isoformat(),
        num_photos,
        result['scenario'],
        result.get('top_family'),
        result.get('top_family_score'),
        top_genus,
        result['formatted_output'],
        json.dumps(result),
        user_id
    ))
    conn.commit()
    conn.close()


def save_to_review_queue(
    identification_id: str,
    result: dict,
    photo_paths: list = None
):
    """
    Saves an identification to the expert review queue.
    Stores paths to the saved photos for display in
    the review portal.
    """
    review_id = str(uuid.uuid4())
    top_genus = (
        result['genus_breakdown'][0]['genus']
        if result['genus_breakdown'] else None
    )
    
    # Convert photo paths list to JSON string
    photo_paths_json = json.dumps(photo_paths) if photo_paths else None

    conn = sqlite3.connect(str(DB_PATH))
    c    = conn.cursor()
    
    # Check if it's a non-ammonite
    if result.get('scenario') == 'non_ammonite':
        ai_family = result.get('non_am_display', 'Non-ammonite')
        ai_genus = 'N/A'
        ai_confidence = result.get('non_am_total', 0)
    else:
        ai_family = result.get('top_family')
        ai_genus = top_genus
        ai_confidence = result.get('top_family_score')
    
    c.execute('''
        INSERT INTO review_queue
        (id, identification_id, timestamp,
         ai_family, ai_genus, ai_confidence, status, photo_paths)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        review_id,
        identification_id,
        datetime.utcnow().isoformat(),
        ai_family,
        ai_genus,
        ai_confidence,
        'pending',
        photo_paths_json
    ))
    conn.commit()
    conn.close()
    return review_id


# ============================================================
# API ENDPOINTS
# ============================================================

@app.get("/")
def root():
    """Health check — confirms the server is running."""
    return {
        "status":        "running",
        "app":           "AmmoniteID",
        "version":       APP_VERSION,
        "model_version": MODEL_VERSION,
    }


@app.post("/identify")
async def identify(
    photos: List[UploadFile] = File(...),
    user_id: str = Form(None)
):
    """
    Main identification endpoint.
    Accepts 1 to 3 photos of the same specimen.
    Returns family, genus breakdown and
    formatted display text.
    """

    # ── Validate number of photos ────────────────────────────
    if len(photos) == 0:
        raise HTTPException(
            status_code=400,
            detail="No photos provided."
        )

    if len(photos) > MAX_PHOTOS:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum {MAX_PHOTOS} photos allowed."
        )

    # ── Read and validate each photo ─────────────────────────
    images_bytes = []
    max_bytes    = MAX_FILE_MB * 1024 * 1024

    for photo in photos:
        if photo.content_type not in (
            'image/jpeg', 'image/png', 'image/jpg', 'image/webp'
        ):
            raise HTTPException(
                status_code=400,
                detail=f"{photo.filename} is not a"
                       f" JPG, PNG, or WebP image."
            )

        contents = await photo.read()

        if len(contents) > max_bytes:
            raise HTTPException(
                status_code=400,
                detail=f"{photo.filename} is too large."
                       f" Maximum {MAX_FILE_MB}MB."
            )

        images_bytes.append(contents)

    # ── Run identification ────────────────────────────────────
    try:
        result = identify_from_bytes_list(
            images_bytes,
            num_photos=len(photos)
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Identification failed: {str(e)}"
        )

    # ── Save to database ──────────────────────────────────────
    identification_id = str(uuid.uuid4())
    save_identification(
        identification_id, result, len(photos), user_id=user_id
    )

    # ── Save photos to disk for review ───────────────────────
    # Create a folder for this identification
    review_folder = REVIEW_DIR / identification_id
    review_folder.mkdir(parents=True, exist_ok=True)
    
    saved_photo_paths = []
    for idx, img_bytes in enumerate(images_bytes):
        photo_path = review_folder / f"photo_{idx+1}.jpg"
        with open(str(photo_path), 'wb') as f:
            f.write(img_bytes)
        saved_photo_paths.append(str(photo_path))

    # ── Save to review queue with photo paths ────────────────
    review_id = save_to_review_queue(
        identification_id, result, saved_photo_paths
    )

    # ── Return result ─────────────────────────────────────────
    return {
        "identification_id": identification_id,
        "review_id":         review_id,
        "scenario":          result['scenario'],
        "num_photos":        result['num_photos'],
        "top_family":        result.get('top_family'),
        "family_confidence": result.get('top_family_score'),
        "genus_breakdown":   result.get('genus_breakdown'),
        "family_scores":     result.get('family_scores'),
        "non_am_total":      result.get('non_am_total'),
        "non_am_category":   result.get('non_am_category'),
        "non_am_display":    result.get('non_am_display'),
        "formatted_output":  result['formatted_output'],
        "model_version":     MODEL_VERSION,
        "family_label":      result.get('family_label', ''),
        "genus_label":       result.get('genus_label', ''),
        "feedback_message":  result.get('feedback_message', ''),
        "feedback_style":    result.get('feedback_style', 'info'),
    }


@app.get("/result/{identification_id}")
def get_result(identification_id: str):
    """
    Retrieves a previously saved identification
    by its ID. Used when the app needs to reload
    a result without rerunning the model.
    """
    conn = sqlite3.connect(str(DB_PATH))
    c    = conn.cursor()
    c.execute(
        "SELECT raw_result FROM identifications"
        " WHERE id=?",
        (identification_id,)
    )
    row = c.fetchone()
    conn.close()

    if not row:
        raise HTTPException(
            status_code=404,
            detail="Identification not found."
        )

    return json.loads(row[0])


@app.get("/queue")
def get_review_queue(status: str = "pending"):
    """
    Returns the expert review queue.
    Filter by status: pending, reviewed,
    ambiguous, discarded.
    
    This endpoint is for the expert review portal.
    """
    conn = sqlite3.connect(str(DB_PATH))
    c    = conn.cursor()
    c.execute(
        "SELECT * FROM review_queue WHERE status=?"
        " ORDER BY timestamp DESC",
        (status,)
    )
    rows    = c.fetchall()
    columns = [d[0] for d in c.description]
    conn.close()

    return {
        "status": status,
        "count":  len(rows),
        "items":  [
            dict(zip(columns, row))
            for row in rows
        ]
    }


@app.post("/queue/{review_id}/update")
def update_review(
    review_id:     str,
    expert_family: str = None,
    expert_genus:  str = None,
    expert_notes:  str = None,
    status:        str = "reviewed",
    reviewed_by:   str = "expert"
):
    """
    Updates a review queue item with expert verdict.
    Status options: reviewed, discarded, ambiguous
    
    Called from the expert review portal when
    an expert submits their correction.
    """
    conn = sqlite3.connect(str(DB_PATH))
    c    = conn.cursor()
    c.execute('''
        UPDATE review_queue
        SET status=?, expert_family=?,
            expert_genus=?, expert_notes=?,
            reviewed_at=?, reviewed_by=?
        WHERE id=?
    ''', (
        status,
        expert_family,
        expert_genus,
        expert_notes,
        datetime.utcnow().isoformat(),
        reviewed_by,
        review_id
    ))
    conn.commit()
    conn.close()

    return {
        "review_id": review_id,
        "status":    status,
        "updated":   True
    }


@app.get("/stats")
def get_stats():
    """
    Returns basic usage statistics.
    Used by the admin panel and review portal.
    """
    conn = sqlite3.connect(str(DB_PATH))
    c    = conn.cursor()

    # Total identifications
    c.execute("SELECT COUNT(*) FROM identifications")
    total = c.fetchone()[0]

    # Scenario breakdown
    c.execute('''
        SELECT scenario, COUNT(*) as count
        FROM identifications
        GROUP BY scenario
        ORDER BY count DESC
    ''')
    scenarios = dict(c.fetchall())

    # Top families identified
    c.execute('''
        SELECT top_family, COUNT(*) as count
        FROM identifications
        WHERE top_family IS NOT NULL
        GROUP BY top_family
        ORDER BY count DESC
    ''')
    families = dict(c.fetchall())

    # Pending reviews
    c.execute('''
        SELECT COUNT(*) FROM review_queue
        WHERE status='pending'
    ''')
    pending_reviews = c.fetchone()[0]

    conn.close()

    return {
        "total_identifications": total,
        "pending_reviews":       pending_reviews,
        "scenarios":             scenarios,
        "top_families":          families,
        "model_version":         MODEL_VERSION,
    }


@app.get("/photo/{identification_id}/{photo_name}")
def get_photo(identification_id: str, photo_name: str):
    """
    Serves a photo from the review queue folder.
    Used by the expert review portal to display images.
    """
    from fastapi.responses import FileResponse
    
    photo_path = REVIEW_DIR / identification_id / photo_name
    
    if not photo_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Photo not found."
        )
    
    return FileResponse(str(photo_path))
