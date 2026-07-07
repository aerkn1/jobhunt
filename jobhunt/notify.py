"""Telegram notifications: a short push pointing you back to the Notion board."""
from __future__ import annotations

import html
import logging
import os

import requests

from .config import cfg
from .models import JobPost

log = logging.getLogger("jobhunt.notify")
_BOARD_URL = os.environ.get("NOTION_BOARD_URL", "your Notion board")


def _link(url: str, label: str) -> str:
    if not url:
        return html.escape(label)
    return (
        f'<a href="{html.escape(url, quote=True)}">'
        f'{html.escape(label)}</a>'
    )


def _send(text: str) -> None:
    if not (cfg.telegram_token and cfg.telegram_chat_id):
        log.info("telegram not configured; skipping. Message was:\n%s", text)
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{cfg.telegram_token}/sendMessage",
            json={
                "chat_id": cfg.telegram_chat_id,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
            timeout=20,
        )
    except Exception as e:
        log.warning("telegram send failed: %s", e)


def _job_line(job: JobPost, score: int) -> str:
    label = f"{score} — {job.role} @ {job.company} ({job.country or 'Remote'})"
    return f"• {_link(job.url, label)}"


def digest(created: list[tuple[JobPost, int, str]]) -> None:
    if not created:
        return
    created = sorted(created, key=lambda t: -t[1])
    lines = [_job_line(j, s) for j, s, _ in created[:20]]
    more = f"\n…and {len(created) - 20} more" if len(created) > 20 else ""
    if _BOARD_URL.startswith("http"):
        board = f"\n\n{_link(_BOARD_URL, 'Review in Notion')}"
    else:
        board = f"\n\nReview in Notion: {html.escape(_BOARD_URL)}"
    _send(
        f"{len(created)} new role(s) to review:\n"
        + "\n".join(lines)
        + more
        + board,
    )
    log.info("telegram notification sent")


def draft_ready(job: JobPost) -> None:
    header = (
        f"Draft ready: {html.escape(job.role)} @ {html.escape(job.company)}"
    )
    _send(f"{header}\n{_link(job.url, 'Apply')}")


def ping(text: str) -> None:
    _send(html.escape(text))
