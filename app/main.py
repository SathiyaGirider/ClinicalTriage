"""
LifeLine API (course-project PROTOTYPE, synthetic data only; not a medical device).

Run:  uvicorn app.main:app --reload
"""

import logging
import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.abdm_mock.router import router as abdm_router
from app.auth.router import router as auth_router
from app.booking.router import router as booking_router
from app.catalog.router import router as catalog_router
from app.common.logging_setup import configure_logging
from app.config import settings
from app.db import init_db
from app.doctor.router import router as doctor_router
from app.ehr.router import router as ehr_router
from app.intake.session_router import router as intake_session_router
from app.patient.router import router as patient_router
from app.pipeline.router import router as pipeline_router
from app.queue.router import router as queue_router
from app.triage.router import router as triage_router


configure_logging()
logger = logging.getLogger("lifeline.main")

DISCLAIMER = "Demo with synthetic data. Do not enter real health information."
AI_BANNER = "AI assists the care team. It does not diagnose or prescribe. A nurse or doctor decides."

app = FastAPI(
    title="LifeLine API (prototype)",
    version="0.1.0",
    description=f"{DISCLAIMER} {AI_BANNER} Course-project prototype; not clinically validated and not a medical product.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.frontend_origin.split(",") if o.strip()],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), geolocation=(self), microphone=(self)"
    response.headers["Cache-Control"] = response.headers.get("Cache-Control", "no-store")
    if not request.url.path.startswith(("/docs", "/redoc")):
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'")
    return response


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    logger.error("unhandled error path=%s error=%s", request.url.path, type(exc).__name__)
    return JSONResponse(status_code=500, content={"detail": "Something went wrong. Please try again."})


for r in (auth_router, catalog_router, booking_router, intake_session_router, pipeline_router, triage_router, queue_router,
          doctor_router, ehr_router, patient_router, abdm_router):
    app.include_router(r)


# Person A's original kiosk endpoints are kept in the codebase but they are
# unauthenticated, so they are only mounted when explicitly enabled.
if os.getenv("ENABLE_LEGACY_KIOSK", "false").lower() == "true":
    from app.intake.router import router as legacy_intake_router
    app.include_router(legacy_intake_router)


@app.get("/health", tags=["Meta"])
def health():
    return {"status": "ok", "llm_configured": settings.llm_configured, "ehr_backend": settings.ehr_backend,
            "disclaimer": DISCLAIMER, "ai_banner": AI_BANNER}


@app.get("/config/public", tags=["Meta"])
def public_config():
    return {"emergency_numbers": settings.emergency_numbers, "alert_amber_seconds": settings.alert_amber_seconds,
            "alert_red_seconds": settings.alert_red_seconds, "hold_minutes": settings.hold_minutes,
            "walkin_policy": settings.walkin_policy, "disclaimer": DISCLAIMER, "ai_banner": AI_BANNER,
            "dev_endpoints": settings.dev_endpoints}


@app.on_event("startup")
def _startup() -> None:
    init_db()
    if settings.seed_demo:
        from app.seed import seed_if_empty
        seed_if_empty()


# Serve the built frontend (frontend/dist) if present, so one process runs the demo.
_DIST = Path(__file__).resolve().parents[1] / "frontend" / "dist"
if _DIST.exists():
    app.mount("/assets", StaticFiles(directory=_DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        f = _DIST / path
        if path and f.is_file() and _DIST in f.resolve().parents:
            return FileResponse(f)
        return FileResponse(_DIST / "index.html")
else:
    @app.get("/favicon.ico", include_in_schema=False)
    def favicon():
        from fastapi import Response
        return Response(status_code=204)

    @app.get("/", include_in_schema=False)
    def root_dev_notice():
        return {
            "service": "LifeLine API (Prototype)",
            "status": "online",
            "frontend_dev_url": "http://localhost:5173",
            "swagger_docs": "http://localhost:8000/docs",
            "instructions": (
                "The backend is active on port 8000. To use the web interface, open http://localhost:5173 in your browser "
                "(started via 'npm run dev' in the frontend directory). Alternatively, run 'npm run build' in the frontend "
                "folder to bundle static files so port 8000 serves both API and web UI."
            ),
        }
