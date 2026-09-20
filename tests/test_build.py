import random
from datetime import datetime, timedelta

from corpus.build import answers, render, threads_dir, timeline
from corpus.script import parse_script
from insights.inbox import parse_thread

SCRIPT = parse_script(
    """
thread: Mei Tanaka
folder: meitanaka_1
speakers: Y=you, M=Mei Tanaka
hours: 18-24
rate: 2025-03-01..2025-03-31 7

== scene 2025-03-14 21:20 | unanswered:interview
M: how was your week
M*: wait how did the interview go??
-- 11h
Y: did you see the fire in studio {😂}
M: >reel POV: architecture students and fire #fyp

== filler
M: what did you eat today
Y: a granola bar & spite
"""
)


def built() -> list:
    return timeline(SCRIPT, random.Random("seed"))


def test_same_seed_gives_the_same_timeline():
    assert built() == built()


def test_scene_plays_at_its_time_in_order_with_its_gap():
    scene = [post for post in built() if post.label]
    assert scene[0].timestamp == datetime(2025, 3, 14, 21, 20)
    assert [post.line.text for post in scene][:2] == ["how was your week", "wait how did the interview go??"]
    assert scene[2].timestamp - scene[1].timestamp == timedelta(hours=11)


def test_filler_keeps_clear_of_the_scene():
    posts = built()
    scene_start = datetime(2025, 3, 14, 21, 20)
    scene_end = max(post.timestamp for post in posts if post.label)
    crowding = [p for p in posts if not p.label and scene_start - timedelta(hours=3) <= p.timestamp <= scene_end]
    assert crowding == []


def test_filler_fills_the_rated_period():
    filler = [post for post in built() if not post.label]
    assert len(filler) > 40
    assert all(datetime(2025, 3, 1, 18) <= post.timestamp < datetime(2025, 4, 1, 1) for post in filler)


def test_rendered_html_reads_back_through_the_inbox_parser():
    posts = built()
    thread = parse_thread(SCRIPT.folder, [render(SCRIPT, posts)])
    spoken = [post.line.text for post in posts if not post.line.is_reel]
    assert thread.name == "Mei Tanaka"
    assert [message.text for message in thread.messages] == spoken
    assert "a granola bar & spite" in spoken


def test_every_thread_script_survives_the_round_trip_with_its_planted_lines():
    for path in sorted(threads_dir.glob("*.txt")):
        script = parse_script(path.read_text(encoding="utf-8"))
        posts = timeline(script, random.Random(script.folder))
        parsed = {message.text for message in parse_thread(script.folder, [render(script, posts)]).messages}
        planted = {post.line.text for post in posts if post.label and post.line.is_key}
        assert planted <= parsed, path.name
        assert max(post.timestamp for post in posts) < datetime(2026, 9, 19), path.name


def test_answers_group_starred_lines_by_label():
    (planted,) = answers([(SCRIPT, built())])
    assert (planted["label"], planted["kind"]) == ("unanswered:interview", "unanswered")
    assert planted["keys"] == [
        {
            "thread": "Mei Tanaka",
            "sender": "Mei Tanaka",
            "timestamp": "2025-03-14T21:20:00Z",
            "text": "wait how did the interview go??",
        }
    ]
