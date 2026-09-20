# Insta Insights - HackMIT 2026

Arav Chadha, Rafay Farah, Roman Stashkiv, Candy Xie  

![Insta Insights](thumbnail/insta-insights-thumbnail.png)

Insta Insights is your Instagram DMs, in review. It reads your message history and turns it into a seven-page story about your friendships: who has mattered most, the moments you forgot, the question you never answered, the plan you keep making and never do. Every insight shows the real messages behind it and ends in a suggested message, written the way you text, so that noticing a friendship turns into reaching out.

## What It Does

- Ranks **Your People** by shared history with a penalty for silence, and leaves out chats that are only logistics.
- Surfaces **Memory Lane** moments: funny or warm conversations from at least six months ago, with the best lines highlighted.
- Finds **Reconnect** topics: something two friends talked about constantly that faded while they kept talking, plus a web search for a recent reason to bring it back up.
- Finds **You Both Wanted This**: a friend said they want to try something, and you said the same thing to a different friend, months apart, in different words.
- Finds **Unfinished Plans** that came up in two or more conversations and never happened, even when worded differently each time.
- Finds **Unanswered Moments**: a friend asked something that mattered, you kept talking, and never answered.
- Builds a **Friendship Recap** for your closest friends from everything above.
- Shows the evidence for every claim as the original chat bubbles, with the key message highlighted.
- Writes a draft message for each insight in your own texting style, which you can edit, regenerate and copy.

## Project Structure

- `insights/`
  - `inbox.py` parses Instagram's "Download your information" HTML export into threads
  - `windows.py` splits threads into conversations on long silences
  - `index.py` indexes messages and conversations into Elasticsearch
  - `your_people.py`, `memory_lane.py`, `reconnect.py`, `both_wanted.py`, `unfinished_plans.py`, `unanswered.py`, `recap.py` are the seven insights
  - `judge.py` is the single place a language model is called, returning validated structured output
  - `cards.py` writes insights in the JSON shape the frontend reads
  - `server.py` serves the frontend and the cards over HTTP
- `frontend/` is the story interface, one self-contained HTML file
- `contract/` is the JSON contract between backend and frontend, with example and real sample output
- `corpus/` holds the scripted synthetic conversations, the builder that renders them as an Instagram export, and the scorer
- `data/` holds the generated synthetic inbox and its answer key
- `mockups/` holds the twelve design directions the team chose from
- `tests/` has one test file per source file

## Core Flow

1. `ingest` parses the Instagram export and indexes every message and every conversation into Elasticsearch. Conversations get ELSER semantic embeddings through a `semantic_text` field.
2. Each insight narrows thousands of messages to a few dozen candidates with Elasticsearch alone: aggregations for Your People, phrase search for plans and wishes, `significant_text` for faded topics, and semantic search to link reworded mentions across chats.
3. A small model (Claude Haiku) judges each candidate and returns structured output: was the question ever answered, is this the same plan, did it happen, is this moment worth remembering.
4. A larger model (Claude Opus) writes the card's title, body and the draft message, matching how the owner texts in the evidence.
5. For public Reconnect topics only, the judge searches the web for recent news. Only the topic's name is searched, never a message. A hook is kept only with a real link and a date in the last four months.
6. The cards are written as JSON in the shape fixed by `contract/CARDS_CONTRACT.md`, and the frontend renders them as a story you move through with the arrow keys.

A full run takes about 25 seconds and costs a few cents, because search does the narrowing before any model is called.

## Tech Stack

- Python 3
- Elasticsearch on Elastic Cloud (aggregations, `significant_text`, `semantic_text` with ELSER)
- Claude API (Haiku for judging, Opus for writing, the web search tool for news hooks)
- FastAPI and Uvicorn
- Beautiful Soup
- Plain HTML, CSS and JavaScript for the frontend
- pytest

## Local Setup

1. Create a virtual environment and install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Create your config file:

```bash
cp .env.example .env
```

3. Fill in `.env`:

- `ELASTIC_URL`
- `ELASTIC_API_KEY`
- `ANTHROPIC_API_KEY`

4. Index the synthetic inbox:

```bash
python -m insights ingest data/corpus/inbox
```

5. Generate the cards:

```bash
python -m insights cards
```

6. Start the server and open http://localhost:8000:

```bash
python -m insights serve
```

Use the left and right arrow keys to move between pages, and up and down to move between cards on a page.

## Development Notes

- Run the tests with `python -m pytest`. They are offline and free: no Elasticsearch or model calls.
- `python -m insights cards --only reconnect` runs a single insight while iterating.
- `python -m corpus.score cards.json` scores a run against the answer key.
- `python -m corpus.build` regenerates the synthetic inbox from the scripts in `corpus/threads/`.
- `cards.json` and `.env` are gitignored. Restart the server after changing Python code.
- To use your own data, request your Instagram export as HTML, put the `inbox` folder under `data/private/` (gitignored), and ingest that path.

## Testing Against an Answer Key

All chat data in this repository is synthetic. The inbox is 12,855 messages across seven conversations, written as scripts and rendered into Instagram's export format, with 13 planted moments the insights should find and 7 decoys they should ignore: a question answered a day late, a plan that actually happened, a wish only one person has. A full run finds 13 of 13 and flags 0 of 7, with no stray cards. These numbers measure the pipeline on data we designed, not accuracy on real inboxes.

## Current Backend Capabilities

- Instagram HTML export parsing, including multi-file threads, reactions, forwarded reels and deleted accounts
- Message and conversation indexing with stable content-hash ids
- Seven insights, run concurrently
- Structured model output validated against typed schemas
- News hooks with source links, behind a public-topic gate
- `GET /cards`, `POST /cards/refresh` and `POST /cards/{id}/regenerate`
- An answer-key scorer for the synthetic inbox

## Summary

Nobody loses a friend in a fight. They lose them to being busy, and the thing that would fix it is already in their messages, under thousands of others they will never scroll back through. Insta Insights uses search to find those moments and language models to understand them, then hands you the one message that picks the friendship back up.
