from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Optional

GCP_PROJECT = "chimera-v4"
GCP_REGION = "europe-west2"
CLOUD_RUN_SERVICE = "fsu4"
FSU_NAME = "fsu4"
FSU_VERSION = "1.0.0"
API_VERSION = "1.0"

GMAIL_ADDRESS = "chimera.data.in@gmail.com"
PUBSUB_TOPIC = "fsu4-trigger"
PUBSUB_SUBSCRIPTION = "fsu4-sub"

GCS_BUCKET = "chimera-ops-email-raw"

FIRESTORE_COLLECTION = "fsu4-intelligence"
FIRESTORE_SOURCES_COLLECTION = "fsu4-sources"
FIRESTORE_CONFIG_DOC = "fsu4-config"

CLAUDE_MODEL = "claude-sonnet-4-20250514"
CLAUDE_MAX_TOKENS = 4096

CHIMERA_DOMAIN_HINTS = [
    "horse racing",
    "lay betting",
    "betfair",
    "form guide",
    "stake management",
    "signal intelligence",
    "spread control",
    "market data",
    "racing tips",
    "trading strategy",
]


class ProcessingConfig(BaseModel):
    ignore_senders: list[str] = Field(
        default_factory=list,
        description="Email addresses to skip processing entirely",
    )
    ignore_subjects_containing: list[str] = Field(
        default_factory=list,
        description="Subject keywords that trigger skip (case-insensitive)",
    )
    min_relevancy_threshold: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Minimum relevancy score to store in Firestore",
    )
    max_attachment_size_mb: int = Field(
        default=50,
        description="Maximum attachment size in MB to process",
    )
    enable_ocr: bool = Field(default=True, description="Enable image OCR via Vision API")
    enable_transcription: bool = Field(
        default=True, description="Enable audio transcription via Speech-to-Text"
    )
    enable_pdf_extraction: bool = Field(
        default=True, description="Enable PDF text extraction via PyMuPDF"
    )
    enable_docx_extraction: bool = Field(
        default=True, description="Enable Word document text extraction"
    )
    cloud_run_timeout_seconds: int = Field(
        default=300, description="Cloud Run request timeout"
    )
    gmail_watch_expiry_buffer_hours: int = Field(
        default=24,
        description="Hours before Gmail watch expiry to trigger renewal",
    )
    extra_domain_hints: list[str] = Field(
        default_factory=list,
        description="Additional domain hints passed to Claude for relevancy scoring",
    )


CONFIG_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "ignore_senders": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Email addresses to skip processing entirely",
        },
        "ignore_subjects_containing": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Subject keywords that trigger skip (case-insensitive)",
        },
        "min_relevancy_threshold": {
            "type": "number",
            "minimum": 0.0,
            "maximum": 1.0,
            "description": "Minimum relevancy score to store in Firestore",
        },
        "max_attachment_size_mb": {
            "type": "integer",
            "description": "Maximum attachment size in MB to process",
        },
        "enable_ocr": {"type": "boolean"},
        "enable_transcription": {"type": "boolean"},
        "enable_pdf_extraction": {"type": "boolean"},
        "enable_docx_extraction": {"type": "boolean"},
        "cloud_run_timeout_seconds": {"type": "integer"},
        "gmail_watch_expiry_buffer_hours": {"type": "integer"},
        "extra_domain_hints": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
    "additionalProperties": False,
}
