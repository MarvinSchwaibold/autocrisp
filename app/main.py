from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.api import router

BASE_DIR = Path(__file__).resolve().parent.parent

app = FastAPI(
    title="AutoCrisp",
    description="AI-powered image enhancement service using Real-ESRGAN",
    version="0.1.0"
)

# CORS middleware for future frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
if (BASE_DIR / "static").exists():
    app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

# Include API routes
app.include_router(router, prefix="/api")


@app.get("/", response_class=HTMLResponse)
async def root():
    template_path = BASE_DIR / "templates" / "index.html"
    if template_path.exists():
        return template_path.read_text()
    return "<h1>AutoCrisp</h1><p>Template not found. Visit <a href='/docs'>/docs</a> for API.</p>"


@app.get("/health")
async def health():
    return {"status": "healthy"}
