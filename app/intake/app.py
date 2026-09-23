"""
Standalone FastAPI application for the Intake Module.

Enables independent development, testing, and OpenAPI Swagger documentation (/docs)
without touching main.py.

To run:
    uvicorn app.intake.app:app --reload --port 8000
"""

import os
# Reload trigger
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.intake.router import router as intake_router

app = FastAPI(
    title="ClinicalTriage — Intake Module (Person A)",
    description=(
        "Patient Voice & Text Intake module with English and Tamil Web Speech API support, "
        "hybrid LLM extraction with deterministic guardrails, red-flag keyword scanning, "
        "and strict IntakeResult schema conformance."
    ),
    version="1.0.0",
)

# Enable CORS for frontend flexibility
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Intake router
app.include_router(intake_router)

# Mount static folder for browser Web Speech API demo client
STATIC_DIR = Path(__file__).parent / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/", include_in_schema=False)
    @app.get("/kiosk", include_in_schema=False)
    async def serve_kiosk_ui():
        kiosk_file = STATIC_DIR / "kiosk.html"
        if kiosk_file.exists():
            return FileResponse(kiosk_file)
        return {"message": "Kiosk interface ready. Visit /docs for OpenAPI specifications."}

    @app.get("/form", include_in_schema=False)
    async def serve_form_ui():
        index_file = STATIC_DIR / "index.html"
        if index_file.exists():
            return FileResponse(index_file)
        return {"message": "Form interface ready."}

    @app.get("/records", include_in_schema=False)
    async def serve_records_ui():
        records_file = STATIC_DIR / "records.html"
        if records_file.exists():
            return FileResponse(records_file)
        return {"message": "Records viewer ready."}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
