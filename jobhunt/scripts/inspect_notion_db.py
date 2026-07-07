"""Print the Notion board schema and compare to what jobhunt expects.

Usage:
    NOTION_TOKEN=... NOTION_DB_ID=... python -m jobhunt.scripts.inspect_notion_db
"""
from __future__ import annotations

import os
import sys

from notion_client import Client

from jobhunt.notion import OPTIONAL_PROPERTIES, REQUIRED_PROPERTIES

EXPECTED_TYPES: dict[str, str | tuple[str, ...]] = {
    "Role": ("title", "rich_text"),
    "Company": "rich_text",
    "Location": "rich_text",
    "Country": "rich_text",
    "Source": "select",
    "Fit Score": "number",
    "Why Fit": "rich_text",
    "Salary": "rich_text",
    "Remote": "checkbox",
    "Visa": "select",
    "Date Posted": "date",
    "Date Found": "created_time",
    "Job URL": "url",
    "Status": "status",
}


def main() -> None:
    for name in ("NOTION_TOKEN", "NOTION_DB_ID"):
        if not os.environ.get(name):
            sys.exit(f"Missing {name}")

    notion = Client(auth=os.environ["NOTION_TOKEN"])
    db_id = os.environ["NOTION_DB_ID"].split("?")[0].strip()

    db = notion.databases.retrieve(database_id=db_id)
    print(f"Database: {db['title'][0]['plain_text'] if db.get('title') else db_id}")

    sources = db.get("data_sources") or []
    if not sources:
        sys.exit("No data_sources on this database.")
    ds_id = sources[0]["id"]
    print(f"Data source: {sources[0].get('name', ds_id)} ({ds_id})\n")

    ds = notion.data_sources.retrieve(ds_id)
    props = ds.get("properties") or {}
    print(f"Properties ({len(props)}):")
    for name in sorted(props):
        ptype = props[name].get("type", "?")
        tag = ""
        if name in REQUIRED_PROPERTIES:
            tag = " [required]"
        elif name in OPTIONAL_PROPERTIES:
            tag = " [optional]"
        exp = EXPECTED_TYPES.get(name)
        if exp:
            ok = ptype in exp if isinstance(exp, tuple) else ptype == exp
            if not ok:
                want = " or ".join(exp) if isinstance(exp, tuple) else exp
                tag += f" — expected {want}, got {ptype}"
        print(f"  - {name}: {ptype}{tag}")

    missing = [n for n in REQUIRED_PROPERTIES if n not in props]
    if missing:
        print(f"\nMISSING required: {missing}")
        print("Add these in Notion or create a fresh board with setup_notion_db.py")
        sys.exit(1)

    print("\nSchema OK for jobhunt.")


if __name__ == "__main__":
    main()
