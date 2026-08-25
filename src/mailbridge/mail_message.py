"""
Nostr Mail — формат письма kind:1301.

Content события kind:1301 = RFC 2822-совместимый текст:
    From: <адрес>
    To: <адрес>
    Subject: <тема>
    Date: <RFC 2822 date>
    Message-ID: <id@домен>
    [In-Reply-To: <id>]
    [References: <id1> <id2>]

    <тело письма>

Заголовки UTF-8 как есть (nostr-экосистема UTF-8-first; nostrmail.org рендерит
их напрямую). Message-ID генерируется уникальным — для дедупликации и threads.

Лимит: письмо должно влезать в NIP-44 plaintext (65535 байт), оставляем запас
на JSON-обёртку rumor — MAX_MAIL_SIZE = 60000.
"""

from __future__ import annotations

import datetime
import re

MAIL_KIND = 1301
MAX_MAIL_SIZE = 60000  # байт (запас под NIP-44 лимит 65535 + JSON rumor)

_HEADER_RE = re.compile(r"^([A-Za-z-]+):\s?(.*)$", re.MULTILINE)


def _rfc2822_date(ts: datetime.datetime | None = None) -> str:
    dt = ts or datetime.datetime.now(datetime.timezone.utc)
    return dt.strftime("%a, %d %b %Y %H:%M:%S %z")


def build_mail(
    from_addr: str,
    to_addr: str,
    subject: str,
    body: str,
    date: datetime.datetime | None = None,
    message_id: str | None = None,
    in_reply_to: str | None = None,
    references: str | None = None,
    extra_headers: dict[str, str] | None = None,
) -> str:
    """Собирает RFC 2822 текст письма. Кидает ValueError при превышении лимита."""
    import uuid

    mid = message_id or f"<{uuid.uuid4().hex}@cryter-mail.v2.site>"

    lines = [
        f"From: {from_addr}",
        f"To: {to_addr}",
        f"Subject: {subject}",
        f"Date: {_rfc2822_date(date)}",
        f"Message-ID: {mid}",
    ]
    if in_reply_to:
        lines.append(f"In-Reply-To: {in_reply_to}")
    if references:
        refs = references if isinstance(references, str) else " ".join(references)
        lines.append(f"References: {refs}")
    if extra_headers:
        for k, v in extra_headers.items():
            lines.append(f"{k}: {v}")

    mail = "\n".join(lines) + "\n\n" + (body or "")

    if len(mail.encode("utf-8")) > MAX_MAIL_SIZE:
        raise ValueError(
            f"письмо {len(mail.encode('utf-8'))} байт > лимита {MAX_MAIL_SIZE}"
        )
    return mail


def parse_mail(text: str) -> dict:
    """Разбирает RFC 2822 текст письма в dict. Не строгий — выживает при мусоре."""
    if "\n\n" in text:
        header_block, body = text.split("\n\n", 1)
    elif "\r\n\r\n" in text:
        header_block, body = text.split("\r\n\r\n", 1)
    else:
        header_block, body = text, ""

    headers: dict[str, str] = {}
    for match in _HEADER_RE.finditer(header_block):
        name = match.group(1).lower()
        value = match.group(2).strip()
        # продолжаем многострочные заголовки (folding) — редкий случай, ок
        headers[name] = value

    return {
        "from": headers.get("from", ""),
        "to": headers.get("to", ""),
        "subject": headers.get("subject", ""),
        "date": headers.get("date", ""),
        "message_id": headers.get("message-id", ""),
        "in_reply_to": headers.get("in-reply-to", ""),
        "references": headers.get("references", ""),
        "body": body,
        "headers": headers,
    }


def extract_addresses(text: str) -> tuple[str, str]:
    """Из RFC 2822 текста — (from_addr, to_addr) для быстрой маршрутизации."""
    parsed = parse_mail(text)
    return parsed["from"], parsed["to"]
