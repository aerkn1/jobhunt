"""Entrypoint B (on demand).

Finds tickets you dragged to 'Approved' that have no draft yet, generates a
tailored CV + cover letter, and writes them into the ticket body. Then pings you.

This step NEVER submits an application — it only prepares documents for you.
Run it manually (workflow_dispatch) after approving cards, not on a fast cron.
"""
from __future__ import annotations

import logging

from . import draft, notify, notion
from .config import cfg

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
log = logging.getLogger("jobhunt.approve")


def run() -> None:
    cv = cfg.load_cv()
    approved = notion.query_status("Approved")
    log.info("%d approved tickets", len(approved))

    done = 0
    for page in approved:
        if notion.has_draft(page["id"]):
            continue
        job = notion.read_job(page)
        try:
            tailored_cv, cover = draft.generate(job, cv)
            notion.append_draft(page["id"], tailored_cv, cover)
            notify.draft_ready(job)
            done += 1
            log.info("drafted: %s @ %s", job.role, job.company)
        except Exception as e:
            log.warning("draft failed for %s: %s", job.url, e)

    log.info("generated %d drafts", done)


if __name__ == "__main__":
    run()
