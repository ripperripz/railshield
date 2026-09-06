"""Vercel Python entrypoint for the RailShield FastAPI application."""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
os.environ["RAILSHIELD_ENVIRONMENT"] = "serverless"

from app.main import app  # noqa: E402, F401
