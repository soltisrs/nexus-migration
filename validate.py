# ---------------------------------------------------------------
# validate.py — Nexus Migration Validation
#
# Compares the source CSV against what was loaded into Monday.com
# and prints a categorised audit report highlighting any issues.
#
# Checks performed:
#   - Record counts match (engagements + deliverables)
#   - All items from CSV exist on Monday
#   - All field values match (client, lead, budget, status, dates, etc.)
#   - No deliverables are missing key data (assignee, due date, etc.)
#   - No deliverables are orphaned (missing engagement link)
#   - No extra items exist on Monday that weren't in the CSV
#
# Run: python validate.py
# Requires: .env file with MONDAY_API_TOKEN set
# ---------------------------------------------------------------

import csv
from collections import defaultdict

from config import (
    ENG_BOARD_ID, DELIV_BOARD_ID, CSV_FILE,
    ENG_LEAD_COL, ENG_CLIENT_COL, ENG_BUDGET_COL, ENG_TIMELINE_COL, ENG_STATUS_COL,
    DELIV_ASSIGNEE_COL, DELIV_STATUS_COL, DELIV_DATE_COL, DELIV_HOURS_COL, DELIV_PRIORITY_COL,
    ENG_STATUS_MAP, DELIV_STATUS_MAP,
)
from utils import fetch_board_data, fetch_linked_deliverables, to_iso, safe_float


def run_validation():
    """Query Monday.com, compare against the source CSV, and print a full audit report."""
    print("\n" + "=" * 62)
    print("  NEXUS MIGRATION VALIDATION - STARTING AUDIT")
    print("=" * 62)

    monday_eng   = fetch_board_data(ENG_BOARD_ID)
    monday_deliv = fetch_board_data(DELIV_BOARD_ID)
    linked_deliv = fetch_linked_deliverables()

    issues              = defaultdict(list)
    checked_engagements = set()
    csv_eng_names       = set()
    csv_deliv_names     = set()

    with open(CSV_FILE, mode="r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    for row in rows:
        e_name = row["engagement_name"].strip()
        d_name = row["deliverable_name"].strip()
        csv_eng_names.add(e_name)
        csv_deliv_names.add(d_name)

        # -- ENGAGEMENT CHECKS (run once per unique engagement) -----------
        if e_name not in checked_engagements:
            checked_engagements.add(e_name)

            if e_name not in monday_eng:
                issues["Missing Engagements"].append(f"'{e_name}'")
            else:
                m = monday_eng[e_name]

                # Helper to log a field mismatch for this engagement
                def eng_check(label, csv_val, mon_val):
                    if csv_val != mon_val:
                        issues[f"Engagement - {label}"].append(
                            f"'{e_name}' | CSV: '{csv_val}'  ->  Monday: '{mon_val}'"
                        )

                eng_check("Client",
                    row["client"].strip(),
                    (m.get(ENG_CLIENT_COL) or "").strip())

                eng_check("Lead",
                    row["engagement_lead"].strip(),
                    (m.get(ENG_LEAD_COL) or "").strip())

                # Budget compared as floats to ignore formatting differences ($150,000 vs 150000)
                csv_budget = safe_float(row["budget"])
                mon_budget = safe_float(m.get(ENG_BUDGET_COL))
                if csv_budget != mon_budget:
                    issues["Engagement - Budget"].append(
                        f"'{e_name}' | CSV: ${csv_budget:,.0f}  ->  Monday: ${mon_budget:,.0f}"
                    )

                # Status normalised through map before comparing (handles "In Progress" -> "Active" etc.)
                expected = ENG_STATUS_MAP.get(row["engagement_status"].strip().lower(), "Not Started")
                actual   = (m.get(ENG_STATUS_COL) or "").strip()
                if expected.lower() != actual.lower():
                    issues["Engagement - Status"].append(
                        f"'{e_name}' | Expected: '{expected}'  ->  Monday: '{actual}'"
                    )

                # Timeline: verify start date is present in the timerange string
                csv_start = to_iso(row["engagement_start"])
                mon_tl    = (m.get(ENG_TIMELINE_COL) or "")
                if csv_start and csv_start not in mon_tl:
                    issues["Engagement - Start Date"].append(
                        f"'{e_name}' | CSV: '{csv_start}'  ->  Monday: '{mon_tl}'"
                    )

                # Flag engagements missing key fields entirely on Monday
                missing = [
                    label for label, col in [("lead", ENG_LEAD_COL), ("client", ENG_CLIENT_COL)]
                    if not (m.get(col) or "").strip()
                ]
                if safe_float(m.get(ENG_BUDGET_COL)) == 0:
                    missing.append("budget")
                if missing:
                    issues["Incomplete Engagements (Missing Data)"].append(
                        f"'{e_name}' | Missing: {', '.join(missing)}"
                    )

        # -- DELIVERABLE CHECKS -------------------------------------------
        if d_name not in monday_deliv:
            issues["Missing Deliverables"].append(f"'{d_name}'")
        else:
            m = monday_deliv[d_name]

            # Helper to log a field mismatch for this deliverable
            def deliv_check(label, csv_val, mon_val):
                if csv_val != mon_val:
                    issues[f"Deliverable - {label}"].append(
                        f"'{d_name}' | CSV: '{csv_val}'  ->  Monday: '{mon_val}'"
                    )

            deliv_check("Assignee",
                row["assignee"].strip(),
                (m.get(DELIV_ASSIGNEE_COL) or "").strip())

            deliv_check("Priority",
                row["priority"].strip(),
                (m.get(DELIV_PRIORITY_COL) or "").strip())

            deliv_check("Due Date",
                to_iso(row["due_date"]),
                (m.get(DELIV_DATE_COL) or "").strip())

            # Hours compared as floats to avoid string formatting mismatches
            csv_h = safe_float(row["hours_estimated"])
            mon_h = safe_float(m.get(DELIV_HOURS_COL))
            if csv_h != mon_h:
                issues["Deliverable - Hours"].append(
                    f"'{d_name}' | CSV: {csv_h:.0f}h  ->  Monday: {mon_h:.0f}h"
                )

            # Status normalised through map before comparing
            expected = DELIV_STATUS_MAP.get(row["deliverable_status"].strip().lower(), "To Do")
            actual   = (m.get(DELIV_STATUS_COL) or "").strip()
            if expected.lower() != actual.lower():
                issues["Deliverable - Status"].append(
                    f"'{d_name}' | Expected: '{expected}'  ->  Monday: '{actual}'"
                )

            # Flag deliverables missing key fields entirely on Monday
            missing = []
            if not (m.get(DELIV_ASSIGNEE_COL) or "").strip():
                missing.append("assignee")
            if not (m.get(DELIV_DATE_COL) or "").strip():
                missing.append("due date")
            if not (m.get(DELIV_STATUS_COL) or "").strip():
                missing.append("status")
            if safe_float(m.get(DELIV_HOURS_COL)) == 0:
                missing.append("estimated hours")
            if missing:
                issues["Incomplete Deliverables (Missing Data)"].append(
                    f"'{d_name}' | Missing: {', '.join(missing)}"
                )

            # Flag deliverables with no linked engagement
            if d_name not in linked_deliv:
                issues["Orphaned Deliverables (No Engagement Linked)"].append(
                    f"'{d_name}' | Should be linked to: '{e_name}'"
                )

    # Flag items that exist on Monday but weren't in the CSV at all
    for name in set(monday_eng.keys()) - csv_eng_names:
        issues["Extra Items on Monday (not in CSV)"].append(f"Engagement: '{name}'")
    for name in set(monday_deliv.keys()) - csv_deliv_names:
        issues["Extra Items on Monday (not in CSV)"].append(f"Deliverable: '{name}'")

    # -- REPORT -----------------------------------------------------------
    total_issues = sum(len(v) for v in issues.values())

    print(f"\n  RECORD COUNTS")
    print(f"  {'-' * 40}")
    print(f"  CSV    Engagements : {len(csv_eng_names)}")
    print(f"  CSV    Deliverables: {len(rows)}")
    print(f"  Monday Engagements : {len(monday_eng)}")
    print(f"  Monday Deliverables: {len(monday_deliv)}")

    # Count comparison between Smartsheet and Monday.com
    if len(csv_eng_names) != len(monday_eng):
        print(f"\n  !! Engagement count mismatch  : {len(csv_eng_names)} CSV vs {len(monday_eng)} Monday")
    if len(rows) != len(monday_deliv):
        print(f"  !! Deliverable count mismatch : {len(rows)} CSV vs {len(monday_deliv)} Monday")

    print(f"\n{'=' * 62}")

    if not total_issues:
        print("  RESULT: 100% DATA INTEGRITY - ALL CHECKS PASSED")
    else:
        print(f"  RESULT: {total_issues} issue(s) across {len(issues)} category(ies)")
        print(f"{'=' * 62}\n")

        # Critical issues (missing/orphaned/incomplete) print first, field mismatches after
        priority_order = [
            "Missing Engagements",
            "Missing Deliverables",
            "Orphaned Deliverables (No Engagement Linked)",
            "Incomplete Engagements (Missing Data)",
            "Incomplete Deliverables (Missing Data)",
        ]
        for category in priority_order + [k for k in issues if k not in priority_order]:
            if category not in issues:
                continue
            msgs = issues[category]
            icon = "!!" if any(w in category for w in ["Missing", "Orphaned", "Incomplete"]) else "--"
            print(f"  {icon}  {category.upper()}  ({len(msgs)} item{'s' if len(msgs) != 1 else ''})")
            print(f"  {'-' * 58}")
            for msg in msgs:
                print(f"     * {msg}")
            print()

    print("=" * 62)
    print("  Audit complete.\n")


if __name__ == "__main__":
    run_validation()
