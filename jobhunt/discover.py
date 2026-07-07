"""Entrypoint A (scheduled, twice daily).

fetch sources -> dedupe against Notion + seen log -> score unseen jobs ->
create tickets for matches -> append scan log -> send one Telegram digest.

Notion is the UI; the seen log is an append-only record of every job ever
enriched/scored (including below-threshold), so repeat runs skip LLM cost.
"""
from __future__ import annotations

import logging

from . import notify, notion
from .config import cfg
from .enrich import enrich_all
from .normalize import canonical
from .score import score
from .seen import SeenLog
from .sources import jobspy_source, visa_repo_source

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
log = logging.getLogger("jobhunt.discover")


def run() -> None:
    cv = cfg.load_cv()

    log.info("building skip set from Notion board + seen log…")
    skip = notion.existing_urls()
    notion_count = len(skip)

    seen_log = SeenLog(cfg.seen_log)
    file_seen = seen_log.load_urls()
    skip |= file_seen
    log.info(
        "skip set: %d notion + %d seen log → %d unique URLs",
        notion_count,
        len(file_seen),
        len(skip),
    )

    jobs = jobspy_source.fetch()
    jobs += visa_repo_source.fetch()
    log.info("fetched %d jobs across sources", len(jobs))

    fresh, batch_seen = [], set()
    for j in jobs:
        u = canonical(j.url) if j.url else ""
        if u and u not in skip and u not in batch_seen:
            fresh.append(j)
            batch_seen.add(u)
    log.info("%d fresh jobs after dedupe", len(fresh))

    enrich_all(fresh)

    created: list = []
    appended = 0
    for j in fresh:
        s, why = score(j, cv)
        ticket_created = False
        if s >= cfg.threshold:
            try:
                notion.create_ticket(j, s, why)
                created.append((j, s, why))
                ticket_created = True
                log.info("ticket %d — %s @ %s", s, j.role, j.company)
            except Exception as e:
                log.warning("failed to create ticket for %s: %s", j.url, e)

        if seen_log.record_scan(
            url=j.url,
            source=j.source,
            score=s,
            ticket=ticket_created,
            post_date=j.post_date,
        ):
            appended += 1

    log.info(
        "created %d tickets (threshold %d); appended %d scan log entries",
        len(created),
        cfg.threshold,
        appended,
    )
    notify.digest(created)


if __name__ == "__main__":
    run()
