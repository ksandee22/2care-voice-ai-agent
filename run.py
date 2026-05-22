"""Run the API server from project root: python run.py"""
import os
import sys
from pathlib import Path

# Ensure project root is on PYTHONPATH (required on Render/Linux)
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import uvicorn

from backend.config import get_settings

if __name__ == "__main__":
    s = get_settings()
    port = int(os.environ.get("PORT", s.port))
    # Disable reload on Render/production (PORT is set by the platform)
    reload = os.environ.get("PORT") is None and os.environ.get("RENDER") is None
    uvicorn.run("backend.main:app", host="0.0.0.0", port=port, reload=reload)
