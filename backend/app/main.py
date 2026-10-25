"""Nirikshan API: AI-assisted scrutiny workstation for AICTE approval applications (SIH 2026, PS 26261)."""
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .api import analytics, aph, applications, auth, documents, reports
from .config import BACKEND_DIR, settings
from .db import init_db

app = FastAPI(title="Nirikshan API", version="1.0.0",
              description="Evidence-linked scrutiny of AICTE approval dossiers. The AI finds, explains and cites; the officer decides.")
app.add_middleware(CORSMiddleware, allow_origins=[o.strip() for o in settings.cors_origins.split(",")],
                   allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
                   expose_headers=["X-Page-Width", "X-Page-Height"])

for r in (auth.router, applications.router, documents.router, reports.router, aph.router, analytics.router):
    app.include_router(r)


@app.on_event("startup")
def _startup():
    init_db()


@app.get("/health")
def health():
    from .services import llm, ocr, retrieval
    return {"status": "ok", "app": settings.app_name, "ocr": ocr.available_engine(), "llm": llm.name(),
            "retrieval": retrieval.engine_name(), "aph_edition": settings.aph_edition}


# Serve the built React app (frontend/dist) when present, so one process runs the whole demo.
DIST = BACKEND_DIR.parent / "frontend" / "dist"
if DIST.exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        f = DIST / path
        if path and f.is_file() and DIST in f.resolve().parents:
            return FileResponse(f)
        return FileResponse(DIST / "index.html")
