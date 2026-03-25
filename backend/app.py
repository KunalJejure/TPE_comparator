"""FastAPI application — serves the dashboard UI and comparison API."""

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from backend.api.compare import router as compare_router
from backend.api.chat import router as chat_router
from backend.api.reports import router as reports_router
from backend.api.auth import router as auth_router
from backend.config import SECRET_KEY, IS_PRODUCTION
from backend.database import init_db

# Initialize database
init_db()

# ---- Paths ----
_BACKEND_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _BACKEND_DIR.parent
_FRONTEND_DIR = _PROJECT_ROOT / "frontend"

# ---- App ----
app = FastAPI(
    title="PDF Comparator",
    version="1.0.0",
    description="Enterprise-grade PDF comparison system",
)

# Session middleware — required for OAuth2 state + user sessions
app.add_middleware(
    SessionMiddleware,
    secret_key=SECRET_KEY,
    session_cookie="qalens_session",
    max_age=86400,          # 24-hour session
    same_site="lax",
    https_only=IS_PRODUCTION,
)

# Static files (CSS, JS, images)
_STATIC_DIR = _FRONTEND_DIR / "static"
_STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

# HTML templates
_TEMPLATES_DIR = _FRONTEND_DIR / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))

# API routes
app.include_router(compare_router, prefix="/api")
app.include_router(chat_router, prefix="/api")
app.include_router(reports_router, prefix="/api/reports")

app.include_router(auth_router)


@app.get("/health")
def health_check():
    return {"status": "UP"}


@app.get("/")
def home(request: Request):
    user = request.session.get("user")
    return templates.TemplateResponse(
        request,
        "index.html",
        context={
            "user": user,
            "sso_authenticated": user is not None,
        },
    )
