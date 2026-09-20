"""Reads the inbox folder of an Instagram "Download your information" HTML export."""

import hashlib
import logging
import re
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from bs4 import BeautifulSoup, Tag

logger = logging.getLogger(__name__)

deleted_account = "Instagram user"
stamp_format = "%b %d, %Y %I:%M %p"

# The export renders reactions, shares and system notices as if someone typed them.
not_speech = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\bsent an attachment\b",
        r"^liked a message$",
        r"^reacted .* to your message$",
        r"^(you )?(sent|shared) an? (photo|video|voice message|story|reel|post)",
        r"^this message (is no longer available|was unsent)",
        r"^(missed|started) (a )?(video|voice|audio) (call|chat)",
        r"^changed the (theme|group name|chat)",
        r"^(added|removed) .* (to|from) the (group|chat)",
        r"^https?://\S+$",
    )
)


class InboxError(Exception):
    pass


@dataclass(frozen=True)
class Message:
    id: str
    thread_id: str
    sender: str
    timestamp: datetime
    text: str


@dataclass(frozen=True)
class Thread:
    id: str
    name: str
    participants: tuple[str, ...]
    messages: tuple[Message, ...]

    @property
    def is_group(self) -> bool:
        return len(self.participants) > 2


def read_inbox(inbox: Path) -> list[Thread]:
    if not inbox.is_dir():
        raise InboxError(f"inbox folder not found: {inbox}")
    threads = [_read_thread(folder) for folder in sorted(inbox.iterdir()) if folder.is_dir()]
    return [t for t in threads if t.messages and t.name != deleted_account]


def parse_thread(thread_id: str, pages: Iterable[str]) -> Thread:
    name = thread_id
    rows: list[tuple[datetime, str, str]] = []
    for html in pages:
        soup = BeautifulSoup(html, "html.parser")
        if soup.h1:
            name = soup.h1.get_text(strip=True)
        rows.extend(_rows(soup, thread_id))
    rows.sort(key=lambda row: row[0])
    messages = tuple(_messages(thread_id, rows))
    participants = tuple(dict.fromkeys(m.sender for m in messages))
    return Thread(thread_id, name, participants, messages)


def _read_thread(folder: Path) -> Thread:
    pages = (p.read_text(encoding="utf-8") for p in sorted(folder.glob("message_*.html")))
    return parse_thread(folder.name, pages)


def _rows(soup: BeautifulSoup, thread_id: str) -> Iterable[tuple[datetime, str, str]]:
    for block in soup.select("div.pam"):
        sender, body, stamp = block.find("h2"), block.select_one("div._a6-p"), block.select_one("div._a6-o")
        if not (sender and body and stamp):
            continue
        timestamp = _timestamp(stamp.get_text(strip=True))
        if timestamp is None:
            logger.warning("skipped a message in %s: unreadable timestamp %r", thread_id, stamp.get_text())
            continue
        text = _text(body)
        if _is_speech(text):
            yield timestamp, sender.get_text(strip=True), text


def _messages(thread_id: str, rows: list[tuple[datetime, str, str]]) -> Iterable[Message]:
    seen: Counter[tuple[datetime, str, str]] = Counter()
    for row in rows:
        timestamp, sender, text = row
        # Identical messages in the same minute are told apart by their order of occurrence,
        # so ids depend only on content and stay the same when a newer export adds messages.
        key = f"{thread_id}|{sender}|{timestamp.isoformat()}|{text}|{seen[row]}"
        seen[row] += 1
        yield Message(hashlib.sha1(key.encode()).hexdigest()[:16], thread_id, sender, timestamp, text)


def _timestamp(raw: str) -> datetime | None:
    try:
        # The export prints local wall-clock time with no zone; it is read as UTC.
        return datetime.strptime(raw, stamp_format).replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _text(body: Tag) -> str:
    for nobody_typed in body.select("ul._a6-q, a"):
        nobody_typed.decompose()
    for line_break in body.find_all("br"):
        line_break.replace_with("\n")
    return re.sub(r"[ \t]+", " ", body.get_text(" ")).strip()


def _is_speech(text: str) -> bool:
    return len(text) >= 2 and not any(pattern.search(text) for pattern in not_speech)
