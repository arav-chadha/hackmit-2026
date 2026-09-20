"""Parses the thread scripts in corpus/threads/. The format is described in corpus/FORMAT.md."""

import calendar
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

line_pattern = re.compile(r"^([A-Z])(\*?): (.+?)(?:\s*\{(.+)\})?$")
gap_pattern = re.compile(r"^-- (\d+)([smhd])$")
gap_units = {"s": "seconds", "m": "minutes", "h": "hours", "d": "days"}
reel_prefix = ">reel "


class ScriptError(Exception):
    pass


@dataclass(frozen=True)
class Line:
    speaker: str
    text: str
    is_key: bool = False
    is_reel: bool = False
    reaction: str | None = None
    gap_before: timedelta | None = None


@dataclass(frozen=True)
class Scene:
    start: datetime
    label: str | None
    lines: tuple[Line, ...]


@dataclass(frozen=True)
class Filler:
    era: tuple[date, date] | None
    lines: tuple[Line, ...]


@dataclass(frozen=True)
class Rate:
    start: date
    end: date
    sessions_per_week: float


@dataclass
class Script:
    name: str
    folder: str
    speakers: dict[str, str]
    hours: tuple[int, int]
    rates: list[Rate] = field(default_factory=list)
    scenes: list[Scene] = field(default_factory=list)
    fillers: list[Filler] = field(default_factory=list)


def parse_script(text: str) -> Script:
    header, *sections = re.split(r"^== ", text, flags=re.MULTILINE)
    script = _header(header)
    for section in sections:
        heading, _, body = section.partition("\n")
        lines = _lines(body, script.speakers)
        kind, _, rest = heading.strip().partition(" ")
        if kind == "scene":
            script.scenes.append(_scene(rest, lines))
        elif kind == "filler":
            script.fillers.append(Filler(_era(rest.strip()), lines))
        else:
            raise ScriptError(f"unknown section: == {heading}")
    return script


def _header(text: str) -> Script:
    fields: dict[str, list[str]] = {}
    for raw in _meaningful(text):
        key, _, value = raw.partition(":")
        fields.setdefault(key.strip(), []).append(value.strip())
    missing = {"thread", "folder", "speakers", "hours"} - fields.keys()
    if missing:
        raise ScriptError(f"header is missing {sorted(missing)}")
    speakers = dict(pair.strip().split("=") for pair in fields["speakers"][0].split(","))
    first_hour, last_hour = (int(h) for h in fields["hours"][0].split("-"))
    rates = [_rate(value) for value in fields.get("rate", [])]
    return Script(fields["thread"][0], fields["folder"][0], speakers, (first_hour, last_hour), rates)


def _rate(value: str) -> Rate:
    span, sessions_per_week = value.split()
    start, end = (date.fromisoformat(day) for day in span.split(".."))
    return Rate(start, end, float(sessions_per_week))


def _scene(heading: str, lines: tuple[Line, ...]) -> Scene:
    stamp, _, label = heading.partition("|")
    return Scene(datetime.strptime(stamp.strip(), "%Y-%m-%d %H:%M"), label.strip() or None, lines)


def _era(value: str) -> tuple[date, date] | None:
    if not value:
        return None
    first, last = (datetime.strptime(month, "%Y-%m").date() for month in value.split(".."))
    return first, last.replace(day=calendar.monthrange(last.year, last.month)[1])


def _lines(body: str, speakers: dict[str, str]) -> tuple[Line, ...]:
    lines: list[Line] = []
    gap: timedelta | None = None
    for raw in _meaningful(body):
        gap_match = gap_pattern.match(raw)
        if gap_match:
            gap = timedelta(**{gap_units[gap_match[2]]: int(gap_match[1])})
            continue
        lines.append(_line(raw, speakers, gap))
        gap = None
    if not lines:
        raise ScriptError("a section has no dialogue")
    return tuple(lines)


def _line(raw: str, speakers: dict[str, str], gap: timedelta | None) -> Line:
    match = line_pattern.match(raw)
    if not match:
        raise ScriptError(f"cannot read line: {raw!r}")
    code, star, text, reaction = match.groups()
    if code not in speakers:
        raise ScriptError(f"unknown speaker {code!r} in line: {raw!r}")
    is_reel = text.startswith(reel_prefix)
    return Line(speakers[code], text.removeprefix(reel_prefix), bool(star), is_reel, reaction, gap)


def _meaningful(text: str) -> list[str]:
    stripped = (raw.strip() for raw in text.splitlines())
    return [raw for raw in stripped if raw and not raw.startswith("#")]
