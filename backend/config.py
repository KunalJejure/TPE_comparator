"""Centralised configuration — loaded once at startup."""

import os
import logging
from pathlib import Path
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Project root is the parent of the backend/ package
BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env from project root
load_dotenv(BASE_DIR / ".env")

# ---- Environment variables ----
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    logger.warning("GROQ_API_KEY is not set. AI analysis will be unavailable.")

# ---- Azure AD ----
AZURE_CLIENT_ID = os.getenv("AZURE_CLIENT_ID")
AZURE_CLIENT_SECRET = os.getenv("AZURE_CLIENT_SECRET")
AZURE_TENANT_ID = os.getenv("AZURE_TENANT_ID")
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")

AZURE_METADATA_URL = f"https://login.microsoftonline.com/{AZURE_TENANT_ID}/v2.0/.well-known/openid-configuration"

# ---- App URL ----
# Set BASE_URL in production (e.g. https://your-app.up.railway.app)
# Locally it auto-detects but replaces 0.0.0.0 with localhost
BASE_URL = os.getenv("BASE_URL", "")

# Detect production: Railway always sets RAILWAY_ENVIRONMENT
IS_PRODUCTION = bool(os.getenv("RAILWAY_ENVIRONMENT") or os.getenv("RAILWAY_PROJECT_ID"))


# ---- Paths ----
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

STATIC_DIR = BASE_DIR / "frontend" / "static"
REPORTS_DIR = STATIC_DIR / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)
