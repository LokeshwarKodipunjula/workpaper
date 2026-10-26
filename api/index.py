"""Vercel entry point: one Python serverless function that runs the whole FastAPI app.

Vercel rewrites every /api/* request here (see vercel.json); the React build is served as static files.
The import path is the same one uvicorn uses locally (`app.main:app` with backend/ on sys.path), so
nothing in the backend knows it is on Vercel except the database fallback in events.db_url().
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from app.main import app  # noqa: E402,F401
