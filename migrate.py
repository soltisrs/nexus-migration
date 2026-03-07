# ---------------------------------------------------------------
# migrate.py — Nexus Smartsheet -> Monday.com Data Migration
#
# Reads nexus_smartsheet_export.csv and creates:
#   - One item per unique engagement on the Engagements board
#   - One item per deliverable on the Deliverables board
#   - A board_relation link connecting each deliverable to its parent engagement
#
# Run: python migrate.py
# Requires: .env file with MONDAY_API_TOKEN set
# ---------------------------------------------------------------

import csv
import json
import time

from config import (
    ENG_BOARD_ID, DELIV_BOARD_ID, CSV_FILE,
    ENG_LEAD_COL, ENG_CLIENT_COL, ENG_BUDGET_COL, ENG_TIMELINE_COL, ENG_STATUS_COL,
    DELIV_ASSIGNEE_COL, DELIV_STATUS_COL, DELIV_DATE_COL, DELIV_HOURS_COL,
    DELIV_PRIORITY_COL, DELIV_LINK_COL,
    ENG_STATUS_MAP, DELIV_STATUS_MAP,
)
from utils import run_query, to_iso, clean_budget

# GraphQL mutation reused for both engagements and deliverables
CREATE_ITEM = """
    mutation ($board: ID!, $name: String!, $values: JSON!) {
        create_item(board_id: $board, item_name: $name, column_values: $values) {
            id
        }
    }
"""


def migrate_data():
    """Read the CSV and migrate all engagements and deliverables to Monday.com.
    Engagements are deduplicated by engagement_id — if the same engagement appears
    across multiple rows (one per deliverable), it is only created once."""

    # Maps engagement_id (e.g. ENG-001) -> Monday item ID
    # Built as we go to link deliverables to the correct parent
    engagement_id_map = {}

    eng_created   = 0
    deliv_created = 0
    errors        = []

    print("\n" + "=" * 60)
    print("  NEXUS DATA MIGRATION - STARTING")
    print("=" * 60)

    with open(CSV_FILE, mode="r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    print(f"  Loaded {len(rows)} rows from {CSV_FILE}\n")

    for i, row in enumerate(rows, start=1):
        eng_id   = row["engagement_id"].strip()
        eng_name = row["engagement_name"].strip()

        # -- STEP 1: CREATE ENGAGEMENT (once per unique engagement_id) ----
        if eng_id not in engagement_id_map:
            print(f"[{i}/{len(rows)}] Creating engagement: {eng_name} ({eng_id})")

            start_iso = to_iso(row["engagement_start"])
            end_iso   = to_iso(row["engagement_end"])

            eng_vals = {
                ENG_LEAD_COL:   row["engagement_lead"].strip(),
                ENG_CLIENT_COL: row["client"].strip(),
                ENG_BUDGET_COL: clean_budget(row["budget"]),
                ENG_STATUS_COL: {"label": ENG_STATUS_MAP.get(row["engagement_status"].strip().lower(), "Not Started")},
            }

            # Only set timeline if both dates parsed successfully
            if start_iso and end_iso:
                eng_vals[ENG_TIMELINE_COL] = {"from": start_iso, "to": end_iso}
            else:
                print(f"  WARNING: Missing dates for '{eng_name}' - timeline skipped")

            result = run_query(CREATE_ITEM, {"board": ENG_BOARD_ID, "name": eng_name, "values": json.dumps(eng_vals)})

            if result.get("errors") or not result.get("data"):
                msg = f"Failed to create engagement '{eng_name}': {result.get('errors', 'No data returned')}"
                print(f"  ERROR: {msg}")
                errors.append(msg)
                engagement_id_map[eng_id] = None  # mark as failed so deliverables are skipped
                time.sleep(1)
                continue

            monday_eng_id = result["data"]["create_item"]["id"]
            engagement_id_map[eng_id] = monday_eng_id
            eng_created += 1
            time.sleep(0.5)

        else:
            monday_eng_id = engagement_id_map[eng_id]

        # Skip deliverables whose parent engagement failed to create
        if monday_eng_id is None:
            print(f"  SKIPPING deliverable '{row['deliverable_name'].strip()}' - parent engagement failed")
            continue

        # -- STEP 2: CREATE DELIVERABLE -----------------------------------
        deliv_name = row["deliverable_name"].strip()
        print(f"  └─ Adding deliverable: {deliv_name}")

        due_iso = to_iso(row["due_date"])

        deliv_vals = {
            DELIV_ASSIGNEE_COL: row["assignee"].strip(),
            DELIV_STATUS_COL:   {"label": DELIV_STATUS_MAP.get(row["deliverable_status"].strip().lower(), "To Do")},
            DELIV_HOURS_COL:    row["hours_estimated"].strip(),
            DELIV_PRIORITY_COL: row["priority"].strip(),
            DELIV_LINK_COL:     {"item_ids": [int(monday_eng_id)]},  # links to parent engagement
        }

        # Only set due date if it parsed successfully
        if due_iso:
            deliv_vals[DELIV_DATE_COL] = {"date": due_iso}
        else:
            print(f"  WARNING: Missing due date for '{deliv_name}' - date skipped")

        result = run_query(CREATE_ITEM, {"board": DELIV_BOARD_ID, "name": deliv_name, "values": json.dumps(deliv_vals)})

        if result.get("errors") or not result.get("data"):
            msg = f"Failed to create deliverable '{deliv_name}': {result.get('errors', 'No data returned')}"
            print(f"  ERROR: {msg}")
            errors.append(msg)
        else:
            deliv_created += 1

        time.sleep(0.5)

    # -- SUMMARY ----------------------------------------------------------
    print("\n" + "=" * 60)
    print("  MIGRATION COMPLETE")
    print("=" * 60)
    print(f"  Engagements created : {eng_created}")
    print(f"  Deliverables created: {deliv_created}")

    if errors:
        print(f"\n  {len(errors)} error(s) encountered:")
        for e in errors:
            print(f"    * {e}")
        print("\n  Review errors above and re-run for any failed items.")
    else:
        print("\n  No errors. All items migrated successfully.")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    migrate_data()