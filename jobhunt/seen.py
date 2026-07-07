"""Append-only scan log for jobs processed by discover.

Each line is one immutable JSON record. URLs are never removed or rewritten;
first-seen wins — duplicate URLs are skipped on append and on read.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from .normalize import canonical

log = logging.getLogger("jobhunt.seen")


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class SeenLog:
    """JSONL append-only log keyed by canonical Job URL."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._urls: set[str] = set()

    def load_urls(self) -> set[str]:
        """Read every line; return the set of URLs ever scanned."""
        self._urls.clear()
        if not self.path.exists():
            return set()
        with self.path.open(encoding="utf-8") as f:
            for lineno, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    url = canonical(str(entry.get("url", "")))
                    if url:
                        self._urls.add(url)
                except (json.JSONDecodeError, TypeError) as e:
                    log.warning("seen log line %d skipped: %s", lineno, e)
        log.info("seen log has %d URLs at %s", len(self._urls), self.path)
        return set(self._urls)

    def record_scan(
        self,
        *,
        url: str,
        source: str,
        score: int,
        ticket: bool,
        post_date: str | None = None,
    ) -> bool:
        """Append one line if this URL was never logged before. Returns True if appended."""
        key = canonical(url)
        if not key:
            return False
        if key in self._urls:
            return False

        self.path.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "url": key,
            "scanned_at": _utc_now(),
            "source": source,
            "score": score,
            "ticket": ticket,
        }
        if post_date:
            entry["post_date"] = post_date

        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        self._urls.add(key)
        return True
