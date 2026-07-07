"""One-time helper: create the jobhunt board with the correct schema.

Usage:
    NOTION_TOKEN=... python -m jobhunt.scripts.setup_notion_db <PARENT_PAGE_ID>

<PARENT_PAGE_ID> is any Notion page you've shared with your integration; the new
database is created inside it. Prints the database id to paste into NOTION_DB_ID.

You can also just build the database by hand in the Notion UI — this script only
saves you the clicking. Either way, remember to switch the DB's default view to
'Board' grouped by Status.
"""
from __future__ import annotations

import os
import sys

from notion_client import Client

SOURCES = ["indeed", "linkedin", "google", "visa_repo", "board"]
VISA = ["yes", "no", "unknown"]
STATUSES = [  # Notion 'status' groups; adjust colors/order in the UI afterward
    "New", "Reviewing", "Approved", "Applied",
    "Interviewing", "Offer", "Rejected", "Skipped",
]


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit("usage: python -m jobhunt.scripts.setup_notion_db <PARENT_PAGE_ID>")
    parent_page_id = sys.argv[1]
    notion = Client(auth=os.environ["NOTION_TOKEN"])

    props = {
        "Role": {"title": {}},
        "Company": {"rich_text": {}},
        "Location": {"rich_text": {}},
        "Country": {"rich_text": {}},
        "Source": {"select": {"options": [{"name": s} for s in SOURCES]}},
        "Fit Score": {"number": {"format": "number"}},
        "Why Fit": {"rich_text": {}},
        "Salary": {"rich_text": {}},
        "Remote": {"checkbox": {}},
        "Visa": {"select": {"options": [{"name": v} for v in VISA]}},
        "Date Posted": {"date": {}},
        "Date Found": {"created_time": {}},
        "Job URL": {"url": {}},
        # NOTE: a 'status' property with custom options often must be finished in
        # the UI; if the API rejects custom groups, create 'Status' as a Status
        # property manually and add the lanes listed in STATUSES.
        "Status": {"status": {}},
    }

    db = notion.databases.create(
        parent={"type": "page_id", "page_id": parent_page_id},
        title=[{"type": "text", "text": {"content": "Job Hunt"}}],
        initial_data_source={"properties": props},
    )
    print("Database created.")
    print("NOTION_DB_ID =", db["id"])
    print("\nNext: open it in Notion, switch the view to 'Board' grouped by Status,")
    print("and ensure these lanes exist:", ", ".join(STATUSES))


if __name__ == "__main__":
    main()
