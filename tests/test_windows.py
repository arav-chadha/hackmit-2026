from datetime import datetime, timedelta, timezone

from insights.inbox import Message, Thread
from insights.windows import windowed

START = datetime(2025, 3, 14, 21, 0, tzinfo=timezone.utc)


def thread(*offsets_in_minutes: float) -> Thread:
    messages = tuple(
        Message(f"m{n}", "mei_1", "you" if n % 2 else "Mei Tanaka", START + timedelta(minutes=offset), f"text {n}")
        for n, offset in enumerate(offsets_in_minutes)
    )
    return Thread("mei_1", "Mei Tanaka", ("Mei Tanaka", "you"), messages)


def test_a_long_silence_starts_a_new_window():
    windows = windowed(thread(0, 1, 2, 600, 601))
    assert [w.message_ids for w in windows] == [("m0", "m1", "m2"), ("m3", "m4")]


def test_a_pause_shorter_than_the_gap_stays_in_the_window():
    windows = windowed(thread(0, 1, 170, 171))
    assert len(windows) == 1


def test_a_marathon_conversation_is_capped():
    windows = windowed(thread(*range(95)), max_messages=40)
    assert [len(w.message_ids) for w in windows] == [40, 40, 15]


def test_text_is_the_conversation_with_speakers():
    (window,) = windowed(thread(0, 1))
    assert window.text == "Mei Tanaka: text 0\nyou: text 1"


def test_window_spans_its_first_and_last_message():
    (window,) = windowed(thread(0, 5, 9))
    assert (window.start, window.end) == (START, START + timedelta(minutes=9))


def test_window_knows_who_started_it():
    first, second = windowed(thread(0, 1, 600))
    assert (first.first_sender, second.first_sender) == ("Mei Tanaka", "Mei Tanaka")
    (shifted,) = windowed(Thread("mei_1", "Mei Tanaka", (), thread(0, 1).messages[1:]))
    assert shifted.first_sender == "you"


def test_every_message_lands_in_exactly_one_window():
    source = thread(0, 1, 2, 600, 601, 2000, 2001, 2002, 9000)
    collected = [message_id for w in windowed(source, max_messages=2) for message_id in w.message_ids]
    assert collected == [m.id for m in source.messages]


def test_window_id_survives_new_messages_at_the_end():
    before = windowed(thread(0, 1, 600, 601))
    after = windowed(thread(0, 1, 600, 601, 602))
    assert [w.id for w in after] == [w.id for w in before]


def test_empty_thread_has_no_windows():
    assert windowed(Thread("mei_1", "Mei Tanaka", (), ())) == []
