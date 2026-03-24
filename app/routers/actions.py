"""
Actions endpoint — exposes pending SCN and SDR items as a to-do list.

GET /v1/actions          — list all action items (SCN + SDR), newest first
GET /v1/actions/{ref}    — get a single action item by reference

Each item includes: ref, type, subject, summary, self_notes,
status, created_at, reply_sent.
"""
from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException, Query

from app.models.intelligence_record import ChimeraMeta, ChimeraResponse
from app.routers.registry import require_api_key
from app.services import firestore_service

router = APIRouter()


@router.get("")
async def list_actions(
    limit: int = Query(50, ge=1, le=200),
    _: None = Depends(require_api_key),
):
    """
    Return all pending action items from Mark's strategy emails.
    Includes SCN (strategy instructions) and SDR (strategy development requests).
    """
    start = time.monotonic()
    items = firestore_service.get_action_items(limit=limit)
    elapsed = int((time.monotonic() - start) * 1000)

    return ChimeraResponse(
        request_id="actions-list",
        status="success",
        data={
            "items": items,
            "count": len(items),
        },
        meta=ChimeraMeta(processing_time_ms=elapsed),
    )


@router.get("/{ref}")
async def get_action(
    ref: str,
    _: None = Depends(require_api_key),
):
    """Fetch a single action item by its reference (e.g. SCN-20260323-001)."""
    start = time.monotonic()

    collection = "chimera-scn-records" if ref.startswith("SCN-") else "chimera-sdr-records"
    doc = firestore_service._db().collection(collection).document(ref).get()

    if not doc.exists:
        raise HTTPException(status_code=404, detail=f"Action {ref} not found")

    data = doc.to_dict()
    created = data.get("created_at")
    if hasattr(created, "isoformat"):
        data["created_at"] = created.isoformat()

    elapsed = int((time.monotonic() - start) * 1000)
    return ChimeraResponse(
        request_id=ref,
        status="success",
        data=data,
        meta=ChimeraMeta(processing_time_ms=elapsed),
    )
