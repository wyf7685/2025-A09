from pathlib import Path

DATA_DIR = Path("data")
UPLOAD_DIR = DATA_DIR / "uploads"
EXPORT_DIR = DATA_DIR / "exports"
STATE_DIR = DATA_DIR / "states"
MODEL_DIR = DATA_DIR / "models"
SESSION_DIR = DATA_DIR / "sessions"
DATASOURCE_DIR = DATA_DIR / "datasources"

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
EXPORT_DIR.mkdir(parents=True, exist_ok=True)
STATE_DIR.mkdir(parents=True, exist_ok=True)
MODEL_DIR.mkdir(parents=True, exist_ok=True)
SESSION_DIR.mkdir(parents=True, exist_ok=True)
DATASOURCE_DIR.mkdir(parents=True, exist_ok=True)
