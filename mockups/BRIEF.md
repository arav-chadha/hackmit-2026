# Mockup brief: "your DMs, wrapped"

A Spotify-Wrapped-style story experience for insights about your Instagram friendships. Seven pages, one
per insight kind; the person taps or presses arrow keys to move through them. Each designer builds ONE
visual direction as ONE self-contained HTML file. These are design mockups for a hackathon team to choose
between, so visual quality, personality and polish matter more than anything else.

## Hard requirements

1. **One file**: `mockups/<given-name>.html`. Inline CSS and a small inline script. No frameworks, no build
   step, no external JS. Google Fonts via `<link>` is allowed, with a sensible system fallback stack. It must
   work when opened directly from disk (`file://`).
2. **Real data, embedded**: read `contract/cards.sample.json` and embed it verbatim as
   `const DATA = { ... };` in the script. ALL insight content (titles, bodies, stats, messages, drafts, names,
   news hook) must be rendered from `DATA`, not retyped into the HTML. Design chrome (page headings, button
   labels, taglines, progress UI) is yours to write. Read `contract/CARDS_CONTRACT.md` for what every field means.
3. **Seven pages in this order**, each showing the cards of one `kind`:
   1. `your_people` — ranked list, show all (5). Sort by `rank`.
   2. `memory_lane`
   3. `reconnect`
   4. `both_wanted`
   5. `unfinished_plans`
   6. `unanswered`
   7. `recap` — the finale; should feel like the shareable "Wrapped summary" moment.
   Pages 2–7: sort by `score` descending and show at most 4 cards. A page must look good with 1 card
   (`both_wanted` has exactly one) and with 4. How multiple cards share a page (stack, carousel within the
   page, vertical scroll, fan of cards, one hero + smaller ones...) is a core part of your design.
4. **Navigation**: right arrow / left arrow keys, and click or tap on the right / left side of the stage,
   move between pages. Show progress (segmented story bars, dots, a counter, your choice). The URL hash
   selects the starting page: `file.html#3` opens on page 3 (needed for screenshots). Interactive elements
   inside a card (buttons, links, scroll areas) must not trigger page navigation when clicked.
5. **Render every contract field faithfully**:
   - `title`, `body`
   - `stats`: generic label/value pairs; never hardcode which labels exist
   - `rank` on Your People
   - `evidence`: chat bubbles. `isFromOwner` true = right side, false = left. `isKey` true = visibly
     highlighted. Show a date separator when consecutive messages fall on different days or are 4+ hours
     apart. If a message's `threadName` differs from the card's `friend.name`, label which chat it came from
     (this happens on the `both_wanted` card and is the whole point of that insight).
   - `action`: a button with `action.label`. Clicking opens a sheet/modal with the `draft` in an editable
     textarea, a Copy button (use `navigator.clipboard`), a visible-but-inert Regenerate button, and a close
     control. When `draft` is null (recap), the sheet shows a shareable summary instead (title, body, stats).
   - `context`: when not null, show the news hook (`text`, `source`, `date`) with `url` as a real link
     opening in a new tab. Only one card has one; make it feel special, like a "why now" moment.
   - Empty `stats`, empty `evidence`, null `action`, null `context` all occur. Nothing may render as an
     empty box, "null" or "undefined".
6. **Branding**: clearly tied to Instagram through its visual language: the gradient
   (`#405DE6` `#5851DB` `#833AB4` `#C13584` `#E1306C` `#FD1D1D` `#F56040` `#F77737` `#FCAF45` `#FFDC80`),
   story rings around avatars, story progress bars, DM-style bubbles, rounded friendly UI. Avatars are
   initials inside a gradient ring (there are no photos). Do NOT draw or include the Instagram logo, camera
   glyph or wordmark, and do not mention or imitate Spotify's name or logo. A small line such as
   "made for Instagram DMs" is fine. Working product name: **"wrapped"** is off-limits as a standalone brand;
   use **"Your DMs, in review"** or invent a short name of your own.
7. **Format**: unless your direction says otherwise, a phone-portrait stage (about 9:16, max ~430px wide,
   fitting within the viewport height) centered on a desktop page with a tasteful backdrop, and filling the
   screen on an actual phone. Content that doesn't fit scrolls inside the stage.
8. **Quality bar**: distinctive, confident, modern. Big type, real hierarchy, generous spacing, subtle motion
   on page change (CSS transitions/animations; respect `prefers-reduced-motion`). Accessible contrast for
   body text. No lorem ipsum. No emoji used as icons (inline SVG is fine). Do not use em dashes in any copy
   you write.

## Verify before you finish

Google Chrome is installed. Take screenshots and LOOK at them (use the Read tool on the PNGs), then fix what
is ugly, clipped, overlapping or broken. At minimum check pages 1, 2, 4 and 7, and one with the action
sheet open if you can.

```
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
"$CHROME" --headless=new --disable-gpu --hide-scrollbars --virtual-time-budget=4000 \
  --window-size=1280,900 --screenshot=/ABSOLUTE/PATH/shot.png "file:///ABSOLUTE/PATH/mockups/NAME.html#1"
```

Save screenshots under `mockups/shots/<given-name>-p<N>.png`. Also run with
`--enable-logging=stderr --v=0` once (or `--dump-dom`) and confirm there are no JavaScript errors and that
real titles from the data appear in the DOM.

## Rules of engagement

Work only inside `mockups/`. Create only your own HTML file and your own screenshots. Do not modify any
other file in the repository, do not run git commands, do not start servers.

Report back in under 150 words: the file path, the design idea in one sentence, how multiple cards share a
page, and anything that is unfinished or that you are unhappy with.
