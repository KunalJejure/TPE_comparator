from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.api.compare import router as compare_router

app = FastAPI(
    title="PDF Comparator",
    version="1.0.0",
    description="Enterprise-grade PDF comparison system",
)

# Static files (CSS, JS, logo)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# HTML templates
templates = Jinja2Templates(directory="app/templates")

# API routes
app.include_router(compare_router, prefix="/api")

@app.get("/health")
def health_check():
    return {"status": "UP"}

@app.get("/")
def home(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {"request": request},
    )
