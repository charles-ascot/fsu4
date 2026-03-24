"""
Mark Insley email processing — classification and automated response.

All emails from mark.insley@ascotwm.com are classified by Claude into one of:
  - strategy_instruction  → full SCN process + 5-step reply
  - strategy_development  → SDR process + 3-step reply
  - strategy_discussion   → log + simple acknowledgement
  - general_correspondence→ log + simple acknowledgement

Design note: AI classification now. Once enough labelled data exists, the
classify_mark_email() call can be swapped for a rules-based classifier with
no changes to the rest of the pipeline.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from typing import Optional

import anthropic

from app.core.config import CLAUDE_MODEL
from app.core.secrets import get_anthropic_api_key
from app.services import firestore_service, gmail_service
from app.models.intelligence_record import IntelligenceRecord
from app.services.gmail_service import ParsedEmail

logger = logging.getLogger(__name__)

MARK_EMAIL = "mark.insley@ascotwm.com"

_SELF_NOTE_PATTERNS = [
    r"I will have to\b[^.!?\n]+[.!?]?",
    r"I need to\b[^.!?\n]+[.!?]?",
    r"I should\b[^.!?\n]+[.!?]?",
    r"I must\b[^.!?\n]+[.!?]?",
    r"I think I(?:'ll| will| should| need)[^.!?\n]+[.!?]?",
]

_CLASSIFICATION_PROMPT = """You are classifying an inbound email from Mark Insley at Ascot Wealth Management to Charles Duckitt, his trading operations manager.

Classify this email into exactly ONE of these four types:

strategy_instruction — Mark is giving a specific parameter change, rule adjustment, or direct instruction to modify the live trading engine. Contains specific numbers, ranges, formulas, or explicit statements about what should or should not happen. Examples: odds band changes, stake adjustments, RPR weight updates, rule overrides, specific percentage adjustments.

strategy_development — Mark is exploring a new idea, requesting a test, backtest, dry run, or data pull, or proposing a new rule that needs testing before going live. Exploratory or research in nature. Examples: "can you test this", "what data do we need", "I want to try a new rule", asking for Betfair streaming data, requesting specific fields or file formats.

strategy_discussion — Mark is thinking out loud, sharing research or analysis (including from external AI tools like ChatGPT), reflecting on past performance, or discussing theoretical concepts. No specific instruction or test request embedded. Examples: sharing a ChatGPT conversation, reflecting on market efficiency, analysing concepts like overround.

general_correspondence — Brief conversational message with no strategy content. Examples: "let me look at it tonight", "noted", "I'll get back to you", short one or two line acknowledgements.

Email subject: {subject}
Email body (first 600 chars): {body}

Return ONLY valid JSON with no preamble:
{{"type": "<strategy_instruction|strategy_development|strategy_discussion|general_correspondence>", "confidence": <0.0-1.0>, "reasoning": "<one sentence max>"}}"""


# ── Classification ─────────────────────────────────────────────────────────────

def classify_mark_email(parsed: ParsedEmail, body_text: str) -> dict:
    """
    Use Claude to classify a Mark email into one of the four types.
    Returns dict with keys: type, confidence, reasoning.
    Falls back to strategy_discussion on any error.
    """
    client = anthropic.Anthropic(api_key=get_anthropic_api_key())
    body_truncated = body_text[:600] if body_text else parsed.subject

    prompt = _CLASSIFICATION_PROMPT.format(
        subject=parsed.subject,
        body=body_truncated,
    )

    try:
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=150,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text.strip()
        # Strip markdown fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()
        result = json.loads(raw)
        logger.info("Mark email classified: type=%s confidence=%.2f | %s",
                    result.get("type"), result.get("confidence", 0), result.get("reasoning", ""))
        return result
    except Exception as exc:
        logger.warning("Mark email classification failed, defaulting to strategy_discussion: %s", exc)
        return {"type": "strategy_discussion", "confidence": 0.0, "reasoning": "classification error"}


def extract_self_notes(body_text: str) -> list[str]:
    """Extract self-directed commitments from Mark's email body."""
    notes = []
    for pattern in _SELF_NOTE_PATTERNS:
        for match in re.finditer(pattern, body_text, re.IGNORECASE):
            note = match.group(0).strip().rstrip(".")
            if note and note not in notes:
                notes.append(note)
    return notes


# ── Main dispatcher ────────────────────────────────────────────────────────────

def process_mark_email(
    record: IntelligenceRecord,
    parsed: ParsedEmail,
    body_text: str,
) -> Optional[str]:
    """
    Entry point for all Mark emails. Classifies and routes to the correct handler.
    Returns a reference string (SCN/SDR/None) for logging.
    """
    classification = classify_mark_email(parsed, body_text)
    email_type = classification.get("type", "strategy_discussion")

    # Store the classification on the Firestore record tags
    record.chimera_domain_tags = list(set(
        record.chimera_domain_tags + [f"mark-{email_type.replace('_', '-')}"]
    ))

    if email_type == "strategy_instruction":
        return _process_strategy_instruction(record, parsed, body_text)
    elif email_type == "strategy_development":
        return _process_strategy_development(record, parsed, body_text)
    else:
        # strategy_discussion and general_correspondence share the same simple ack
        return _process_simple_ack(record, parsed)


# ── Handlers ───────────────────────────────────────────────────────────────────

def _process_strategy_instruction(
    record: IntelligenceRecord,
    parsed: ParsedEmail,
    body_text: str,
) -> Optional[str]:
    """Full SCN process: generate reference, send 5-step reply, store Firestore record."""
    try:
        scn_ref = firestore_service.get_next_reference("SCN")
        self_notes = extract_self_notes(body_text)
        instruction_summary = record.summary or parsed.subject

        gmail_service.send_reply(
            to_address=MARK_EMAIL,
            subject=f"Strategy Instruction Received — {scn_ref}",
            body_html=_build_scn_reply_html(scn_ref, parsed.subject, instruction_summary, self_notes),
            thread_id=parsed.thread_id,
            in_reply_to=parsed.raw_headers.get("message-id", ""),
        )

        firestore_service.store_mark_record("chimera-scn-records", scn_ref, {
            "type": "strategy_instruction",
            "scn_ref": scn_ref,
            "record_id": record.record_id,
            "message_id": parsed.message_id,
            "thread_id": parsed.thread_id,
            "subject": parsed.subject,
            "instruction_summary": instruction_summary,
            "self_notes": self_notes,
            "status": "pending_scn",
            "created_at": datetime.utcnow(),
            "reply_sent": True,
            "asana_task_created": False,
        })

        record.action_items = list(set(record.action_items + [f"SCN raised: {scn_ref}"]))
        logger.info("SCN complete: %s → %s (self_notes=%d)", parsed.message_id, scn_ref, len(self_notes))
        return scn_ref

    except Exception as exc:
        logger.error("SCN process failed for %s: %s", parsed.message_id, exc, exc_info=True)
        return None


def _process_strategy_development(
    record: IntelligenceRecord,
    parsed: ParsedEmail,
    body_text: str,
) -> Optional[str]:
    """SDR process: generate reference, send 3-step reply, store Firestore record."""
    try:
        sdr_ref = firestore_service.get_next_reference("SDR")
        self_notes = extract_self_notes(body_text)
        summary = record.summary or parsed.subject

        gmail_service.send_reply(
            to_address=MARK_EMAIL,
            subject=f"Strategy Development Request Received — {sdr_ref}",
            body_html=_build_sdr_reply_html(sdr_ref, parsed.subject, summary, self_notes),
            thread_id=parsed.thread_id,
            in_reply_to=parsed.raw_headers.get("message-id", ""),
        )

        firestore_service.store_mark_record("chimera-sdr-records", sdr_ref, {
            "type": "strategy_development",
            "sdr_ref": sdr_ref,
            "record_id": record.record_id,
            "message_id": parsed.message_id,
            "thread_id": parsed.thread_id,
            "subject": parsed.subject,
            "summary": summary,
            "self_notes": self_notes,
            "status": "pending_development",
            "created_at": datetime.utcnow(),
            "reply_sent": True,
        })

        record.action_items = list(set(record.action_items + [f"SDR raised: {sdr_ref}"]))
        logger.info("SDR complete: %s → %s", parsed.message_id, sdr_ref)
        return sdr_ref

    except Exception as exc:
        logger.error("SDR process failed for %s: %s", parsed.message_id, exc, exc_info=True)
        return None


def _process_simple_ack(
    record: IntelligenceRecord,
    parsed: ParsedEmail,
) -> Optional[str]:
    """Send a simple acknowledgement for discussion and general correspondence emails."""
    try:
        gmail_service.send_reply(
            to_address=MARK_EMAIL,
            subject=f"RE: {parsed.subject}",
            body_html=_build_simple_ack_html(),
            thread_id=parsed.thread_id,
            in_reply_to=parsed.raw_headers.get("message-id", ""),
        )
        logger.info("Simple ack sent for %s", parsed.message_id)
        return None

    except Exception as exc:
        logger.error("Simple ack failed for %s: %s", parsed.message_id, exc, exc_info=True)
        return None


# ── Reply templates ────────────────────────────────────────────────────────────

def _build_scn_reply_html(
    scn_ref: str,
    original_subject: str,
    instruction_summary: str,
    self_notes: list[str],
) -> str:
    summary_display = (instruction_summary[:400] + "…") if len(instruction_summary) > 400 else instruction_summary

    if self_notes:
        notes_html = "".join(f"<li>{note}</li>" for note in self_notes)
        step_5 = f"""<p><strong>5. Your noted commitments</strong><br>
During your message you also noted the following for your own action:</p>
<ul style="margin: 8px 0; padding-left: 20px;">{notes_html}</ul>
<p>These have been recorded and are on file. Charles will follow up on these as part of the SCN process.</p>"""
    else:
        step_5 = """<p><strong>5. Your sign-off required</strong><br>
You will receive the formal Strategy Change Notice document from Charles for your review.
Please respond with your approval before any parameter changes are made to the engine.
No changes will be applied without your sign-off.</p>"""

    return f"""<!DOCTYPE html>
<html><body style="font-family:Arial,sans-serif;font-size:14px;color:#333;line-height:1.6;max-width:640px;">
<p>Hi Mark,</p>
<p>Thank you for your instruction regarding <em>{original_subject}</em>. This has been received and processed as follows:</p>
<p><strong>1. Logged to data lake</strong><br>
Your instruction has been recorded in the Chimera Operational Data Lake under reference <strong>{scn_ref}</strong>.
It is stored permanently for audit, traceability, and future model review.</p>
<p><strong>2. Strategy Change Notice raised</strong><br>
A Strategy Change Notice has been drafted and assigned to Charles for preparation.
This document will formalise the proposed change — <em>{summary_display}</em> — and will be
submitted to you for sign-off before anything is applied to the engine.</p>
<p><strong>3. No changes applied yet</strong><br>
The engine is running on its current parameters. Nothing will be adjusted until the SCN has been reviewed and signed off by you.</p>
<p><strong>4. Awaiting SCN sign-off</strong><br>
Charles will prepare the formal SCN document and send it to you for review. Please look out for this
and respond with your approval. You can reference <strong>{scn_ref}</strong> to track this instruction across all communications.</p>
{step_5}
<p style="margin-top:24px;color:#666;font-size:12px;">Regards,<br><em>Chimera FSU4 — Automated Process Notification</em></p>
</body></html>"""


def _build_sdr_reply_html(
    sdr_ref: str,
    original_subject: str,
    summary: str,
    self_notes: list[str],
) -> str:
    summary_display = (summary[:400] + "…") if len(summary) > 400 else summary

    self_note_block = ""
    if self_notes:
        notes_html = "".join(f"<li>{note}</li>" for note in self_notes)
        self_note_block = f"""<p><strong>Your noted commitments</strong><br>
You also noted the following during your message:</p>
<ul style="margin:8px 0;padding-left:20px;">{notes_html}</ul>
<p>These have been recorded and Charles will follow up as part of this development request.</p>"""

    return f"""<!DOCTYPE html>
<html><body style="font-family:Arial,sans-serif;font-size:14px;color:#333;line-height:1.6;max-width:640px;">
<p>Hi Mark,</p>
<p>Thank you for your strategy development request regarding <em>{original_subject}</em>. This has been received and logged as follows:</p>
<p><strong>1. Logged to data lake</strong><br>
Your request has been recorded in the Chimera Operational Data Lake under reference <strong>{sdr_ref}</strong>.
It is stored permanently for audit and traceability.</p>
<p><strong>2. Flagged for research and development</strong><br>
This has been noted as a strategy development item: <em>{summary_display}</em><br>
Charles will assess the scope of work required and follow up with next steps.</p>
<p><strong>3. No live changes</strong><br>
Nothing has been applied to the engine. This item is exploratory and will follow the standard
development and testing process before any live implementation.</p>
{self_note_block}
<p style="margin-top:24px;color:#666;font-size:12px;">Regards,<br><em>Chimera FSU4 — Automated Process Notification</em></p>
</body></html>"""


def _build_simple_ack_html() -> str:
    return """<!DOCTYPE html>
<html><body style="font-family:Arial,sans-serif;font-size:14px;color:#333;line-height:1.6;max-width:640px;">
<p>Hi Mark,</p>
<p>Your message has been received and logged in the Chimera system for reference.
Action will be taken where required.</p>
<p style="margin-top:24px;color:#666;font-size:12px;">Regards,<br><em>Chimera FSU4 — Automated Process Notification</em></p>
</body></html>"""
