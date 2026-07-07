"""Fetch job page text for sources that only provide a URL (visa_repo)."""
from __future__ import annotations

import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
import trafilatura

from .config import cfg
from .models import JobPost

log = logging.getLogger("jobhunt.enrich")

_USER_AGENT = "jobhunt/1.0 (job discovery; contact via GitHub)"
_MIN_CHARS = 200
_MAX_DESC = 6000


def _strip_html(html: str) -> str:
    cleaned = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.S | re.I)
    cleaned = re.sub(r"<style[^>]*>.*?</style>", " ", cleaned, flags=re.S | re.I)
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _extract_text(html: str, url: str) -> str:
    text = trafilatura.extract(
        html,
        url=url,
        include_comments=False,
        include_tables=True,
    )
    if text:
        text = text.strip()
        if len(text) >= _MIN_CHARS:
            return text
    fallback = _strip_html(html)
    return fallback if len(fallback) >= _MIN_CHARS else ""


def _fetch_page_text(url: str) -> str:
    resp = requests.get(
        url,
        timeout=cfg.visa_fetch_timeout,
        headers={"User-Agent": _USER_AGENT},
        allow_redirects=True,
    )
    resp.raise_for_status()
    if not resp.text:
        return ""
    return _extract_text(resp.text, url)[:_MAX_DESC]


def enrich(job: JobPost) -> JobPost:
    """Replace stub description with fetched page text when possible."""
    if job.source != "visa_repo" or not cfg.visa_fetch_job_page or not job.url:
        return job
    try:
        text = _fetch_page_text(job.url)
    except Exception as e:
        log.warning("enrich failed %s @ %s: %s", job.role, job.company, e)
        return job
    if text:
        job.description = text
        log.info("enriched %s @ %s (%d chars)", job.role, job.company, len(text))
    else:
        log.warning("enrich empty %s @ %s — keeping stub", job.role, job.company)
    return job


def enrich_all(jobs: list[JobPost]) -> None:
    """Enrich visa_repo jobs in parallel; mutates jobs in place."""
    targets = [
        j for j in jobs
        if j.source == "visa_repo" and cfg.visa_fetch_job_page and j.url
    ]
    if not targets:
        return
    workers = min(cfg.visa_fetch_max_concurrent, len(targets))
    log.info("enriching %d visa_repo jobs (%d workers)", len(targets), workers)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(enrich, j) for j in targets]
        for fut in as_completed(futures):
            try:
                fut.result()
            except Exception as e:
                log.warning("enrich worker error: %s", e)
