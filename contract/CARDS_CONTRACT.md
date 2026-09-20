# Cards contract

The backend reads an Instagram DM export and produces one JSON file of **cards**.
Each card is one insight about one friendship. The frontend only displays cards;
it never computes anything or builds sentences.

`cards.example.json` (next to this file) is a complete, valid example containing
every insight kind. Build against it. Real output will have the same shape.

`cards.sample.json` is real output from the pipeline run on the synthetic dataset. It has
only the insight kinds built so far, and is refreshed as more are added. Same shape, real content.

## The one rule that matters

Every card has the **same fields**, whatever its kind. Write **one generic card
renderer**: title, body, stats if any, evidence if any, action button if any.
Use `kind` only for styling (icon, color, section heading), not for layout
logic. A new insight kind added later should render without frontend changes.

Every key is **always present**. "Empty" is `null` or `[]`, never a missing key.

## Envelope

| Field | Type | Meaning |
|---|---|---|
| `generatedAt` | string, ISO 8601 UTC | When the cards were computed |
| `owner` | string | Display name of the person whose export this is |
| `cards` | Card[] | In no particular order. Sort them yourself (see `score`, `rank`) |

## Card

| Field | Type | Meaning |
|---|---|---|
| `id` | string | Stable across runs: the same insight always gets the same id. Safe to use as a key for "dismissed" / "seen" state in localStorage |
| `kind` | string | Which insight this is. See the table below |
| `score` | number, 0 to 1 | How strong the insight is. Sort the feed by this, descending. Highest score = featured card |
| `rank` | number or null | Only set for ranked kinds (`your_people`): 1 is closest. `null` everywhere else |
| `friend` | `{ name, threadId }` | Who the card is about. `threadId` groups all cards about the same friend |
| `title` | string | Display-ready headline |
| `body` | string | Display-ready one or two sentences |
| `stats` | `{ label, value }[]` | Pre-formatted label/value pairs, both strings. Render as a list or grid. You do not need to know which labels exist. Often `[]` |
| `evidence` | Evidence[] | The real messages that prove the claim, oldest first. Often the most compelling part of the card. May be `[]` |
| `action` | `{ label, draft }` or null | A button. `label` is the button text. `draft` is a suggested message the user can edit, or `null` when the button has no message (e.g. Share) |

## Evidence (one message)

| Field | Type | Meaning |
|---|---|---|
| `id` | string | Message id |
| `sender` | string | Display name |
| `isFromOwner` | boolean | `true` = the user sent it. Use for left/right bubble alignment |
| `isKey` | boolean | `true` = this is the message the insight is about; highlight it. `false` = surrounding context |
| `threadName` | string | Which chat the message is from. Usually the card's friend, but **not always** (see `both_wanted`) |
| `timestamp` | string, ISO 8601 UTC | `new Date(timestamp)` works directly |
| `text` | string | The message. Contains emoji |

## Insight kinds

| `kind` | What it shows | stats | evidence | action label |
|---|---|---|---|---|
| `your_people` | Closest-friends ranking. **One card per friend**; group by kind and order by `rank` | yes | none | none |
| `memory_lane` | A funny or nostalgic moment buried in old chats | date | one continuous run of messages, highlights marked `isKey` | "Send this memory" |
| `reconnect` | A topic or hobby the two used to share and stopped talking about | mention count, last mentioned | a few old messages, from different dates | "Reconnect" |
| `unfinished_plans` | Something they repeatedly said they'd do together and never did | times mentioned | each mention, all `isKey`, months apart | "Make It Happen" |
| `unanswered` | A question the friend asked that the user never answered, even though they kept talking | date asked | the question (`isKey`) plus what the user said instead | "Respond" |
| `both_wanted` | Something both people independently said they wanted. The user's message may come from a **different chat**, so show `threadName` on each message | none | one message from each person, both `isKey` | "Do It Together" |
| `recap` | Summary of one whole friendship | many | two or three standout messages | "Share Recap" (`draft` is `null`) |

## Things not to assume

- **Evidence is not always one conversation.** `memory_lane` is a continuous
  run; `unfinished_plans` and `reconnect` jump across months. Show a date
  separator whenever consecutive timestamps are far apart.
- **Evidence may be empty, stats may be empty, action may be null.** All three
  are empty on some cards.
- **Unknown `kind` values may appear.** Render them with the generic layout
  rather than hiding them or crashing.
- **Several cards can be about the same friend.** Group by `friend.threadId`
  if you want a per-friend view.

## Button behavior

- **Edit**: fully client-side. Put `action.draft` in a textarea.
- **Send**: there is no API for sending Instagram DMs. "Send" means copy the
  draft to the clipboard and/or open the chat on instagram.com. A Chrome
  extension could go further and paste it into the message box.
- **Regenerate**: needs a live backend endpoint, which does not exist yet. Build
  the button, leave it disabled or hidden for now.

## Not supported (yet)

- **Charts.** `stats` values are display strings, not numbers. If you want a
  chart (e.g. messages per month), tell us and we will add a numeric `series`
  field rather than you parsing strings.
- **Group chats.** Every card is about exactly one friend.

## Changes

Any change from here on will be **additive** (new optional fields, new kinds).
Existing fields will not be renamed or removed.
