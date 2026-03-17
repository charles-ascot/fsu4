from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field
import uuid


class Intent(str, Enum):
    informational = "informational"
    action_required = "action_required"
    data_payload = "data_payload"
    alert = "alert"
    report = "report"


class Urgency(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class Sentiment(str, Enum):
    neutral = "neutral"
    positive = "positive"
    negative = "negative"


class RecordStatus(str, Enum):
    pending = "pending"
    processing = "processing"
    complete = "complete"
    failed = "failed"
    skipped = "skipped"


class Entities(BaseModel):
    people: list[str] = Field(default_factory=list)
    organisations: list[str] = Field(default_factory=list)
    race_venues: list[str] = Field(default_factory=list)
    horse_names: list[str] = Field(default_factory=list)
    monetary_values: list[str] = Field(default_factory=list)


class AttachmentRecord(BaseModel):
    filename: str
    content_type: str
    size_bytes: int
    gcs_path: str
    extracted_text_path: Optional[str] = None
    transcript_path: Optional[str] = None
    processing_status: str = "stored"


class IntelligenceRecord(BaseModel):
    # Identity
    record_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    status: RecordStatus = RecordStatus.pending
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Section 4.1 — Source Metadata
    message_id: str
    thread_id: str
    from_address: str
    from_name: str
    subject: str
    received_at: datetime
    forwarded_from: Optional[str] = None
    gmail_labels: list[str] = Field(default_factory=list)

    # Section 4.2 — AI-Generated Intelligence
    title: Optional[str] = Field(None, max_length=80)
    summary: Optional[str] = None
    topics: list[str] = Field(default_factory=list)
    entities: Entities = Field(default_factory=Entities)
    intent: Optional[Intent] = None
    urgency: Optional[Urgency] = None
    relevancy_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    relevancy_reasoning: Optional[str] = None
    chimera_domain_tags: list[str] = Field(default_factory=list)
    action_items: list[str] = Field(default_factory=list)
    contains_pii: Optional[bool] = None
    sentiment: Optional[Sentiment] = None

    # GCS paths
    gcs_raw_prefix: Optional[str] = None
    gcs_processed_prefix: Optional[str] = None

    # Attachments
    attachments: list[AttachmentRecord] = Field(default_factory=list)

    # Processing metadata
    processing_error: Optional[str] = None
    ai_model_used: Optional[str] = None
    processing_time_ms: Optional[int] = None

    def to_firestore_dict(self) -> dict:
        data = self.model_dump(mode="json")
        # Firestore stores datetimes as native datetime objects
        data["created_at"] = self.created_at
        data["updated_at"] = self.updated_at
        data["received_at"] = self.received_at
        return data

    @classmethod
    def from_firestore_dict(cls, data: dict) -> "IntelligenceRecord":
        # Convert Firestore DatetimeWithNanoseconds to datetime if needed
        for field in ("created_at", "updated_at", "received_at"):
            if hasattr(data.get(field), "timestamp"):
                data[field] = data[field].replace(tzinfo=None)
        return cls(**data)


class ChimeraRequest(BaseModel):
    chimera_version: str = "1.0"
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    issued_at: datetime = Field(default_factory=datetime.utcnow)
    issued_by: str = "system"
    payload: dict = Field(default_factory=dict)


class ChimeraMeta(BaseModel):
    processing_time_ms: int = 0
    version: str = "1.0.0"


class ChimeraResponse(BaseModel):
    chimera_version: str = "1.0"
    request_id: str
    fsu: str = "chimera-fsu-email-ingest"
    status: str = "success"
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    data: dict = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)
    meta: ChimeraMeta = Field(default_factory=ChimeraMeta)


class ForwardingSource(BaseModel):
    source_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    email_address: str
    display_name: Optional[str] = None
    description: Optional[str] = None
    active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    email_count: int = 0
    last_received_at: Optional[datetime] = None
