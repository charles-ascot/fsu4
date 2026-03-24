from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import FSU_NAME, FSU_VERSION, API_VERSION
from app.models.intelligence_record import ChimeraMeta, ChimeraResponse
from app.routers import ingest, registry
from app.routers.actions import router as actions_router
from app.routers.config import router as config_router, sources_router
from app.services import gmail_service, firestore_service  # noqa: F401 — firestore_service used in lifespan

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Establish Gmail watch on startup — renewed here and by Cloud Scheduler."""
    logger.info("Starting %s v%s", FSU_NAME, FSU_VERSION)
    try:
        watch_result = gmail_service.setup_gmail_watch()
        logger.info("Gmail watch active: %s", watch_result)
        # Store the starting historyId so the first notification can find its messages
        history_id = watch_result.get("historyId")
        if history_id:
            firestore_service.set_last_history_id(str(history_id))
    except Exception as exc:
        logger.error("Gmail watch setup failed: %s", exc, exc_info=True)
    yield
    logger.info("Shutting down %s", FSU_NAME)


app = FastAPI(
    title=FSU_NAME,
    version=FSU_VERSION,
    description="Chimera Email Data Collection FSU — transforms inbound emails into structured intelligence records.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://fsu4.thync.online"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Unhandled exception handler ───────────────────────────────────────────────

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception on %s: %s", request.url.path, exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "chimera_version": API_VERSION,
            "request_id": "error",
            "fsu": FSU_NAME,
            "status": "error",
            "timestamp": datetime.utcnow().isoformat(),
            "data": {},
            "errors": [str(exc)],
            "meta": {"processing_time_ms": 0, "version": FSU_VERSION},
        },
    )


# ── System endpoints ──────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    """Cloud Run liveness probe — no auth."""
    return {"status": "ok"}


@app.get("/status")
async def status():
    """Operational status snapshot — no auth."""
    start = time.monotonic()
    try:
        metrics = firestore_service.get_metrics()
        firestore_ok = True
    except Exception as exc:
        metrics = {}
        firestore_ok = False
        logger.warning("Firestore health check failed: %s", exc)

    elapsed = int((time.monotonic() - start) * 1000)
    return ChimeraResponse(
        request_id="status",
        status="success",
        data={
            "fsu": FSU_NAME,
            "version": FSU_VERSION,
            "firestore": "ok" if firestore_ok else "degraded",
            "registry_stats": metrics,
            "timestamp": datetime.utcnow().isoformat(),
        },
        meta=ChimeraMeta(processing_time_ms=elapsed),
    )


@app.get("/version")
async def version():
    """FSU and API version info — no auth."""
    return ChimeraResponse(
        request_id="version",
        status="success",
        data={
            "fsu": FSU_NAME,
            "fsu_version": FSU_VERSION,
            "api_version": API_VERSION,
            "ai_model": "claude-sonnet-4-20250514",
            "built_for": "chimera-platform",
        },
        meta=ChimeraMeta(),
    )


# ── Router mounts ─────────────────────────────────────────────────────────────

app.include_router(ingest.router, prefix="/v1/ingest", tags=["ingest"])
app.include_router(registry.router, prefix="/v1/registry", tags=["registry"])
app.include_router(actions_router, prefix="/v1/actions", tags=["actions"])
app.include_router(config_router, prefix="/v1/config", tags=["config"])
app.include_router(sources_router, prefix="/v1/sources", tags=["sources"])
