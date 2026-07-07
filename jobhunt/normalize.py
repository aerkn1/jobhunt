"""URL canonicalization for dedupe.

Since the Job URL is the dedupe key (Notion is the source of truth), we must
strip volatile tracking params while KEEPING identifier params. E.g. Indeed's
`viewjob?jk=XXXX` — the `jk` is the job id and must survive; but `refId`,
`trackingId`, `utm_*` on LinkedIn are noise and must be removed, or the same
posting appears "new" every run.
"""
from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

# Params that are pure tracking/session noise -> drop them.
_TRACKING = {
    "refid", "trackingid", "trk", "trkinfo", "originaltrk", "position",
    "pagenum", "src", "source", "from", "utm_source", "utm_medium",
    "utm_campaign", "utm_term", "utm_content", "gclid", "fbclid", "spa",
    "recommended", "eblc", "reflink",
}


def canonical(url: str) -> str:
    if not url:
        return url
    try:
        s = urlsplit(url.strip())
    except ValueError:
        return url.strip()

    scheme = (s.scheme or "https").lower()
    netloc = s.netloc.lower()
    path = s.path.rstrip("/") or "/"

    kept = [(k, v) for k, v in parse_qsl(s.query, keep_blank_values=False)
            if k.lower() not in _TRACKING]
    kept.sort()  # order-independent so ?a=1&b=2 == ?b=2&a=1
    query = urlencode(kept)

    return urlunsplit((scheme, netloc, path, query, ""))  # fragment dropped
