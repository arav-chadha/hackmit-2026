# Round 2 brief: full-screen, no scrolling

Read `mockups/BRIEF.md` first: everything in it still applies EXCEPT where this file overrides it. The team
saw the phone-format round 1 mockups (`mockups/01-stories.html` and `mockups/03-dm.html` are finished; open
them and their screenshots in `mockups/shots/` for the visual language and the quality bar) and gave this
feedback:

> They should fill the screen instead of being like iPhone stories. It can still have the story-type element
> at the top, but you shouldn't need to scroll to see all the insights.

## Overrides

1. **Fill the viewport.** The experience occupies the whole browser window (`100vw` x `100dvh`), edge to
   edge. No phone frame, no centered narrow stage, no decorative side panels. Requirement 7 of the original
   brief is void.
2. **No scrolling, anywhere, at laptop size.** At 1440x800 and at 1280x720 every page must show ALL of its
   cards and all of their content with no page scroll, no scrolling region inside the stage, no scrolling
   inside a card, and nothing clipped or overlapping. Size type and spacing with `clamp()` / viewport units /
   container queries so the layout breathes at 1440x800 and still fits at 1280x720. Below ~900px wide
   (phones) it may stack into one column and scroll; that fallback only needs to be tidy, not designed.
3. **Card caps** (this replaces "at most 4"): pages 2 to 7 show at most **3** cards, the top 3 by `score`.
   Page 1 (Your People) shows all 5 as a compact ranking. `both_wanted` has exactly 1 card and `reconnect`
   and `unfinished_plans` have 2: pages with fewer cards must use the space well (bigger card, bigger type,
   bigger evidence), never look like a 3-slot grid with holes.
4. **Evidence cap on the page:** show at most **6** messages per card on the page. Always include every
   `isKey` message; fill the rest with the messages nearest to them, keeping original order. When messages
   were left out, show a small "+N more" affordance that opens the FULL conversation in a modal (the modal
   may scroll). Date separators and the different-chat labels still apply to what is shown.
5. **Story element stays:** a seven-segment story progress bar across the full width at the top, with the
   page name and an `n / 7` counter. Arrow keys, clicking the left/right edge zones, and clicking a segment
   all navigate. Hash start (`#3`) still required.
6. **Self-check hook (required):** if the URL hash ends in `&check` (for example `#2&check`), after the page
   has rendered and fonts have loaded, write a JSON report into `<pre id="overflow-report">` appended to
   `<body>`: `{page, viewport: [w, h], pageScrolls: <documentElement.scrollHeight > innerHeight + 1>,
   clipped: [<short selector or text snippet of every element inside the stage whose scrollHeight > clientHeight + 1
   or scrollWidth > clientWidth + 1, ignoring elements that are intentionally hidden or are modals>]}`.
   Then run Chrome with `--dump-dom` for all 7 pages at both sizes and confirm `pageScrolls` is false and
   `clipped` is empty everywhere. Fix the layout, not the check.

## Verify before you finish

```
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
"$CHROME" --headless=new --disable-gpu --hide-scrollbars --virtual-time-budget=5000 \
  --window-size=1440,800 --screenshot=/ABS/mockups/shots/NAME-p1.png "file:///ABS/mockups/NAME.html#1"
"$CHROME" --headless=new --disable-gpu --virtual-time-budget=5000 --window-size=1280,720 \
  --dump-dom "file:///ABS/mockups/NAME.html#1&check" | grep -A3 overflow-report
```

Screenshot all 7 pages at 1440x800, and pages 1, 2 and 7 at 1280x720 (suffix `-sm`). LOOK at the
screenshots with the Read tool: the automated check cannot see ugly, cramped or unbalanced. Memory Lane
(page 2, three cards with long conversations) and Your People (page 1, five people) are the hardest pages:
get those right first. Also capture one screenshot with the action sheet open.

Report back in under 150 words: file path, the idea in one sentence, which layout strategy you used for
multiple cards, the overflow-check result at both sizes, and anything you are unhappy with.
