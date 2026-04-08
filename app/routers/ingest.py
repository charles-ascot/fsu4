from __future__ import annotations

import base64
import io
import json
import logging
import time
from datetime import datetime
from typing import Optional

import fitz  # PyMuPDF
import docx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from google.cloud import vision, speech

from app.core.config import ProcessingConfig
from app.models.intelligence_record import (
    ChimeraResponse,
    ChimeraMeta,
    IntelligenceRecord,
    RecordStatus,
)
from app.services import (
    ai_service,
    firestore_service,
    gmail_service,
    storage_service,
)
from app.routers.config import get_current_config
from app.routers.registry import require_api_key
from app.services import scn_service

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Pub/Sub push receiver ──────────────────────────────────────────────────────

@router.post("/pubsub-push", status_code=status.HTTP_204_NO_CONTENT)
async def pubsub_push(request: Request):
    """
    Cloud Pub/Sub push endpoint — called by Google when a new email arrives.
    Must return 2xx quickly; heavy processing is synchronous here since Cloud Run
    handles concurrency and the 300s timeout covers normal email sizes.
    """
    try:
        body = await request.json()
    except Exception:
        # Return 204 to avoid Pub/Sub retry storm on malformed messages
        return

    message = body.get("message", {})
    if not message:
        return

    data_b64 = message.get("data", "")
    if not data_b64:
        return

    try:
        payload = json.loads(base64.b64decode(data_b64).decode("utf-8"))
    except Exception as exc:
        logger.warning("Failed to decode Pub/Sub message: %s", exc)
        return

    history_id = payload.get("historyId")
    if not history_id:
        return

    # Use the previously stored historyId as startHistoryId so we see the
    # change that triggered this notification (Gmail returns records AFTER startHistoryId)
    start_history_id = firestore_service.get_last_history_id()
    if not start_history_id:
        # First notification — use one before current to capture this change
        start_history_id = str(int(history_id) - 1)

    config = get_current_config()
    new_messages = gmail_service.list_history(start_history_id)

    # Always advance the cursor regardless of whether we found messages
    firestore_service.set_last_history_id(str(history_id))

    for msg_stub in new_messages:
        message_id = msg_stub.get("id")
        if not message_id:
            continue
        try:
            _process_message(message_id, config)
        except Exception as exc:
            logger.error("Failed to process message %s: %s", message_id, exc, exc_info=True)


@router.post("/manual")
async def manual_ingest(
    payload: dict,
    _: None = Depends(require_api_key),
):
    """Manually trigger processing for a specific Gmail message ID."""
    start = time.monotonic()
    message_id = payload.get("message_id")
    if not message_id:
        raise HTTPException(status_code=400, detail="message_id required")

    config = get_current_config()
    record = _process_message(message_id, config)
    elapsed = int((time.monotonic() - start) * 1000)

    return ChimeraResponse(
        request_id=payload.get("request_id", record.record_id),
        status="success",
        data={"record_id": record.record_id, "status": record.status.value},
        meta=ChimeraMeta(processing_time_ms=elapsed),
    )


@router.post("/reprocess/{record_id}")
async def reprocess(
    record_id: str,
    _: None = Depends(require_api_key),
):
    """Re-run AI tagging on an existing record (e.g. after model upgrade)."""
    start = time.monotonic()
    record = firestore_service.get_record(record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")

    # Load body text from GCS
    body_text = ""
    if record.gcs_raw_prefix:
        try:
            body_text = storage_service.download_text(f"{record.gcs_raw_prefix}body.txt")
        except Exception as exc:
            logger.warning("Could not load body text for reprocess: %s", exc)

    config = get_current_config()
    extra_hints = config.extra_domain_hints

    try:
        record = ai_service.tag_email(record, body_text, extra_domain_hints=extra_hints)
    except Exception as exc:
        logger.error("AI retagging failed for %s: %s", record_id, exc)
        record = ai_service.fallback_tag_email(record)
        record.processing_error = str(exc)

    firestore_service.update_record(record)

    if record.gcs_processed_prefix:
        storage_service.store_processed_record(record.record_id, record.model_dump(mode="json"))

    elapsed = int((time.monotonic() - start) * 1000)
    return ChimeraResponse(
        request_id=record_id,
        status="success",
        data={"record_id": record.record_id, "status": record.status.value},
        meta=ChimeraMeta(processing_time_ms=elapsed),
    )


@router.get("/queue")
async def get_queue(_: None = Depends(require_api_key)):
    """View records currently in pending status."""
    pending = firestore_service.get_pending_records()
    return ChimeraResponse(
        request_id="queue-query",
        status="success",
        data={
            "pending_count": len(pending),
            "records": [
                {
                    "record_id": r.record_id,
                    "message_id": r.message_id,
                    "subject": r.subject,
                    "from_address": r.from_address,
                    "received_at": r.received_at.isoformat(),
                    "status": r.status.value,
                }
                for r in pending
            ],
        },
        meta=ChimeraMeta(),
    )


# ── Core processing pipeline ──────────────────────────────────────────────────

def _process_message(message_id: str, config: ProcessingConfig) -> IntelligenceRecord:
    """
    Full email processing pipeline:
    1. Idempotency check
    2. Fetch from Gmail
    3. Parse headers + body
    4. Skip check (sender/subject filters)
    5. Store raw artefacts to GCS
    6. Process attachments
    7. AI tagging via Claude
    8. Store processed record to GCS
    9. Write intelligence record to Firestore
    """
    # 1. Idempotency
    if firestore_service.message_already_processed(message_id):
        logger.info("Message %s already processed — skipping", message_id)
        existing = firestore_service.get_record_by_message_id(message_id)
        return existing

    # 2. Fetch full message
    raw_message = gmail_service.get_message(message_id)

    # 3. Parse
    parsed = gmail_service.parse_gmail_message(raw_message)

    # If the email was forwarded to this inbox, promote the original sender so
    # all downstream logic (SCN check, Registry, skip filters) sees the true author.
    # The actual forwarder's address is preserved in forwarded_from on the record.
    forwarder_address = None
    if parsed.original_from_address:
        forwarder_address = parsed.from_address  # e.g. charles.duckitt@ascotwm.com
        parsed.from_address = parsed.original_from_address
        parsed.from_name = parsed.original_from_name or parsed.from_name
        logger.info(
            "Forward detected — treating sender as %s (forwarded by %s)",
            parsed.from_address, forwarder_address,
        )

    # Build skeleton record for early Firestore write
    record = IntelligenceRecord(
        message_id=parsed.message_id,
        thread_id=parsed.thread_id,
        from_address=parsed.from_address,
        from_name=parsed.from_name,
        subject=parsed.subject,
        received_at=parsed.received_at,
        forwarded_from=forwarder_address or parsed.forwarded_from,
        gmail_labels=parsed.gmail_labels,
        status=RecordStatus.processing,
    )

    # 4. Skip checks
    if parsed.from_address in config.ignore_senders:
        record.status = RecordStatus.skipped
        firestore_service.create_record(record)
        logger.info("Skipping message %s — sender %s in ignore list", message_id, parsed.from_address)
        return record

    subject_lower = parsed.subject.lower()
    for keyword in config.ignore_subjects_containing:
        if keyword.lower() in subject_lower:
            record.status = RecordStatus.skipped
            firestore_service.create_record(record)
            logger.info("Skipping message %s — subject matches ignore keyword '%s'", message_id, keyword)
            return record

    # Write processing record early for observability
    firestore_service.create_record(record)

    # 5. Store raw artefacts
    metadata_dict = {
        "message_id": parsed.message_id,
        "thread_id": parsed.thread_id,
        "from_address": parsed.from_address,
        "from_name": parsed.from_name,
        "subject": parsed.subject,
        "received_at": parsed.received_at.isoformat(),
        "forwarded_from": parsed.forwarded_from,
        "gmail_labels": parsed.gmail_labels,
        "headers": parsed.raw_headers,
        "attachment_count": len(parsed.attachments),
    }

    gcs_raw_prefix = storage_service.store_raw_email(
        message_id=parsed.message_id,
        received_at=parsed.received_at,
        metadata=metadata_dict,
        body_text=parsed.body_text,
        body_html=parsed.body_html,
    )
    record.gcs_raw_prefix = gcs_raw_prefix

    # 6. Process attachments
    attachment_texts: list[dict] = []
    max_bytes = config.max_attachment_size_mb * 1024 * 1024

    for att in parsed.attachments:
        att_data: bytes = att.get("data") or b""
        att_filename: str = att["filename"]
        att_content_type: str = att["content_type"]
        att_size: int = att["size"]

        if not att_data:
            logger.warning("Attachment %s has no data — skipping extraction", att_filename)

        if att_size > max_bytes:
            logger.warning(
                "Attachment %s (%d bytes) exceeds limit — storing raw only",
                att_filename, att_size,
            )

        gcs_att_path = storage_service.store_raw_attachment(
            message_id=parsed.message_id,
            received_at=parsed.received_at,
            filename=att_filename,
            data=att_data,
            content_type=att_content_type,
        )

        from app.models.intelligence_record import AttachmentRecord
        att_record = AttachmentRecord(
            filename=att_filename,
            content_type=att_content_type,
            size_bytes=att_size,
            gcs_path=gcs_att_path,
        )

        extracted_text: Optional[str] = None

        if att_data and att_size <= max_bytes:
            extracted_text = _extract_attachment_text(
                data=att_data,
                filename=att_filename,
                content_type=att_content_type,
                config=config,
            )

        if extracted_text:
            ext_path = storage_service.store_extracted_text(
                record.record_id, att_filename, extracted_text
            )
            att_record.extracted_text_path = ext_path
            att_record.processing_status = "extracted"
            attachment_texts.append({"filename": att_filename, "text": extracted_text})

        record.attachments.append(att_record)

    # 7. AI tagging
    body_for_ai = parsed.body_text or _strip_html(parsed.body_html)

    try:
        record = ai_service.tag_email(
            record=record,
            body_text=body_for_ai,
            attachment_texts=attachment_texts if attachment_texts else None,
            extra_domain_hints=config.extra_domain_hints,
        )
    except Exception as exc:
        logger.error("AI tagging failed for message %s: %s", message_id, exc, exc_info=True)
        record = ai_service.fallback_tag_email(record)
        record.processing_error = str(exc)

    # Mark email processing — classify and send appropriate automated reply
    if parsed.from_address.lower() == scn_service.MARK_EMAIL:
        scn_service.process_mark_email(record, parsed, body_for_ai)

    # Apply relevancy threshold
    if (
        config.min_relevancy_threshold > 0.0
        and record.relevancy_score is not None
        and record.relevancy_score < config.min_relevancy_threshold
    ):
        logger.info(
            "Record %s relevancy %.2f below threshold %.2f — marking skipped",
            record.record_id, record.relevancy_score, config.min_relevancy_threshold,
        )
        record.status = RecordStatus.skipped

    # 8. Store processed record to GCS
    gcs_processed_prefix = storage_service.store_processed_record(
        record.record_id, record.model_dump(mode="json")
    )
    record.gcs_processed_prefix = gcs_processed_prefix

    # 9. Update Firestore
    firestore_service.update_record(record)

    # Update source stats
    firestore_service.increment_source_email_count(parsed.from_address)

    # Update daily manifest
    storage_service.update_daily_manifest(
        parsed.received_at,
        {
            "record_id": record.record_id,
            "message_id": parsed.message_id,
            "subject": parsed.subject,
            "from_address": parsed.from_address,
            "status": record.status.value,
            "relevancy_score": record.relevancy_score,
            "intent": record.intent.value if record.intent else None,
        },
    )

    logger.info(
        "Processed message %s → record %s (status=%s, relevancy=%.2f)",
        message_id,
        record.record_id,
        record.status.value,
        record.relevancy_score or 0.0,
    )
    return record


def _extract_attachment_text(
    data: bytes,
    filename: str,
    content_type: str,
    config: ProcessingConfig,
) -> Optional[str]:
    """Extract text from an attachment based on its type."""
    fname_lower = filename.lower()

    # PDF
    if (fname_lower.endswith(".pdf") or "pdf" in content_type) and config.enable_pdf_extraction:
        return _extract_pdf_text(data)

    # Word
    if (
        fname_lower.endswith(".docx") or "wordprocessingml" in content_type
    ) and config.enable_docx_extraction:
        return _extract_docx_text(data)

    # Image OCR
    if (
        content_type.startswith("image/") or fname_lower.endswith((".jpg", ".jpeg", ".png", ".gif", ".webp"))
    ) and config.enable_ocr:
        return _ocr_image(data)

    # Audio transcription
    if (
        content_type.startswith("audio/")
        or fname_lower.endswith((".mp3", ".wav", ".flac", ".ogg", ".m4a"))
    ) and config.enable_transcription:
        return _transcribe_audio(data, content_type)

    return None


def _extract_pdf_text(data: bytes) -> Optional[str]:
    try:
        doc = fitz.open(stream=data, filetype="pdf")
        texts = [page.get_text() for page in doc]
        doc.close()
        return "\n".join(texts).strip() or None
    except Exception as exc:
        logger.warning("PDF extraction failed: %s", exc)
        return None


def _extract_docx_text(data: bytes) -> Optional[str]:
    try:
        doc = docx.Document(io.BytesIO(data))
        return "\n".join(p.text for p in doc.paragraphs if p.text).strip() or None
    except Exception as exc:
        logger.warning("DOCX extraction failed: %s", exc)
        return None


def _ocr_image(data: bytes) -> Optional[str]:
    try:
        client = vision.ImageAnnotatorClient()
        image = vision.Image(content=data)
        response = client.text_detection(image=image)
        if response.error.message:
            logger.warning("Vision API error: %s", response.error.message)
            return None
        texts = response.text_annotations
        return texts[0].description.strip() if texts else None
    except Exception as exc:
        logger.warning("OCR failed: %s", exc)
        return None


def _transcribe_audio(data: bytes, content_type: str) -> Optional[str]:
    try:
        client = speech.SpeechClient()

        encoding_map = {
            "audio/flac": speech.RecognitionConfig.AudioEncoding.FLAC,
            "audio/wav": speech.RecognitionConfig.AudioEncoding.LINEAR16,
            "audio/x-wav": speech.RecognitionConfig.AudioEncoding.LINEAR16,
            "audio/mp3": speech.RecognitionConfig.AudioEncoding.MP3,
            "audio/mpeg": speech.RecognitionConfig.AudioEncoding.MP3,
        }
        encoding = encoding_map.get(
            content_type.lower(), speech.RecognitionConfig.AudioEncoding.ENCODING_UNSPECIFIED
        )

        audio = speech.RecognitionAudio(content=data)
        config = speech.RecognitionConfig(
            encoding=encoding,
            language_code="en-GB",
            enable_automatic_punctuation=True,
        )
        response = client.recognize(config=config, audio=audio)
        transcript = " ".join(
            result.alternatives[0].transcript for result in response.results
        )
        return transcript.strip() or None
    except Exception as exc:
        logger.warning("Audio transcription failed: %s", exc)
        return None


def _strip_html(html: str) -> str:
    """Very basic HTML tag stripping — used only when no plain-text body exists."""
    import re
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()
