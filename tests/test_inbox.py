from datetime import datetime, timezone
from pathlib import Path

import pytest

from insights.inbox import InboxError, parse_thread, read_inbox

CORPUS = Path(__file__).parent.parent / "data" / "corpus-instagram" / "inbox"


def block(sender: str, body: str, stamp: str) -> str:
    return (
        '<div class="pam _3-95 _2ph- _a6-g uiBoxWhite noborder">'
        f'<h2 class="_3-95 _2pim _a6-h _a6-i">{sender}</h2>'
        f'<div class="_3-95 _a6-p"><div><div></div><div>{body}</div><div></div><div></div></div></div>'
        f'<div class="_3-94 _a6-o">{stamp}</div></div>'
    )


def page(title: str, *blocks: str) -> str:
    return f"<html><body><h1>{title}</h1><main>{''.join(blocks)}</main></body></html>"


def test_messages_come_out_oldest_first():
    html = page(
        "Mei Tanaka",
        block("you", "second", "Sep 24, 2025 10:44 pm"),
        block("Mei Tanaka", "first", "Sep 23, 2025 8:15 pm"),
    )
    thread = parse_thread("mei_1", [html])
    assert [m.text for m in thread.messages] == ["first", "second"]


def test_timestamp_is_parsed_including_noon_and_midnight():
    html = page(
        "Mei Tanaka",
        block("you", "late", "Sep 24, 2025 10:44 pm"),
        block("you", "noon", "Sep 24, 2025 12:05 pm"),
        block("you", "midnight", "Sep 24, 2025 12:05 am"),
    )
    stamps = {m.text: m.timestamp for m in parse_thread("mei_1", [html]).messages}
    assert stamps["late"] == datetime(2025, 9, 24, 22, 44, tzinfo=timezone.utc)
    assert stamps["noon"] == datetime(2025, 9, 24, 12, 5, tzinfo=timezone.utc)
    assert stamps["midnight"] == datetime(2025, 9, 24, 0, 5, tzinfo=timezone.utc)


def test_reactions_are_not_part_of_the_text():
    body = 'Are you feeling better?</div><div></div><ul class="_a6-q"><li><span>❤Mei Tanaka</span></li></ul><div>'
    html = page("Mei Tanaka", block("you", body, "Sep 24, 2023 11:55 pm"))
    assert parse_thread("mei_1", [html]).messages[0].text == "Are you feeling better?"


def test_forwarded_reel_is_dropped():
    body = (
        "Mei Tanaka sent an attachment.POV: five minutes means forty #fyp</div>"
        '<div><a href="https://www.instagram.com/reel/abc/">https://www.instagram.com/reel/abc/</a>'
    )
    html = page("Mei Tanaka", block("Mei Tanaka", body, "May 31, 2025 10:54 pm"))
    assert parse_thread("mei_1", [html]).messages == ()


@pytest.mark.parametrize(
    "text",
    ["Liked a message", "Reacted ❤ to your message", "https://example.com/x", "This message was unsent"],
)
def test_things_nobody_typed_are_dropped(text):
    html = page("Mei Tanaka", block("Mei Tanaka", text, "May 31, 2025 10:54 pm"))
    assert parse_thread("mei_1", [html]).messages == ()


def test_html_entities_are_decoded():
    html = page("Mei Tanaka", block("you", "fish &amp; chips, it&#39;s great", "May 31, 2025 10:54 pm"))
    assert parse_thread("mei_1", [html]).messages[0].text == "fish & chips, it's great"


def test_ids_survive_a_newer_export():
    older = [block("Mei Tanaka", "hello", "Sep 1, 2025 9:00 am")]
    newer = [block("you", "hi!", "Sep 2, 2025 9:00 am")] + older
    before = parse_thread("mei_1", [page("Mei Tanaka", *older)]).messages
    after = parse_thread("mei_1", [page("Mei Tanaka", *newer)]).messages
    assert after[0].id == before[0].id


def test_identical_messages_get_distinct_ids():
    html = page(
        "Mei Tanaka",
        block("you", "lol", "Sep 1, 2025 9:00 am"),
        block("you", "lol", "Sep 1, 2025 9:00 am"),
    )
    first, second = parse_thread("mei_1", [html]).messages
    assert first.id != second.id


def test_pages_of_one_thread_are_merged():
    newest = page("Mei Tanaka", block("you", "second", "Sep 2, 2025 9:00 am"))
    oldest = page("Mei Tanaka", block("Mei Tanaka", "first", "Sep 1, 2025 9:00 am"))
    thread = parse_thread("mei_1", [newest, oldest])
    assert [m.text for m in thread.messages] == ["first", "second"]


def test_three_speakers_make_a_group():
    html = page(
        "cohort",
        block("you", "one", "Sep 1, 2025 9:00 am"),
        block("Mei Tanaka", "two", "Sep 1, 2025 9:01 am"),
        block("Rafa Ortiz", "three", "Sep 1, 2025 9:02 am"),
    )
    assert parse_thread("cohort_1", [html]).is_group


def test_corpus_reads_every_thread_except_the_deleted_account():
    threads = {t.name: t for t in read_inbox(CORPUS)}
    assert len(threads) == 7
    assert "Instagram user" not in threads
    assert set(threads["Mei Tanaka"].participants) == {"you", "Mei Tanaka"}
    assert not threads["Mei Tanaka"].is_group


def test_corpus_text_is_clean():
    messages = [m for t in read_inbox(CORPUS) for m in t.messages]
    assert messages
    assert not any("sent an attachment" in m.text for m in messages)
    assert not any("<" in m.text and ">" in m.text for m in messages)


def test_missing_inbox_is_an_error():
    with pytest.raises(InboxError):
        read_inbox(Path("/nonexistent/inbox"))
