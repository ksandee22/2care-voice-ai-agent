"""
Render/Heroku entry point — single module at repo root.
Start command: uvicorn app:app --host 0.0.0.0 --port $PORT
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.main import app  # noqa: F401

__all__ = ["app"]
