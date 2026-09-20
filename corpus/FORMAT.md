# Thread script format

Each file in `corpus/threads/` is one Instagram conversation. `python -m corpus.build`
turns them into `data/corpus/inbox/` (Instagram's HTML export shape) and
`data/corpus/answers.json` (every planted moment, used to score the insights).

`corpus/threads/mei.txt` is the reference example. Match its tone and density.

## Header

```
thread: Mei Tanaka                         display name of the chat
folder: meitanaka_17950517471278735        handle + underscore + 17 digits
speakers: Y=you, M=Mei Tanaka              Y is always the account owner, named "you"
hours: 18-24                               when filler sessions start (wraps: 22-2 is fine)
rate: 2023-12-05..2025-05-31 3             date range, filler sessions per week (repeatable)
```

## Sections

```
== scene 2025-03-14 21:20 | unanswered:interview
== filler 2024-01..2024-08
== filler
```

- **scene**: happens once, at that exact time. The label after `|` is optional.
- **filler**: a short everyday exchange the builder reuses many times at random times.
  The optional month range limits when it can appear. Undated fillers can appear any time,
  and every thread needs several so no date is left uncovered.

## Lines

```
M: plain message
Y*: a key message (goes into answers.json; only meaningful inside a labeled scene)
M: that is so funny {😂}          the OTHER person reacted with 😂
M: >reel the way she just walked off 😭 #comedy      a forwarded reel with this caption
-- 11h                             silence before the next line: s, m, h or d
# comment
```

Without a `--` line the builder spaces messages 5 to 70 seconds apart, like a live chat.

## Labels

`kind:tag`. Scenes sharing a label are one planted moment, even across files.

| kind | what to plant |
|---|---|
| `unanswered` | The friend asks something that matters. `you` keeps chatting (in the scene, after a `--` gap) and never answers. Star the question. |
| `unfinished_plans` | Same plan raised in 3+ scenes months apart, worded differently each time, never done. Star each mention. |
| `both_wanted` | Each person independently says they want the same thing, months apart, worded differently, never noticing. Star both. May span two files. |
| `reconnect` | A shared obsession that fills one era (scenes plus era-dated fillers) then vanishes. Star 3 or so vivid messages. |
| `memory_lane` | One long, fast, genuinely funny or warm scene (15+ lines). Star the 2 or 3 best lines. |
| `control` | A decoy that must NOT be flagged: a question answered a day later, a plan that then happens, a wish only one person has. Star the decoy line. |

## Rules for fillers

Fillers repeat, so they must be safe to see many times and must never look like a planted moment.

- Self-contained: any question is answered inside the same exchange.
- No plans ("we should", "let's", "wanna go") and no wishes ("i want to try").
- 3 to 8 lines. Vary who speaks first according to the thread's dynamic.
- Specific beats generic: a named class, a named show, a particular bad dining hall meal.

## Voice

`you`: a CS junior in Boston, does hackathons, some design work. Texts in lowercase, short
bursts, often two or three messages in a row. Uses lol, fr, ngl, omg, 😭 and 💀. Rarely uses
periods. Never sounds like an essay. Today is 2026-09-19; nothing may be dated later.

Each friend should have their own rhythm, punctuation, pet phrases and topics. People
double-text, trail off, change subject, and send reels. Nobody narrates their feelings in
full sentences.
