# jobhunt

A stateless, twice-daily job-discovery pipeline. It scrapes job boards and a
visa-sponsorship list, scores each new role 0–100 against your CV with an LLM,
and creates a ticket in a **Notion Kanban** board for anything above your
threshold — then pings you on Telegram. You review and approve in Notion; an
on-demand step drafts a tailored CV + cover letter. **It never submits an
application for you** — submission stays a deliberate human action.

Runs entirely on **GitHub Actions** — no server, no local machine, no database
to maintain. Notion is both the UI and the dedupe source of truth.

```
sources ─► dedupe (vs Notion) ─► LLM score ─► Notion "New" lane ─► Telegram
                                                     │
                                        you drag New ─► Approved
                                                     │
                                        approve.py ─► drafts written back
                                                     │
                                        you submit manually ─► "Applied"
```

## What's where

| File | Role |
|---|---|
| `config.yaml` | All tunable knobs — countries, titles, threshold. Edit + commit; next run uses it. |
| `jobhunt/discover.py` | Scheduled entrypoint: fetch → dedupe → score → create tickets → notify. |
| `jobhunt/approve.py` | On-demand: draft CV + cover letter for `Approved` tickets. |
| `jobhunt/sources/` | `jobspy_source.py` (boards), `visa_repo_source.py` (visa list). |
| `jobhunt/notion.py` | Board CRUD, dedupe query, idempotent upsert-by-URL. |
| `jobhunt/normalize.py` | Canonicalizes URLs so the same posting dedupes correctly. |
| `.github/workflows/job-hunt.yml` | The cron + manual triggers. |

## Setup (about 15 minutes, once)

### 1. Notion
1. Create an **internal integration**: https://www.notion.so/my-integrations → copy the token (`NOTION_TOKEN`).
2. Create the database — either:
   - **By hand:** add a database, create the properties listed in
     `jobhunt/scripts/setup_notion_db.py`, and set the default view to **Board
     grouped by Status** with lanes: New, Reviewing, Approved, Applied,
     Interviewing, Offer, Rejected, Skipped; **or**
   - **By script:** share any page with your integration, then run
     `NOTION_TOKEN=... python -m jobhunt.scripts.setup_notion_db <PARENT_PAGE_ID>`
     and finish the Board view in the UI.
3. Open the database → `•••` → **Connections** → connect your integration.
   (Until you do this, the API sees nothing.)
4. Copy the database id (`NOTION_DB_ID`) from the database URL.

### 2. Telegram (optional but recommended)
1. Message **@BotFather** → `/newbot` → copy the bot token (`TELEGRAM_TOKEN`).
2. Message your new bot once, then visit
   `https://api.telegram.org/bot<TOKEN>/getUpdates` to find your chat id
   (`TELEGRAM_CHAT_ID`).

### 3. LLM key
OpenAI API key (`LLM_API_KEY`). Default model is `gpt-4o-mini` — model,
temperature, and token limits live under `llm:` in `config.yaml`.

### 4. Your CV
Put **one PDF** in **`cv/`** (any filename). Markdown is generated as **`cv/<name>.md`**
— run `python -m jobhunt.scripts.cv_from_pdf` once (or let `discover` regenerate when
the PDF changes). **Or** commit the generated `.md` only, **or** set the `CV_TEXT`
secret (pipeline prefers `CV_TEXT` when set).

### 5. GitHub
- **Settings → Secrets and variables → Actions → Secrets:**
  `NOTION_TOKEN`, `NOTION_DB_ID`, `LLM_API_KEY`, `TELEGRAM_TOKEN`,
  `TELEGRAM_CHAT_ID`, and optionally `CV_TEXT`.
- **Variables** (optional): `NOTION_BOARD_URL` — your board's URL, so Telegram
  digests deep-link straight to it.
- Push the repo. The schedule starts automatically.

Test immediately without waiting for the cron: **Actions → job-hunt → Run
workflow** (choose `discover`).

## Operating notes

- **Dedupe uses Notion + `.jobhunt/seen.jsonl`.** Every job that gets
  enriched/scored is appended to the log (append-only; never edited or deleted).
  Low-fit jobs do not need a Notion card to stay skipped. For tickets you
  review, move unwanted ones to `Skipped` rather than deleting — a deleted card
  looks brand-new to Notion dedupe.
- **Cron is UTC.** The workflow uses `06:00`/`15:00` UTC = `09:00`/`18:00`
  Istanbul (UTC+3, no DST). Change the hours if you move.
- **Scheduled runs can be delayed** a few minutes by GitHub under load — fine
  for this use case.
- **Private repos disable scheduled Actions after 60 days of no activity.** A
  cron isn't "activity" — either use a public repo (secrets stay hidden) or add
  an occasional commit.
- **Tune `fit_threshold`** in `config.yaml` (start ~80). Too low and the New
  lane becomes noise; commit a change and the next run respects it.
- **Cost** is a few cheap LLM calls per run (one per fresh job). Keep
  `max_jobs_per_query` modest to control it.

## Safety boundary

By design there is no `apply`, `submit`, or `login` capability anywhere in this
codebase. The pipeline stops at "draft prepared, you notified." Submitting —
and thus any interaction with a job site under your identity — is always done
by you, in your browser. This protects your accounts (LinkedIn/Indeed prohibit
automated submission) and keeps every application human-reviewed.

## Local run (optional)

```bash
pip install -r requirements.txt
export NOTION_TOKEN=... NOTION_DB_ID=... LLM_API_KEY=...
export TELEGRAM_TOKEN=... TELEGRAM_CHAT_ID=...
python -m jobhunt.discover     # or: python -m jobhunt.approve
```
