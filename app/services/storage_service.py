from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Optional

from google.cloud import storage

from app.core.config import GCS_BUCKET

logger = logging.getLogger(__name__)

_client: storage.Client | None = None


def _get_client() -> storage.Client:
    global _client
    if _client is None:
        _client = storage.Client()
    return _client


def _bucket() -> storage.Bucket:
    return _get_client().bucket(GCS_BUCKET)


# ── GCS path helpers ─────────────────────────────────────────────────────────

def raw_prefix(message_id: str, received_at: datetime) -> str:
    """raw/{year}/{month}/{day}/{message_id}/"""
    return (
        f"raw/{received_at.year:04d}/{received_at.month:02d}/"
        f"{received_at.day:02d}/{message_id}/"
    )


def processed_prefix(record_id: str) -> str:
    """processed/{record_id}/"""
    return f"processed/{record_id}/"


def daily_manifest_path(date: datetime) -> str:
    return f"index/daily_manifest_{date.strftime('%Y-%m-%d')}.json"


# ── Upload helpers ────────────────────────────────────────────────────────────

def upload_bytes(gcs_path: str, data: bytes, content_type: str = "application/octet-stream") -> str:
    blob = _bucket().blob(gcs_path)
    blob.upload_from_string(data, content_type=content_type)
    logger.debug("Uploaded %d bytes to gs://%s/%s", len(data), GCS_BUCKET, gcs_path)
    return gcs_path


def upload_text(gcs_path: str, text: str, content_type: str = "text/plain; charset=utf-8") -> str:
    return upload_bytes(gcs_path, text.encode("utf-8"), content_type)


def upload_json(gcs_path: str, obj: dict) -> str:
    data = json.dumps(obj, indent=2, default=str).encode("utf-8")
    return upload_bytes(gcs_path, data, "application/json")


def download_bytes(gcs_path: str) -> bytes:
    blob = _bucket().blob(gcs_path)
    return blob.download_as_bytes()


def download_text(gcs_path: str) -> str:
    return download_bytes(gcs_path).decode("utf-8", errors="replace")


def download_json(gcs_path: str) -> dict:
    return json.loads(download_bytes(gcs_path))


def blob_exists(gcs_path: str) -> bool:
    return _bucket().blob(gcs_path).exists()


# ── Email-specific store operations ──────────────────────────────────────────

def store_raw_email(
    message_id: str,
    received_at: datetime,
    metadata: dict,
    body_text: str,
    body_html: str,
) -> str:
    """
    Store raw email artefacts under:
      raw/{year}/{month}/{day}/{message_id}/
        email_metadata.json
        body.txt
        body.html
    Returns the GCS prefix.
    """
    prefix = raw_prefix(message_id, received_at)
    upload_json(f"{prefix}email_metadata.json", metadata)
    upload_text(f"{prefix}body.txt", body_text)
    upload_text(f"{prefix}body.html", body_html, content_type="text/html; charset=utf-8")
    logger.info("Raw email stored at gs://%s/%s", GCS_BUCKET, prefix)
    return prefix


def store_raw_attachment(
    message_id: str,
    received_at: datetime,
    filename: str,
    data: bytes,
    content_type: str,
) -> str:
    """
    Store attachment under:
      raw/{year}/{month}/{day}/{message_id}/attachments/{filename}
    Returns the GCS path.
    """
    prefix = raw_prefix(message_id, received_at)
    path = f"{prefix}attachments/{filename}"
    upload_bytes(path, data, content_type)
    return path


def store_processed_record(record_id: str, record_dict: dict) -> str:
    """
    Store complete intelligence record under:
      processed/{record_id}/record.json
    Returns the GCS prefix.
    """
    prefix = processed_prefix(record_id)
    upload_json(f"{prefix}record.json", record_dict)
    return prefix


def store_extracted_text(record_id: str, filename: str, text: str) -> str:
    """
    Store extracted attachment text under:
      processed/{record_id}/extracted_texts/{filename}.txt
    Returns the GCS path.
    """
    prefix = processed_prefix(record_id)
    path = f"{prefix}extracted_texts/{filename}.txt"
    upload_text(path, text)
    return path


def store_transcript(record_id: str, filename: str, transcript: str) -> str:
    """
    Store audio transcript under:
      processed/{record_id}/transcripts/{filename}.txt
    Returns the GCS path.
    """
    prefix = processed_prefix(record_id)
    path = f"{prefix}transcripts/{filename}.txt"
    upload_text(path, transcript)
    return path


def update_daily_manifest(date: datetime, record_summary: dict) -> None:
    """Append a record summary to today's daily manifest JSON."""
    path = daily_manifest_path(date)
    if blob_exists(path):
        manifest = download_json(path)
    else:
        manifest = {"date": date.strftime("%Y-%m-%d"), "records": []}

    manifest["records"].append(record_summary)
    manifest["total"] = len(manifest["records"])
    upload_json(path, manifest)
