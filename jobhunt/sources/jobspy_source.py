"""Job-board source: wraps python-jobspy across every (title x country).

Indeed and LinkedIn are scraped separately with board-specific search terms.
Remote is baked into search_term so Indeed can keep using hours_old.
"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
from jobspy import scrape_jobs

from ..config import cfg
from ..models import JobPost
from ..normalize import canonical

log = logging.getLogger("jobhunt.jobspy")

_MAX_WORKERS = 6

# Indeed searches descriptions too — use quoted titles, OR synonyms, and exclusions.
# See https://github.com/speedyapply/JobSpy#frequently-asked-questions
_INDEED_TEMPLATES: dict[str, str] = {
    "Backend Engineer": (
        '("Backend Engineer" OR "Back-end Engineer") '
        "(python OR golang OR java OR node) "
        "-frontend -sales -marketing -intern"
    ),
    "Platform Engineer": (
        '("Platform Engineer" OR "DevOps Engineer") '
        "(kubernetes OR terraform OR aws OR gcp) "
        "-sales -recruiter -intern"
    ),
    "Site Reliability Engineer": (
        '("Site Reliability Engineer" OR SRE) '
        "(kubernetes OR observability OR linux OR prometheus) "
        "-manager -sales -intern"
    ),
}


def _indeed_search_term(title: str, remote: bool) -> str:
    base = _INDEED_TEMPLATES.get(title, f'"{title}"')
    return f"{base} remote" if remote else base


def _linkedin_search_term(title: str, remote: bool) -> str:
    return f"{title} remote" if remote else title


_BOARD_SEARCH = {
    "indeed": _indeed_search_term,
    "linkedin": _linkedin_search_term,
}


def _to_jobpost(row: pd.Series, remote: bool) -> JobPost | None:
    url = str(row.get("job_url") or "").strip()
    if not url:
        return None
    interval = row.get("interval")
    lo, hi = row.get("min_amount"), row.get("max_amount")
    salary = f"{lo:g}-{hi:g} {interval}" if pd.notna(lo) and pd.notna(hi) else None
    posted = row.get("post_date")
    if pd.isna(posted):
        posted = row.get("date_posted")
    return JobPost(
        position=str(row.get("position") or row.get("title") or "").strip(),
        company=str(row.get("company") or "").strip(),
        url=canonical(url),
        source=str(row.get("site") or "board"),
        location=str(row.get("location") or "").strip(),
        country=str(row.get("country") or "").strip(),
        salary=salary,
        remote=remote or bool(row.get("is_remote")),
        post_date=str(posted) if pd.notna(posted) else None,
        description=str(row.get("description") or ""),
    )


def _rows_to_jobs(df: pd.DataFrame | None, remote: bool) -> list[JobPost]:
    if df is None or df.empty:
        return []
    out: list[JobPost] = []
    for _, row in df.iterrows():
        jp = _to_jobpost(row, remote)
        if jp and jp.role and jp.url:
            if remote and not jp.country:
                jp.country = "Remote"
            out.append(jp)
    return out


def _scrape_board(board: str, title: str, country: str) -> list[JobPost]:
    search_fn = _BOARD_SEARCH.get(board)
    if not search_fn:
        log.warning("unsupported board %r, skipping", board)
        return []

    remote = country.strip().lower() == "remote"
    kwargs: dict = dict(
        site_name=[board],
        search_term=search_fn(title, remote),
        results_wanted=cfg.max_jobs_per_query,
        hours_old=cfg.hours_old,
        description_format="markdown",
    )
    if remote:
        # Remote is in search_term (Indeed hours_old compat). LinkedIn rejects
        # location="Remote"; use a broad region instead.
        kwargs["location"] = "Europe" if board == "linkedin" else "Remote"
    else:
        kwargs.update(location=country, country_indeed=country)

    try:
        df = scrape_jobs(**kwargs)
    except Exception as e:
        log.warning("scrape failed for %s / %r / %r: %s", board, title, country, e)
        return []

    jobs = _rows_to_jobs(df, remote)
    log.info("scraped %d from %s for %r / %r", len(jobs), board, title, country)
    return jobs


def fetch() -> list[JobPost]:
    boards = [b for b in cfg.boards if b in _BOARD_SEARCH]
    tasks = [
        (board, title, country)
        for country in cfg.countries
        for title in cfg.titles
        for board in boards
    ]
    jobs: list[JobPost] = []
    with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as pool:
        futures = {
            pool.submit(_scrape_board, board, title, country): (board, title, country)
            for board, title, country in tasks
        }
        for future in as_completed(futures):
            board, title, country = futures[future]
            try:
                jobs.extend(future.result())
            except Exception as e:
                log.warning(
                    "scrape task failed for %s / %r / %r: %s",
                    board, title, country, e,
                )
    return jobs
