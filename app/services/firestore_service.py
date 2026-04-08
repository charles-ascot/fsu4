from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from google.cloud import firestore

from app.core.config import (
    FIRESTORE_COLLECTION,
    FIRESTORE_SOURCES_COLLECTION,
    FIRESTORE_CONFIG_DOC,
    GCP_PROJECT,
    ProcessingConfig,
)
from app.models.intelligence_record import (
    IntelligenceRecord,
    ForwardingSource,
    RecordStatus,
)

logger = logging.getLogger(__name__)

_client: firestore.Client | None = None


def _db() -> firestore.Client:
    global _client
    if _client is None:
        _client = firestore.Client(project=GCP_PROJECT)
    return _client


def _records() -> firestore.CollectionReference:
    return _db().collection(FIRESTORE_COLLECTION)


def _sources() -> firestore.CollectionReference:
    return _db().collection(FIRESTORE_SOURCES_COLLECTION)


def _config_ref() -> firestore.DocumentReference:
    return _db().collection("chimera-fsu-config").document(FIRESTORE_CONFIG_DOC)


# ── Idempotency ───────────────────────────────────────────────────────────────

def message_already_processed(message_id: str) -> bool:
    """Return True if this Gmail message_id already has a record in Firestore."""
    query = _records().where("message_id", "==", message_id).limit(1).stream()
    return any(True for _ in query)


def delete_record(record_id: str) -> None:
    _records().document(record_id).delete()


def get_record_by_message_id(message_id: str) -> Optional[IntelligenceRecord]:
    query = _records().where("message_id", "==", message_id).limit(1).stream()
    for doc in query:
        return IntelligenceRecord.from_firestore_dict(doc.to_dict())
    return None


# ── CRUD ──────────────────────────────────────────────────────────────────────

def create_record(record: IntelligenceRecord) -> str:
    doc_ref = _records().document(record.record_id)
    doc_ref.set(record.to_firestore_dict())
    logger.info("Created Firestore record %s for message %s", record.record_id, record.message_id)
    return record.record_id


def update_record(record: IntelligenceRecord) -> None:
    record.updated_at = datetime.utcnow()
    doc_ref = _records().document(record.record_id)
    doc_ref.set(record.to_firestore_dict())


def get_record(record_id: str) -> Optional[IntelligenceRecord]:
    doc = _records().document(record_id).get()
    if not doc.exists:
        return None
    return IntelligenceRecord.from_firestore_dict(doc.to_dict())


def query_records(
    topic: Optional[str] = None,
    intent: Optional[str] = None,
    urgency: Optional[str] = None,
    domain_tag: Optional[str] = None,
    sender: Optional[str] = None,
    min_relevancy: Optional[float] = None,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> list[IntelligenceRecord]:
    query = _records()

    if intent:
        query = query.where("intent", "==", intent)
    if urgency:
        query = query.where("urgency", "==", urgency)
    if status:
        query = query.where("status", "==", status)
    if sender:
        query = query.where("from_address", "==", sender.lower())
    if min_relevancy is not None:
        query = query.where("relevancy_score", ">=", min_relevancy)

    query = query.order_by("received_at", direction=firestore.Query.DESCENDING)
    query = query.limit(limit + offset)

    results = []
    for i, doc in enumerate(query.stream()):
        if i < offset:
            continue
        rec = IntelligenceRecord.from_firestore_dict(doc.to_dict())
        # Post-filter array fields (Firestore doesn't support array-contains + other filters well)
        if topic and topic not in rec.topics:
            continue
        if domain_tag and domain_tag not in rec.chimera_domain_tags:
            continue
        results.append(rec)

    return results


def get_metrics() -> dict:
    """Return processing statistics from the registry."""
    all_docs = _records().stream()

    total = 0
    by_status: dict[str, int] = {}
    by_intent: dict[str, int] = {}
    by_urgency: dict[str, int] = {}

    for doc in all_docs:
        data = doc.to_dict()
        total += 1
        s = data.get("status", "unknown")
        by_status[s] = by_status.get(s, 0) + 1
        i = data.get("intent")
        if i:
            by_intent[i] = by_intent.get(i, 0) + 1
        u = data.get("urgency")
        if u:
            by_urgency[u] = by_urgency.get(u, 0) + 1

    return {
        "total_records": total,
        "by_status": by_status,
        "by_intent": by_intent,
        "by_urgency": by_urgency,
    }


def get_pending_records(limit: int = 100) -> list[IntelligenceRecord]:
    query = (
        _records()
        .where("status", "==", RecordStatus.pending.value)
        .order_by("received_at")
        .limit(limit)
    )
    return [IntelligenceRecord.from_firestore_dict(d.to_dict()) for d in query.stream()]


# ── SCN (Strategy Change Notice) ──────────────────────────────────────────────

def get_next_reference(prefix: str) -> str:
    """
    Generate the next reference for a given prefix using an atomic daily counter.
    Format: {PREFIX}-YYYYMMDD-001
    Examples: SCN-20260323-001, SDR-20260323-001
    """
    date_str = datetime.utcnow().strftime("%Y%m%d")
    counter_ref = _db().collection("chimera-fsu-system").document(
        f"{prefix.lower()}-counter-{date_str}"
    )

    @firestore.transactional
    def _increment(transaction, ref):
        snapshot = ref.get(transaction=transaction)
        seq = ((snapshot.to_dict() or {}).get("seq", 0)) + 1
        transaction.set(ref, {"seq": seq, "date": date_str})
        return seq

    transaction = _db().transaction()
    seq = _increment(transaction, counter_ref)
    return f"{prefix.upper()}-{date_str}-{seq:03d}"


def store_mark_record(collection: str, doc_id: str, data: dict) -> None:
    """Store a Mark-related process record (SCN, SDR, etc.) to Firestore."""
    _db().collection(collection).document(doc_id).set(data)


def get_action_items(limit: int = 100) -> list[dict]:
    """
    Return pending action items from both SCN and SDR collections,
    merged and sorted by created_at descending.
    """
    items = []

    for collection in ("chimera-scn-records", "chimera-sdr-records"):
        try:
            docs = (
                _db().collection(collection)
                .order_by("created_at", direction=firestore.Query.DESCENDING)
                .limit(limit)
                .stream()
            )
            for doc in docs:
                data = doc.to_dict()
                # Normalise created_at to isoformat string
                created = data.get("created_at")
                if hasattr(created, "isoformat"):
                    data["created_at"] = created.isoformat()
                items.append(data)
        except Exception:
            pass  # collection may not exist yet

    items.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return items[:limit]


# ── Gmail watch state ─────────────────────────────────────────────────────────

def get_last_history_id() -> Optional[str]:
    doc = _db().collection("chimera-fsu-system").document("gmail-watch").get()
    if doc.exists:
        return doc.to_dict().get("last_history_id")
    return None


def set_last_history_id(history_id: str) -> None:
    _db().collection("chimera-fsu-system").document("gmail-watch").set(
        {"last_history_id": history_id, "updated_at": datetime.utcnow()}
    )


# ── Config ────────────────────────────────────────────────────────────────────

def load_config() -> ProcessingConfig:
    doc = _config_ref().get()
    if doc.exists:
        return ProcessingConfig(**doc.to_dict())
    return ProcessingConfig()


def save_config(config: ProcessingConfig) -> None:
    _config_ref().set(config.model_dump())


# ── Sources ───────────────────────────────────────────────────────────────────

def list_sources() -> list[ForwardingSource]:
    return [
        ForwardingSource(**d.to_dict())
        for d in _sources().order_by("created_at").stream()
    ]


def create_source(source: ForwardingSource) -> str:
    _sources().document(source.source_id).set(source.model_dump(mode="json"))
    return source.source_id


def delete_source(source_id: str) -> bool:
    doc_ref = _sources().document(source_id)
    if not doc_ref.get().exists:
        return False
    doc_ref.delete()
    return True


def get_source(source_id: str) -> Optional[ForwardingSource]:
    doc = _sources().document(source_id).get()
    if not doc.exists:
        return None
    return ForwardingSource(**doc.to_dict())


def increment_source_email_count(from_address: str) -> None:
    """Increment email count for a matching source by email address."""
    query = _sources().where("email_address", "==", from_address).limit(1).stream()
    for doc in query:
        doc.reference.update(
            {
                "email_count": firestore.Increment(1),
                "last_received_at": datetime.utcnow(),
            }
        )
        return
