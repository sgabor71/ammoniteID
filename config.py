# ============================================================
# config.py — Configuration constants
# AmmoniteID v1.0 — Hostim-ready
# ============================================================

import os
from pathlib import Path

# Detect hosting platform
IS_RENDER = os.getenv('RENDER') is not None
IS_HOSTIM = os.getenv('HOSTIM') is not None or os.path.exists('/data')

# Base directory
BASE_DIR = Path(__file__).parent

# Model and class info file paths
MODEL_PATH = BASE_DIR / 'ammonite_model_v1_quantized.tflite'
CLASS_INFO = BASE_DIR / 'class_info.json'

# Storage directories - different paths for Render vs Hostim vs local
if IS_RENDER:
    UPLOAD_DIR = Path('/tmp/uploads')
    REVIEW_DIR = Path('/tmp/review_queue')
elif IS_HOSTIM:
    # Hostim uses persistent volumes at /data
    UPLOAD_DIR = Path('/data/uploads')
    REVIEW_DIR = Path('/data/review_queue')
else:
    # Local development
    UPLOAD_DIR = BASE_DIR / 'uploads'
    REVIEW_DIR = BASE_DIR / 'review_queue'

UPLOAD_DIR.mkdir(exist_ok=True, parents=True)
REVIEW_DIR.mkdir(exist_ok=True, parents=True)

# Model settings
IMAGE_SIZE = 224  # EfficientNet-B0 input size

# Confidence thresholds
FAMILY_LIKELY_THRESHOLD = 75
FAMILY_POSSIBLE_THRESHOLD = 50
GENUS_BEST_MATCH_THRESHOLD = 0.25
GENUS_POSSIBLE_THRESHOLD = 0.15

# Upload limits
MAX_PHOTOS  = 3
MAX_FILE_MB = 10

# Version info
MODEL_VERSION = "v1.0"
APP_VERSION   = "1.0.0"
