from __future__ import annotations

import json
import logging
from typing import Optional

import anthropic

from app.core.config import CLAUDE_MODEL, CLAUDE_MAX_TOKENS, CHIMERA_DOMAIN_HINTS
from app.core.secrets import get_anthropic_api_key
from app.models.intelligence_record import (
    Entities,
    Intent,
    Urgency,
    Sentiment,
    IntelligenceRecord,
    RecordStatus,
)

logger = logging.getLogger(__name__)

_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=get_anthropic_api_key())
    return _client


TAGGING_PROMPT_TEMPLATE = """You are an AI intelligence analyst for the Chimera platform — a professional horse racing analytics and trading operation run by Cape Berkshire Ltd.

Your task is to analyse an inbound email and produce a structured intelligence record. Return ONLY valid JSON matching the schema below — no preamble, no explanation.

## Chimera Domain Context
Chimera operates in horse racing and sports trading. Relevant signals include:
{domain_hints}

## Email to Analyse

**From:** {from_name} <{from_address}>
**Subject:** {subject}
**Received:** {received_at}
**Labels:** {gmail_labels}

**Body:**
{body}

{attachment_context}

## Required JSON Output Schema

{{
  "title": "<Descriptive title max 80 chars>",
  "summary": "<2-3 sentence plain-English summary>",
  "topics": ["<topic tag>", ...],
  "entities": {{
    "people": ["<name>", ...],
    "organisations": ["<org>", ...],
    "race_venues": ["<venue>", ...],
    "horse_names": ["<horse>", ...],
    "monetary_values": ["<value>", ...]
  }},
  "intent": "<informational|action_required|data_payload|alert|report>",
  "urgency": "<low|medium|high|critical>",
  "relevancy_score": <0.0 to 1.0>,
  "relevancy_reasoning": "<explanation of score>",
  "chimera_domain_tags": ["<tag>", ...],
  "action_items": ["<item>", ...],
  "contains_pii": <true|false>,
  "sentiment": "<neutral|positive|negative>"
}}

Rules:
- title: max 80 characters, descriptive and specific
- summary: exactly 2-3 sentences
- topics: specific and meaningful (e.g. "lay betting", "form guide", "stake management", "market alert")
- chimera_domain_tags: use Chimera-specific tags from: signal-intelligence, spread-control, racing-data, betfair-signal, strategy-update, operational, market-data, risk-management, reporting, alert
- relevancy_score: 1.0 = directly relevant to Chimera racing/trading operations; 0.0 = completely irrelevant (spam, personal)
- action_items: only include if intent is action_required, otherwise empty array
- contains_pii: true if email contains names, addresses, phone numbers, or financial account details of private individuals
- Return ONLY the JSON object. No markdown fences."""


def tag_email(
    record: IntelligenceRecord,
    body_text: str,
    attachment_texts: Optional[list[dict]] = None,
    extra_domain_hints: Optional[list[str]] = None,
) -> IntelligenceRecord:
    """
    Call Claude to generate intelligence metadata for an email.
    Modifies and returns the record with AI fields populated.
    Raises on API error — caller handles fallback.
    """
    client = _get_client()

    all_hints = CHIMERA_DOMAIN_HINTS + (extra_domain_hints or [])
    hints_str = "\n".join(f"- {h}" for h in all_hints)

    attachment_context = ""
    if attachment_texts:
        parts = []
        for att in attachment_texts:
            parts.append(
                f"**Attachment: {att['filename']}**\n{att['text'][:2000]}"
                + (" [truncated]" if len(att["text"]) > 2000 else "")
            )
        attachment_context = "\n## Attachment Contents\n\n" + "\n\n".join(parts)

    # Truncate body to avoid token limits — keep 6000 chars
    body_truncated = body_text[:6000] + (" [truncated]" if len(body_text) > 6000 else "")

    prompt = TAGGING_PROMPT_TEMPLATE.format(
        domain_hints=hints_str,
        from_name=record.from_name,
        from_address=record.from_address,
        subject=record.subject,
        received_at=record.received_at.isoformat(),
        gmail_labels=", ".join(record.gmail_labels) if record.gmail_labels else "INBOX",
        body=body_truncated,
        attachment_context=attachment_context,
    )

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=CLAUDE_MAX_TOKENS,
        messages=[{"role": "user", "content": prompt}],
    )

    raw_content = response.content[0].text.strip()

    # Strip markdown code fences if Claude added them despite instructions
    if raw_content.startswith("```"):
        raw_content = raw_content.split("```")[1]
        if raw_content.startswith("json"):
            raw_content = raw_content[4:]
        raw_content = raw_content.strip()

    data = json.loads(raw_content)

    record.title = str(data.get("title", record.subject))[:80]
    record.summary = data.get("summary", "")
    record.topics = data.get("topics", [])

    entities_data = data.get("entities", {})
    record.entities = Entities(
        people=entities_data.get("people", []),
        organisations=entities_data.get("organisations", []),
        race_venues=entities_data.get("race_venues", []),
        horse_names=entities_data.get("horse_names", []),
        monetary_values=entities_data.get("monetary_values", []),
    )

    raw_intent = data.get("intent", "informational")
    record.intent = Intent(raw_intent) if raw_intent in Intent._value2member_map_ else Intent.informational

    raw_urgency = data.get("urgency", "low")
    record.urgency = Urgency(raw_urgency) if raw_urgency in Urgency._value2member_map_ else Urgency.low

    score = data.get("relevancy_score", 0.5)
    record.relevancy_score = max(0.0, min(1.0, float(score)))
    record.relevancy_reasoning = data.get("relevancy_reasoning", "")
    record.chimera_domain_tags = data.get("chimera_domain_tags", [])
    record.action_items = data.get("action_items", [])
    record.contains_pii = bool(data.get("contains_pii", False))

    raw_sentiment = data.get("sentiment", "neutral")
    record.sentiment = (
        Sentiment(raw_sentiment) if raw_sentiment in Sentiment._value2member_map_ else Sentiment.neutral
    )

    record.ai_model_used = CLAUDE_MODEL
    record.status = RecordStatus.complete

    return record


def fallback_tag_email(record: IntelligenceRecord) -> IntelligenceRecord:
    """
    Fallback tagging when AI fails — produces minimal valid record from headers only.
    """
    record.title = record.subject[:80]
    record.summary = (
        f"Email from {record.from_address} with subject '{record.subject}'. "
        f"AI tagging failed — manual review required."
    )
    record.topics = []
    record.entities = Entities()
    record.intent = Intent.informational
    record.urgency = Urgency.low
    record.relevancy_score = 0.5
    record.relevancy_reasoning = "AI tagging failed — default score assigned"
    record.chimera_domain_tags = []
    record.action_items = []
    record.contains_pii = False
    record.sentiment = Sentiment.neutral
    record.ai_model_used = "fallback"
    record.status = RecordStatus.complete
    logger.warning("Fallback tagging applied to record %s", record.record_id)
    return record


def agent_query(
    query: str,
    context_records: list[dict],
    extra_hints: Optional[list[str]] = None,
) -> str:
    """
    Answer a structured query from a Chimera agent against a set of intelligence records.
    Returns a plain-English response.
    """
    client = _get_client()

    records_text = json.dumps(context_records[:20], indent=2, default=str)

    prompt = f"""You are an AI analyst for the Chimera racing intelligence platform.

You have been provided with a set of email intelligence records from the Chimera registry.
Answer the following query concisely and accurately, drawing only on the provided records.

## Query
{query}

## Intelligence Records
{records_text}

Provide a direct, structured answer. If the records do not contain sufficient information to answer the query, say so explicitly."""

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )

    return response.content[0].text.strip()
