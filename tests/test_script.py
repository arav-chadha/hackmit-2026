from datetime import date, datetime, timedelta

import pytest

from corpus.script import ScriptError, parse_script

HEADER = """
thread: Mei Tanaka
folder: meitanaka_1
speakers: Y=you, M=Mei Tanaka
hours: 18-24
rate: 2024-01-01..2024-12-31 3
"""


def test_header_is_read():
    script = parse_script(HEADER + "== filler\nM: hi\n")
    assert (script.name, script.folder, script.hours) == ("Mei Tanaka", "meitanaka_1", (18, 24))
    assert script.speakers == {"Y": "you", "M": "Mei Tanaka"}
    assert (script.rates[0].start, script.rates[0].sessions_per_week) == (date(2024, 1, 1), 3.0)


def test_scene_lines_carry_their_markers():
    script = parse_script(
        HEADER
        + "== scene 2025-03-14 21:20 | unanswered:interview\n"
        + "M*: how did it go??\n"
        + "-- 11h\n"
        + "Y: look at this {😂}\n"
        + "M: >reel the way she walked off #comedy\n"
    )
    scene = script.scenes[0]
    question, deflection, reel = scene.lines
    assert (scene.start, scene.label) == (datetime(2025, 3, 14, 21, 20), "unanswered:interview")
    assert (question.speaker, question.text, question.is_key) == ("Mei Tanaka", "how did it go??", True)
    assert (deflection.text, deflection.reaction, deflection.gap_before) == ("look at this", "😂", timedelta(hours=11))
    assert (reel.text, reel.is_reel) == ("the way she walked off #comedy", True)


def test_scene_label_is_optional():
    script = parse_script(HEADER + "== scene 2025-03-14 21:20\nM: hi\n")
    assert script.scenes[0].label is None


def test_filler_era_runs_to_the_end_of_its_last_month():
    script = parse_script(HEADER + "== filler 2024-01..2024-02\nM: hi\n== filler\nY: hey\n")
    assert script.fillers[0].era == (date(2024, 1, 1), date(2024, 2, 29))
    assert script.fillers[1].era is None


def test_comments_and_blank_lines_are_ignored():
    script = parse_script("# about mei\n" + HEADER + "== filler\n\n# note\nM: hi\n")
    assert [line.text for line in script.fillers[0].lines] == ["hi"]


@pytest.mark.parametrize(
    "body",
    ["== filler\nZ: who is this\n", "== filler\njust some words\n", "== filler\n", "== montage\nM: hi\n"],
)
def test_malformed_sections_are_rejected(body):
    with pytest.raises(ScriptError):
        parse_script(HEADER + body)


def test_incomplete_header_is_rejected():
    with pytest.raises(ScriptError):
        parse_script("thread: Mei Tanaka\n== filler\nM: hi\n")
