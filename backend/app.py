"""FastAPI application — serves the dashboard UI and comparison API."""

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from backend.api.compare import router as compare_router
from backend.api.chat import router as chat_router

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


@app.get("/health")
def health_check():
    return {"status": "UP"}


@app.get("/")
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})
