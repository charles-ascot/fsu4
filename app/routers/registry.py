from __future__ import annotations

import time
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status

from app.core.secrets import get_chimera_api_key
from app.models.intelligence_record import ChimeraMeta, ChimeraResponse
from app.services import ai_service, firestore_service

router = APIRouter()


def require_api_key(x_chimera_api_key: str = Header(..., alias="X-Chimera-API-Key")) -> None:
    expected = get_chimera_api_key()
    if x_chimera_api_key != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-Chimera-API-Key",
        )


@router.get("")
async def query_registry(
    topic: Optional[str] = Query(None),
    intent: Optional[str] = Query(None),
    urgency: Optional[str] = Query(None),
    domain_tag: Optional[str] = Query(None),
    sender: Optional[str] = Query(None),
    min_relevancy: Optional[float] = Query(None, ge=0.0, le=1.0),
    status_filter: Optional[str] = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    _: None = Depends(require_api_key),
):
    start = time.monotonic()
    records = firestore_service.query_records(
        topic=topic,
        intent=intent,
        urgency=urgency,
        domain_tag=domain_tag,
        sender=sender,
        min_relevancy=min_relevancy,
        status=status_filter,
        limit=limit,
        offset=offset,
    )
    elapsed = int((time.monotonic() - start) * 1000)

    return ChimeraResponse(
        request_id="registry-query",
        status="success",
        data={
            "records": [r.model_dump(mode="json") for r in records],
            "count": len(records),
            "limit": limit,
            "offset": offset,
        },
        meta=ChimeraMeta(processing_time_ms=elapsed),
    )


@router.get("/metrics")
async def get_metrics(_: None = Depends(require_api_key)):
    start = time.monotonic()
    metrics = firestore_service.get_metrics()
    elapsed = int((time.monotonic() - start) * 1000)
    return ChimeraResponse(
        request_id="registry-metrics",
        status="success",
        data=metrics,
        meta=ChimeraMeta(processing_time_ms=elapsed),
    )


@router.post("/agent/query")
async def agent_query(
    payload: dict,
    _: None = Depends(require_api_key),
):
    """
    AI agent integration endpoint — accepts a structured query and returns
    an AI-synthesised answer drawn from the registry.
    """
    start = time.monotonic()

    query_text = payload.get("query")
    if not query_text:
        raise HTTPException(status_code=400, detail="query field required")

    filters = payload.get("filters", {})
    limit = int(payload.get("limit", 20))

    records = firestore_service.query_records(
        topic=filters.get("topic"),
        intent=filters.get("intent"),
        urgency=filters.get("urgency"),
        domain_tag=filters.get("domain_tag"),
        sender=filters.get("sender"),
        min_relevancy=filters.get("min_relevancy"),
        limit=min(limit, 50),
    )

    context_records = [r.model_dump(mode="json") for r in records]
    answer = ai_service.agent_query(
        query=query_text,
        context_records=context_records,
        extra_hints=payload.get("domain_hints"),
    )

    elapsed = int((time.monotonic() - start) * 1000)
    return ChimeraResponse(
        request_id=payload.get("request_id", "agent-query"),
        status="success",
        data={
            "answer": answer,
            "records_consulted": len(context_records),
            "query": query_text,
        },
        meta=ChimeraMeta(processing_time_ms=elapsed),
    )


@router.get("/{record_id}")
async def get_record(
    record_id: str,
    _: None = Depends(require_api_key),
):
    start = time.monotonic()
    record = firestore_service.get_record(record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")
    elapsed = int((time.monotonic() - start) * 1000)
    return ChimeraResponse(
        request_id=record_id,
        status="success",
        data=record.model_dump(mode="json"),
        meta=ChimeraMeta(processing_time_ms=elapsed),
    )
