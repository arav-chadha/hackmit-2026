"""Builds data/corpus (an Instagram-shaped inbox plus answers.json) from corpus/threads/.

Run with: python -m corpus.build
"""

import html
import json
import random
import shutil
import zlib
from collections import deque
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path

from corpus.script import Filler, Line, Script, parse_script

root = Path(__file__).parent.parent
threads_dir = Path(__file__).parent / "threads"
output_dir = root / "data" / "corpus"

quiet_before_scene = timedelta(hours=3)
quiet_after_session = timedelta(minutes=30)

page_template = (
    '<!DOCTYPE html><html><head><meta charset="utf-8"><title>Instagram</title>\n'
    "<style>._a6-g{{background:#fff}}._a6-h{{font-weight:700}}._a6-o{{color:#8d949e}}._a6-q{{color:gray}}</style>\n"
    '</head><body class="_5vb_ _2yq _a7o5"><div class="_li"><div class="_a705">\n'
    '<header class="_as-_ _a70a"><div class="_a70d"><h1>{name}</h1></div></header>\n'
    '<main class="_a706" role="main">{blocks}</main>\n'
    "</div></div></body></html>\n"
)
block_template = (
    '<div class="pam _3-95 _2ph- _a6-g uiBoxWhite noborder">'
    '<h2 class="_3-95 _2pim _a6-h _a6-i">{sender}</h2>'
    '<div class="_3-95 _a6-p"><div><div></div><div>{text}</div>{attachment}<div></div>{reactions}</div></div>'
    '<div class="_3-94 _a6-o">{stamp}</div></div>'
)
reel_template = '<div><div><div><a target="_blank" href="{url}">{url}</a></div></div></div>'
reaction_template = '<ul class="_a6-q"><li><span>{emoji}{reactor}</span></li></ul>'


@dataclass(frozen=True)
class Post:
    timestamp: datetime
    line: Line
    label: str | None


def timeline(script: Script, rng: random.Random) -> list[Post]:
    posts: list[Post] = []
    busy: list[tuple[datetime, datetime]] = []
    for scene in script.scenes:
        played = _play(scene.lines, scene.start, scene.label, rng)
        posts.extend(played)
        busy.append((scene.start - quiet_before_scene, played[-1].timestamp + quiet_after_session))
    recent: deque[Filler] = deque(maxlen=max(1, len(script.fillers) // 2))
    for start in _session_starts(script, rng):
        if any(low <= start <= high for low, high in busy):
            continue
        session = _filler_session(script.fillers, recent, start, rng)
        posts.extend(session)
        busy.append((start - quiet_after_session, session[-1].timestamp + quiet_after_session))
    return sorted(posts, key=lambda post: post.timestamp)


def render(script: Script, posts: list[Post]) -> str:
    blocks = "".join(_block(script, post) for post in reversed(posts))
    return page_template.format(name=html.escape(script.name), blocks=blocks)


def answers(threads: Iterable[tuple[Script, list[Post]]]) -> list[dict]:
    grouped: dict[str, list[dict]] = {}
    for script, posts in threads:
        for post in posts:
            if post.label and post.line.is_key:
                grouped.setdefault(post.label, []).append(_key(script, post))
    return [{"label": label, "kind": label.partition(":")[0], "keys": keys} for label, keys in grouped.items()]


def main() -> None:
    shutil.rmtree(output_dir / "inbox", ignore_errors=True)
    threads = []
    for path in sorted(threads_dir.glob("*.txt")):
        script = parse_script(path.read_text(encoding="utf-8"))
        posts = timeline(script, random.Random(script.folder))
        folder = output_dir / "inbox" / script.folder
        folder.mkdir(parents=True)
        (folder / "message_1.html").write_text(render(script, posts), encoding="utf-8")
        threads.append((script, posts))
        print(f"{script.name:16} {len(posts):5} messages  {posts[0].timestamp:%Y-%m-%d} → {posts[-1].timestamp:%Y-%m-%d}")
    planted = answers(threads)
    (output_dir / "answers.json").write_text(json.dumps(planted, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"{len(planted)} planted moments → {output_dir / 'answers.json'}")


def _play(lines: tuple[Line, ...], start: datetime, label: str | None, rng: random.Random) -> list[Post]:
    posts: list[Post] = []
    now = start
    for line in lines:
        if posts:
            now += line.gap_before or _pause(rng, is_same_speaker=posts[-1].line.speaker == line.speaker)
        posts.append(Post(now, line, label))
    return posts


def _pause(rng: random.Random, is_same_speaker: bool) -> timedelta:
    if is_same_speaker:
        return timedelta(seconds=rng.randint(3, 25))
    if rng.random() < 0.15:
        return timedelta(seconds=rng.randint(120, 360))
    return timedelta(seconds=rng.randint(5, 70))


def _session_starts(script: Script, rng: random.Random) -> Iterator[datetime]:
    days = [(rate, rate.start + timedelta(days=n)) for rate in script.rates for n in range((rate.end - rate.start).days + 1)]
    for rate, day in days:
        per_day = rate.sessions_per_week / 7
        count = int(per_day) + (rng.random() < per_day % 1)
        yield from sorted(_time_on(day, script.hours, rng) for _ in range(count))


def _time_on(day: date, hours: tuple[int, int], rng: random.Random) -> datetime:
    first_hour, last_hour = hours
    span_hours = (last_hour - first_hour) % 24 or 24
    return datetime.combine(day, time(first_hour)) + timedelta(minutes=rng.randrange(span_hours * 60))


def _filler_session(fillers: list[Filler], recent: deque[Filler], start: datetime, rng: random.Random) -> list[Post]:
    posts: list[Post] = []
    now = start
    for _ in range(rng.choice((1, 1, 2, 2, 3))):
        filler = _draw(fillers, recent, now.date(), rng)
        posts.extend(_play(filler.lines, now, None, rng))
        now = posts[-1].timestamp + timedelta(minutes=rng.randint(1, 8))
    return posts


def _draw(fillers: list[Filler], recent: deque[Filler], day: date, rng: random.Random) -> Filler:
    in_era = [f for f in fillers if f.era is None or f.era[0] <= day <= f.era[1]]
    if not in_era:
        raise ValueError(f"no filler covers {day}; add an undated filler")
    filler = rng.choice([f for f in in_era if f not in recent] or in_era)
    recent.append(filler)
    return filler


def _block(script: Script, post: Post) -> str:
    line = post.line
    text = html.escape(line.text)
    attachment = "<div></div>"
    if line.is_reel:
        text = f"{html.escape(line.speaker)} sent an attachment.{text}"
        attachment = reel_template.format(url=f"https://www.instagram.com/reel/{zlib.crc32(line.text.encode()):010d}/")
    reactions = ""
    if line.reaction:
        reactor = next(name for name in script.speakers.values() if name != line.speaker)
        reactions = reaction_template.format(emoji=line.reaction, reactor=html.escape(reactor))
    return block_template.format(
        sender=html.escape(line.speaker), text=text, attachment=attachment, reactions=reactions, stamp=_stamp(post.timestamp)
    )


def _stamp(moment: datetime) -> str:
    hour = moment.hour % 12 or 12
    return f"{moment:%b} {moment.day}, {moment.year} {hour}:{moment:%M} {'pm' if moment.hour >= 12 else 'am'}"


def _key(script: Script, post: Post) -> dict:
    return {
        "thread": script.name,
        "sender": post.line.speaker,
        "timestamp": post.timestamp.replace(second=0).isoformat() + "Z",
        "text": post.line.text,
    }


if __name__ == "__main__":
    main()
