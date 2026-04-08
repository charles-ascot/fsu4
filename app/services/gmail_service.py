from __future__ import annotations

import base64
import email
import json
import logging
import re
from datetime import datetime
from email.utils import parseaddr, parsedate_to_datetime
from typing import Optional

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.core.config import (
    GCP_PROJECT,
    GMAIL_ADDRESS,
    PUBSUB_TOPIC,
    PUBSUB_SUBSCRIPTION,
    GCS_BUCKET,
)
from app.core.secrets import get_gmail_credentials, get_gmail_token

logger = logging.getLogger(__name__)

GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
]


def _build_gmail_service():
    raw_creds = get_gmail_credentials()
    raw_token = get_gmail_token()

    creds = Credentials(
        token=raw_token.get("token"),
        refresh_token=raw_token.get("refresh_token"),
        token_uri=raw_creds.get("token_uri", "https://oauth2.googleapis.com/token"),
        client_id=raw_creds.get("client_id"),
        client_secret=raw_creds.get("client_secret"),
        scopes=GMAIL_SCOPES,
    )

    if creds.expired and creds.refresh_token:
        creds.refresh(Request())

    return build("gmail", "v1", credentials=creds)


def setup_gmail_watch() -> dict:
    """
    Establish or renew Gmail push notification watch via Pub/Sub.
    Gmail watch() subscriptions expire after 7 days — must be called on startup
    and renewed periodically via Cloud Scheduler.
    """
    service = _build_gmail_service()
    topic_name = f"projects/{GCP_PROJECT}/topics/{PUBSUB_TOPIC}"

    request_body = {
        "labelIds": ["INBOX"],
        "topicName": topic_name,
    }

    result = service.users().watch(userId="me", body=request_body).execute()
    logger.info(
        "Gmail watch established: historyId=%s, expiration=%s",
        result.get("historyId"),
        result.get("expiration"),
    )
    return result


def stop_gmail_watch() -> None:
    service = _build_gmail_service()
    service.users().stop(userId="me").execute()
    logger.info("Gmail watch stopped")


def get_message(message_id: str) -> dict:
    """Fetch full Gmail message by ID."""
    service = _build_gmail_service()
    return (
        service.users()
        .messages()
        .get(userId="me", id=message_id, format="full")
        .execute()
    )


def list_history(start_history_id: str) -> list[dict]:
    """Fetch Gmail history records since a given historyId."""
    service = _build_gmail_service()
    messages_added = []

    try:
        result = (
            service.users()
            .history()
            .list(
                userId="me",
                startHistoryId=start_history_id,
                historyTypes=["messageAdded"],
                labelId="INBOX",
            )
            .execute()
        )

        for history_entry in result.get("history", []):
            for msg in history_entry.get("messagesAdded", []):
                messages_added.append(msg["message"])

        # Handle pagination
        while "nextPageToken" in result:
            result = (
                service.users()
                .history()
                .list(
                    userId="me",
                    startHistoryId=start_history_id,
                    historyTypes=["messageAdded"],
                    labelId="INBOX",
                    pageToken=result["nextPageToken"],
                )
                .execute()
            )
            for history_entry in result.get("history", []):
                for msg in history_entry.get("messagesAdded", []):
                    messages_added.append(msg["message"])

    except HttpError as e:
        if e.resp.status == 404:
            logger.warning("History ID %s not found — watch may have expired", start_history_id)
        else:
            raise

    return messages_added


# Matches Gmail ("--- Forwarded message ---"), Outlook ("--- Original Message ---"),
# and Apple Mail ("Begin forwarded message:") dividers
_FORWARD_DIVIDER_RE = re.compile(
    r'(?:[-]{3,}\s*(?:Forwarded message|Original Message)\s*[-]{3,}'
    r'|Begin forwarded message:)',
    re.IGNORECASE,
)

# Matches "From: Display Name <email@example.com>" or "From: email@example.com"
_FROM_LINE_RE = re.compile(
    r'^From:\s*(?P<name>[^<\n]*?)\s*'
    r'(?:<(?P<email1>[\w.+\-]+@[\w.+\-]+\.\w+)>'
    r'|(?P<email2>[\w.+\-]+@[\w.+\-]+\.\w+))',
    re.MULTILINE | re.IGNORECASE,
)


def _extract_forwarded_sender(body_text: str) -> tuple[str, str]:
    """
    Detect original sender inside a forwarded/forward-auto email body.
    Looks for a forwarded-message divider, then reads the From: line immediately after.
    Returns (display_name, email_address) or ("", "") if not found.
    """
    if not body_text:
        return "", ""
    match = _FORWARD_DIVIDER_RE.search(body_text)
    if not match:
        return "", ""
    # Only scan the 600 chars after the divider to avoid false matches in quoted history
    snippet = body_text[match.start(): match.start() + 600]
    from_match = _FROM_LINE_RE.search(snippet)
    if not from_match:
        return "", ""
    email_addr = (from_match.group("email1") or from_match.group("email2") or "").lower().strip()
    name = (from_match.group("name") or "").strip()
    return name, email_addr


class ParsedEmail:
    def __init__(self):
        self.message_id: str = ""
        self.thread_id: str = ""
        self.from_address: str = ""
        self.from_name: str = ""
        self.subject: str = ""
        self.received_at: datetime = datetime.utcnow()
        self.forwarded_from: Optional[str] = None
        self.original_from_address: Optional[str] = None  # original sender in a forwarded email
        self.original_from_name: Optional[str] = None
        self.gmail_labels: list[str] = []
        self.body_text: str = ""
        self.body_html: str = ""
        self.attachments: list[dict] = []  # {filename, content_type, data (bytes), size}
        self.raw_headers: dict = {}


def parse_gmail_message(raw_message: dict) -> ParsedEmail:
    """Parse a raw Gmail API message object into a structured ParsedEmail."""
    parsed = ParsedEmail()
    parsed.message_id = raw_message["id"]
    parsed.thread_id = raw_message["threadId"]
    parsed.gmail_labels = raw_message.get("labelIds", [])

    headers = {
        h["name"].lower(): h["value"]
        for h in raw_message.get("payload", {}).get("headers", [])
    }
    parsed.raw_headers = headers

    raw_from = headers.get("from", "")
    parsed.from_name, parsed.from_address = parseaddr(raw_from)
    parsed.from_address = parsed.from_address.lower()

    parsed.subject = headers.get("subject", "(no subject)")

    date_str = headers.get("date", "")
    try:
        parsed.received_at = parsedate_to_datetime(date_str).replace(tzinfo=None)
    except Exception:
        parsed.received_at = datetime.utcfromtimestamp(
            int(raw_message.get("internalDate", 0)) / 1000
        )

    # Detect forwarded_from
    x_forwarded = headers.get("x-forwarded-to", "") or headers.get("x-original-to", "")
    if x_forwarded:
        parsed.forwarded_from = x_forwarded.lower()

    _extract_parts(raw_message.get("payload", {}), parsed)
    _fetch_attachment_data(raw_message["id"], parsed)

    # Detect original sender when the email was forwarded to this inbox
    orig_name, orig_email = _extract_forwarded_sender(parsed.body_text)
    if orig_email:
        parsed.original_from_address = orig_email
        parsed.original_from_name = orig_name
        logger.debug(
            "Detected forwarded sender: %s <%s> (envelope from: %s)",
            orig_name, orig_email, parsed.from_address,
        )

    return parsed


def send_reply(
    to_address: str,
    subject: str,
    body_html: str,
    thread_id: str,
    in_reply_to: str = "",
) -> str:
    """
    Send an email reply via the Gmail API.
    Returns the sent Gmail message ID.
    """
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    msg = MIMEMultipart("alternative")
    msg["To"] = to_address
    msg["From"] = GMAIL_ADDRESS
    msg["Subject"] = subject
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
        msg["References"] = in_reply_to

    msg.attach(MIMEText(body_html, "html", "utf-8"))

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")

    service = _build_gmail_service()
    result = (
        service.users()
        .messages()
        .send(userId="me", body={"raw": raw, "threadId": thread_id})
        .execute()
    )
    logger.info("Reply sent to %s (thread=%s) message_id=%s", to_address, thread_id, result.get("id"))
    return result.get("id", "")


def _extract_parts(payload: dict, parsed: ParsedEmail) -> None:
    """Recursively extract body text, HTML, and attachments from MIME parts."""
    mime_type = payload.get("mimeType", "")
    body = payload.get("body", {})
    parts = payload.get("parts", [])

    # message/rfc822 = a forwarded email attached as a full message.
    # Recurse into its nested payload so we extract the original body text.
    if mime_type == "message/rfc822":
        if parts:
            for part in parts:
                _extract_parts(part, parsed)
        return

    if parts:
        for part in parts:
            _extract_parts(part, parsed)
        return

    filename = payload.get("filename", "")
    data = body.get("data", "")

    if not data:
        # Large attachments: Gmail omits inline data and uses attachmentId instead
        attachment_id = body.get("attachmentId", "")
        if filename and attachment_id:
            parsed.attachments.append(
                {
                    "filename": filename,
                    "content_type": mime_type,
                    "data": None,           # fetched later via _fetch_attachment_data
                    "_attachment_id": attachment_id,
                    "size": body.get("size", 0),
                }
            )
        return

    decoded = base64.urlsafe_b64decode(data + "==")

    if filename:
        parsed.attachments.append(
            {
                "filename": filename,
                "content_type": mime_type,
                "data": decoded,
                "size": len(decoded),
            }
        )
        return

    # Accumulate body text — multiple text/plain parts can appear in forwarded emails
    # (outer forwarding note + inner original content). Concatenate all of them.
    if mime_type == "text/plain":
        chunk = decoded.decode("utf-8", errors="replace")
        parsed.body_text = (parsed.body_text + "\n\n" + chunk).strip() if parsed.body_text else chunk
    elif mime_type == "text/html":
        chunk = decoded.decode("utf-8", errors="replace")
        parsed.body_html = (parsed.body_html + "\n" + chunk).strip() if parsed.body_html else chunk


def _fetch_attachment_data(message_id: str, parsed: ParsedEmail) -> None:
    """
    Fetch bytes for any attachment stubs that have an _attachment_id field.
    Gmail returns large attachment data via a separate attachments.get() call.
    """
    stubs = [a for a in parsed.attachments if a.get("_attachment_id")]
    if not stubs:
        return

    service = _build_gmail_service()
    for att in stubs:
        att_id = att.pop("_attachment_id")
        try:
            result = (
                service.users()
                .messages()
                .attachments()
                .get(userId="me", messageId=message_id, id=att_id)
                .execute()
            )
            raw = result.get("data", "")
            att["data"] = base64.urlsafe_b64decode(raw + "==")
            att["size"] = len(att["data"])
            logger.info(
                "Fetched attachment %s (%d bytes) for message %s",
                att["filename"], att["size"], message_id,
            )
        except Exception as exc:
            logger.warning(
                "Failed to fetch attachment %s for message %s: %s",
                att["filename"], message_id, exc,
            )
            att["data"] = b""
