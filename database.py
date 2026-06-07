# ============================================================
# database.py — Shared database configuration for all modules
# AmmoniteID v1.0
# ============================================================
# Single source of truth for database path logic.
# All router files should import DB_PATH and REVIEW_DIR from here.
# ============================================================

import os
from pathlib import Path

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

def get_review_dir():
    """Determine review queue directory based on environment."""
    # Check for explicit DATABASE_PATH (derive review dir from it)
    if os.getenv('DATABASE_PATH'):
        return Path(os.getenv('DATABASE_PATH')).parent / 'review_queue'
    # Check for Render environment
    elif os.getenv('RENDER'):
        return Path('/tmp/review_queue')
    # Check for /data mount (Hostim fallback)
    elif os.path.exists('/data'):
        return Path('/data/review_queue')
    # Local development
    else:
        return Path(__file__).parent / 'review_queue'

def get_upload_dir():
    """Determine upload directory based on environment."""
    if os.getenv('DATABASE_PATH'):
        return Path(os.getenv('DATABASE_PATH')).parent / 'uploads'
    elif os.getenv('RENDER'):
        return Path('/tmp/uploads')
    elif os.path.exists('/data'):
        return Path('/data/uploads')
    else:
        return Path(__file__).parent / 'uploads'

# Export shared constants
DB_PATH = get_db_path()
REVIEW_DIR = get_review_dir()
UPLOAD_DIR = get_upload_dir()

# Ensure directories exist
DB_PATH.parent.mkdir(exist_ok=True, parents=True)
REVIEW_DIR.mkdir(exist_ok=True, parents=True)
UPLOAD_DIR.mkdir(exist_ok=True, parents=True)

print(f"📁 Database path: {DB_PATH}")
print(f"📁 Review directory: {REVIEW_DIR}")
print(f"📁 Upload directory: {UPLOAD_DIR}")