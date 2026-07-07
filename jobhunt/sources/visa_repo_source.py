"""Visa-sponsored jobs source: shallow-clone the repo and parse jobList.json.

No scraping — it's a maintained list, so this is the safest source.
Filters entries to the configured countries and title keywords.
"""
from __future__ import annotations

import json
import logging
import subprocess
import tempfile
from pathlib import Path

from ..config import cfg
from ..models import JobPost
from ..normalize import canonical

log = logging.getLogger("jobhunt.visa")

_JOB_LIST = "jobList.json"


def _clone(url: str) -> Path | None:
    dst = Path(tempfile.mkdtemp(prefix="visa_repo_"))
    try:
        subprocess.run(["git", "clone", "--depth", "1", url, str(dst)],
                       check=True, capture_output=True, timeout=120)
        return dst
    except Exception as e:
        log.warning("visa repo clone failed: %s", e)
        return None


def _load_job_list(root: Path) -> list[dict]:
    path = root / _JOB_LIST
    if not path.exists():
        log.warning("%s not found in cloned repo", _JOB_LIST)
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        log.warning("failed to read %s: %s", _JOB_LIST, e)
        return []
    return data if isinstance(data, list) else []


def _normalize_location(raw: str) -> str:
    return " ".join(raw.split())


def _matches(position: str, company: str, location: str) -> bool:
    loc = location.lower()
    is_remote = "remote" in loc
    country_ok = (not cfg.countries) or any(
        (c.lower() == "remote" and is_remote) or c.lower() in loc
        for c in cfg.countries
    )
    text = f"{position} {company}".lower()
    title_ok = (not cfg.titles) or any(
        any(w in text for w in t.lower().split()) for t in cfg.titles
    )
    return country_ok and title_ok


def fetch() -> list[JobPost]:
    if not cfg.visa_enabled:
        return []
    root = _clone(cfg.visa_url)
    if not root:
        return []

    jobs: list[JobPost] = []
    for item in _load_job_list(root):
        if not isinstance(item, dict):
            continue
        position = (item.get("position") or "").strip()
        company = (item.get("company") or "").strip()
        location = _normalize_location(item.get("location") or "")
        url = (item.get("description") or "").strip()  # JSON field holds apply URL
        if not (position and url and _matches(position, company, location)):
            continue
        is_remote = "remote" in location.lower()
        jobs.append(JobPost(
            position=position,
            company=company or "(unknown)",
            url=canonical(url),
            source="visa_repo",
            location=location,
            country="Remote" if is_remote else location,
            remote=is_remote,
            visa="yes",
            post_date=item.get("post_date") or None,
            description=(
                f"Visa-sponsored: {position} at {company or 'unknown'}. "
                f"Location: {location}. "
                f"Contract: {item.get('contract') or 'n/a'}. "
                f"Relocation: {item.get('reloc') or 'n/a'}."
            ),
        ))
    log.info("visa repo: %d matching rows", len(jobs))
    return jobs
