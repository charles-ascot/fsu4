from __future__ import annotations

import time
from functools import lru_cache

from fastapi import APIRouter, Depends

from app.core.config import CONFIG_JSON_SCHEMA, ProcessingConfig
from app.models.intelligence_record import ChimeraMeta, ChimeraResponse, ForwardingSource
from app.services import firestore_service
from app.routers.registry import require_api_key

router = APIRouter()

# In-process cache of current config — loaded from Firestore on first access
_config_cache: ProcessingConfig | None = None


def get_current_config() -> ProcessingConfig:
    global _config_cache
    if _config_cache is None:
        _config_cache = firestore_service.load_config()
    return _config_cache


def _invalidate_config_cache() -> None:
    global _config_cache
    _config_cache = None


# ── Config endpoints ──────────────────────────────────────────────────────────

@router.get("")
async def get_config(_: None = Depends(require_api_key)):
    start = time.monotonic()
    config = get_current_config()
    elapsed = int((time.monotonic() - start) * 1000)
    return ChimeraResponse(
        request_id="config-get",
        status="success",
        data=config.model_dump(),
        meta=ChimeraMeta(processing_time_ms=elapsed),
    )


@router.put("")
async def update_config(
    payload: dict,
    _: None = Depends(require_api_key),
):
    start = time.monotonic()
    current = get_current_config()
    updated_data = {**current.model_dump(), **payload}
    new_config = ProcessingConfig(**updated_data)
    firestore_service.save_config(new_config)
    _invalidate_config_cache()
    elapsed = int((time.monotonic() - start) * 1000)
    return ChimeraResponse(
        request_id="config-update",
        status="success",
        data=new_config.model_dump(),
        meta=ChimeraMeta(processing_time_ms=elapsed),
    )


@router.get("/schema")
async def get_config_schema(_: None = Depends(require_api_key)):
    return ChimeraResponse(
        request_id="config-schema",
        status="success",
        data={"schema": CONFIG_JSON_SCHEMA},
        meta=ChimeraMeta(),
    )


# ── Sources endpoints ─────────────────────────────────────────────────────────

sources_router = APIRouter()


@sources_router.get("")
async def list_sources(_: None = Depends(require_api_key)):
    start = time.monotonic()
    sources = firestore_service.list_sources()
    elapsed = int((time.monotonic() - start) * 1000)
    return ChimeraResponse(
        request_id="sources-list",
        status="success",
        data={
            "sources": [s.model_dump(mode="json") for s in sources],
            "count": len(sources),
        },
        meta=ChimeraMeta(processing_time_ms=elapsed),
    )


@sources_router.post("")
async def create_source(
    payload: dict,
    _: None = Depends(require_api_key),
):
    start = time.monotonic()
    source = ForwardingSource(
        email_address=payload["email_address"],
        display_name=payload.get("display_name"),
        description=payload.get("description"),
    )
    source_id = firestore_service.create_source(source)
    elapsed = int((time.monotonic() - start) * 1000)
    return ChimeraResponse(
        request_id="sources-create",
        status="success",
        data={"source_id": source_id, **source.model_dump(mode="json")},
        meta=ChimeraMeta(processing_time_ms=elapsed),
    )


@sources_router.delete("/{source_id}")
async def delete_source(
    source_id: str,
    _: None = Depends(require_api_key),
):
    start = time.monotonic()
    deleted = firestore_service.delete_source(source_id)
    if not deleted:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Source not found")
    elapsed = int((time.monotonic() - start) * 1000)
    return ChimeraResponse(
        request_id="sources-delete",
        status="success",
        data={"source_id": source_id, "deleted": True},
        meta=ChimeraMeta(processing_time_ms=elapsed),
    )
