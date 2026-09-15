"""App paths and settings. Easy to tweak for local development."""

from pathlib import Path

# backend/ directory (parent of app/)
BACKEND_DIR = Path(__file__).resolve().parent.parent

# Persisted Kite session for local dev (gitignored — never commit)
SESSION_FILE = BACKEND_DIR / ".kite_session.json"

# CORS origins for the Vite frontend
CORS_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]
