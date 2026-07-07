"""Notion board: UI + source of truth for dedupe.

create_ticket upserts by Job URL so a race or double-run can't duplicate cards.
existing_urls() is the fast dedupe set pulled at the start of each run.

Uses Notion API 2025-09-03: queries go through data_sources, not databases.
"""
from __future__ import annotations

import logging
import time

from notion_client import Client

from .config import cfg
from .models import JobPost
from .normalize import canonical

log = logging.getLogger("jobhunt.notion")
_notion = Client(auth=cfg.notion_token)
DB = cfg.notion_db_id

_ds_id: str | None = None
_schema_checked = False
_prop_types: dict[str, str] | None = None

# Property names must match the board schema (see scripts/setup_notion_db.py).
REQUIRED_PROPERTIES = (
    "Role", "Company", "Location", "Fit Score", "Why Fit",
    "Job URL", "Source", "Visa", "Remote", "Status",
)
OPTIONAL_PROPERTIES = ("Country", "Salary", "Date Posted", "Date Found")


def _data_source_id() -> str:
    """Resolve the primary data source for NOTION_DB_ID (cached)."""
    global _ds_id
    if _ds_id is not None:
        return _ds_id
    db = _notion.databases.retrieve(database_id=DB)
    sources = db.get("data_sources") or []
    if not sources:
        raise RuntimeError(
            f"Database {DB} has no data_sources — check integration access "
            "and Notion API version."
        )
    _ds_id = sources[0]["id"]
    log.debug(
        "resolved data_source_id=%s (%s)",
        _ds_id,
        sources[0].get("name", ""),
    )
    _validate_schema()
    return _ds_id


def data_source_properties() -> dict[str, dict]:
    """Property name → schema object for the job-hunt data source."""
    ds = _notion.data_sources.retrieve(_data_source_id())
    return ds.get("properties") or {}


def _validate_schema() -> None:
    global _schema_checked, _prop_types
    if _schema_checked:
        return
    props = _notion.data_sources.retrieve(_ds_id)["properties"]  # type: ignore[arg-type]
    _prop_types = {k: v["type"] for k, v in props.items()}
    missing = [name for name in REQUIRED_PROPERTIES if name not in props]
    if missing:
        found = sorted(props.keys())
        raise RuntimeError(
            "Notion board schema mismatch.\n"
            f"  Missing: {missing}\n"
            f"  Found:   {found}\n"
            "Add the missing columns in Notion (types in setup_notion_db.py) or run:\n"
            "  python -m jobhunt.scripts.inspect_notion_db\n"
            "  python -m jobhunt.scripts.setup_notion_db <PARENT_PAGE_ID>"
        )
    role_type = _prop_types.get("Role")
    if role_type not in ("title", "rich_text"):
        raise RuntimeError(
            f'Notion "Role" must be Title or Text, not {role_type!r}.'
        )
    _schema_checked = True


def _text_prop(name: str, text: str, *, fallback: str = "") -> dict:
    """Write a text value using title or rich_text to match the board column type."""
    types = _prop_types or {}
    content = ((text or fallback) or "")[:1900]
    if types.get(name) == "title":
        return {"title": [{"text": {"content": content or "(untitled)"}}]}
    return {"rich_text": [{"text": {"content": content}}]}


def _has_prop(name: str) -> bool:
    return name in (_prop_types or {})


def _query_data_source(**kwargs):
    return _notion.data_sources.query(_data_source_id(), **kwargs)


# ---- reads ----------------------------------------------------------
def existing_urls() -> set[str]:
    """Every Job URL already on the board (any lane) = the dedupe set."""
    urls: set[str] = set()
    cursor = None
    while True:
        resp = _query_data_source(
            filter={"property": "Job URL", "url": {"is_not_empty": True}},
            start_cursor=cursor,
            page_size=100,
        )
        for page in resp["results"]:
            u = (page["properties"].get("Job URL", {}) or {}).get("url")
            if u:
                urls.add(canonical(u))
        if not resp.get("has_more"):
            break
        cursor = resp["next_cursor"]
        time.sleep(0.34)  # stay under ~3 req/s
    return urls


def find_by_url(url: str) -> str | None:
    resp = _query_data_source(
        filter={"property": "Job URL", "url": {"equals": canonical(url)}},
        page_size=1,
    )
    results = resp.get("results", [])
    return results[0]["id"] if results else None


def query_status(status: str) -> list[dict]:
    out, cursor = [], None
    while True:
        resp = _query_data_source(
            filter={"property": "Status", "status": {"equals": status}},
            start_cursor=cursor,
            page_size=100,
        )
        out.extend(resp["results"])
        if not resp.get("has_more"):
            break
        cursor = resp["next_cursor"]
        time.sleep(0.34)
    return out


# ---- writes ---------------------------------------------------------
def _props(job: JobPost, score: int, reason: str) -> dict:
    p = {
        "Role": _text_prop("Role", job.role),
        "Company": _text_prop("Company", job.company),
        "Location": _text_prop("Location", job.location),
        "Fit Score": {"number": score},
        "Why Fit": _text_prop("Why Fit", reason),
        "Job URL": {"url": job.url},
        "Source": {"select": {"name": job.source[:100] or "board"}},
        "Visa": {"select": {"name": job.visa}},
        "Remote": {"checkbox": bool(job.remote)},
        "Status": {"status": {"name": cfg.new_lane}},
    }
    if job.country and _has_prop("Country"):
        p["Country"] = _text_prop("Country", job.country)
    elif job.country and not _has_prop("Country"):
        log.debug("skipping Country (column not on board)")
    if job.salary and _has_prop("Salary"):
        p["Salary"] = _text_prop("Salary", job.salary)
    return p


def _jd_blocks(description: str) -> list[dict]:
    chunks = [description[i:i + 1900] for i in range(0, len(description or ""), 1900)][:20]
    return [{
        "object": "block", "type": "paragraph",
        "paragraph": {"rich_text": [{"text": {"content": c}}]},
    } for c in chunks] or [{
        "object": "block", "type": "paragraph",
        "paragraph": {"rich_text": [{"text": {"content": "(no description)"}}]},
    }]


def create_ticket(job: JobPost, score: int, reason: str) -> str:
    """Idempotent: if a ticket with this URL exists, return it untouched."""
    existing = find_by_url(job.url)
    if existing:
        return existing
    page = _notion.pages.create(
        parent={"type": "data_source_id", "data_source_id": _data_source_id()},
        properties=_props(job, score, reason),
        children=_jd_blocks(job.description),
    )
    return page["id"]


def append_draft(page_id: str, tailored_cv: str, cover_letter: str) -> None:
    def heading(text):
        return {"object": "block", "type": "heading_2",
                "heading_2": {"rich_text": [{"text": {"content": text}}]}}

    def paras(text):
        return [{
            "object": "block", "type": "paragraph",
            "paragraph": {"rich_text": [{"text": {"content": text[i:i + 1900]}}]},
        } for i in range(0, len(text), 1900)][:25]

    _notion.blocks.children.append(block_id=page_id, children=(
        [heading("Tailored CV")] + paras(tailored_cv)
        + [heading("Cover letter")] + paras(cover_letter)
    ))


def has_draft(page_id: str) -> bool:
    kids = _notion.blocks.children.list(block_id=page_id, page_size=100)["results"]
    for b in kids:
        if b.get("type") == "heading_2":
            txt = "".join(t["plain_text"] for t in b["heading_2"]["rich_text"])
            if "Tailored CV" in txt:
                return True
    return False


def read_job(page: dict) -> JobPost:
    p = page["properties"]

    def txt(name):
        v = p.get(name, {})
        arr = v.get("rich_text") or v.get("title") or []
        return "".join(x["plain_text"] for x in arr)

    return JobPost(
        position=txt("Role"),
        company=txt("Company"),
        location=txt("Location"),
        url=(p.get("Job URL", {}) or {}).get("url", ""),
        source=(p.get("Source", {}).get("select") or {}).get("name", "board"),
        country=txt("Country"),
        description=txt("Why Fit"),
    )
