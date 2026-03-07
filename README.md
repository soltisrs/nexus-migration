# Nexus Consulting Group — Monday.com Migration

A data migration and validation toolkit built for Nexus Consulting Group's move from Smartsheet to monday.com Work Management.

---

## Overview

Nexus tracked client engagements and deliverables in a single flat Smartsheet — one row per deliverable with engagement data repeated across every row. This project:

1. **Migrates** the flat CSV into two connected Monday.com boards (Engagements + Deliverables)
2. **Validates** the migration by comparing every field in the source CSV against what was loaded into Monday.com

---

## Project Structure

```
nexus_migration/
├── .env                        # API credentials (never committed)
├── .gitignore
├── README.md
├── requirements.txt
├── nexus_smartsheet_export.csv # Source data from Smartsheet
├── config.py                   # Board IDs, column IDs, status maps
├── utils.py                    # Shared helpers (API calls, date parsing, etc.)
├── migrate.py                  # Migration script
└── validate.py                 # Validation script
```

---

## Setup

**1. Clone the repo and install dependencies**
```bash
pip install -r requirements.txt
```

**2. Create your `.env` file**
```bash
cp .env.example .env
```
Then open `.env` and paste in your Monday.com API token:
```
MONDAY_API_TOKEN=your_token_here
```
You can find your token at: monday.com → Profile → Developers → My Access Tokens

**3. Add the source CSV**

Place `nexus_smartsheet_export.csv` in the project root. The file should be a direct export from Smartsheet with these columns:
`engagement_id, engagement_name, client, engagement_lead, engagement_start, engagement_end, budget, engagement_status, deliverable_id, deliverable_name, assignee, due_date, priority, deliverable_status, hours_estimated`

---

## Usage

**Run the migration**
```bash
python migrate.py
```

This will create 6 engagements and 27 deliverables in Monday.com and print a summary on completion. Each deliverable is linked to its parent engagement via a connect-boards column.

> ⚠️ The script does not check for existing items before creating — clear both Monday boards before re-running to avoid duplicates.

**Run the validation**
```bash
python validate.py
```

This queries Monday.com, compares every field against the CSV, and prints a categorised audit report.

---

## Validation Checks

The validation script covers everything Derek and Priya requested during the discovery call:

| Check | Description |
|---|---|
| Record counts | CSV item count matches Monday board count |
| Missing items | Any engagement or deliverable that didn't make it over |
| Field mismatches | Client, lead, budget, status, dates, assignee, hours, priority |
| Incomplete data | Items with blank required fields (no assignee, no due date, etc.) |
| Orphaned deliverables | Deliverables with no linked parent engagement |
| Extra items | Items on Monday that don't exist in the source CSV |

Example output when issues are found:
```
  RESULT: 3 issue(s) across 3 category(ies)

  !!  ORPHANED DELIVERABLES (NO ENGAGEMENT LINKED)  (1 item)
     * 'Current State Assessment' | Should be linked to: 'Digital Transformation Strategy'

  --  ENGAGEMENT - BUDGET  (1 item)
     * 'Digital Transformation Strategy' | CSV: $150,000  ->  Monday: $150,001

  --  ENGAGEMENT - STATUS  (1 item)
     * 'Digital Transformation Strategy' | Expected: 'Active'  ->  Monday: 'Not Started'
```

---

## Design Decisions & Assumptions

**Board structure**
The source CSV stored engagement data repeated on every deliverable row. Based on the discovery call, these were split into two separate boards — Engagements and Deliverables — connected via a board_relation column. This eliminates the manual deduplication Derek described spending hours on.

**Status normalisation**
The CSV contained inconsistent status values used interchangeably by different team members (e.g. `"In Progress"`, `"Active"`, and `"Working on it"` all meaning the same thing). These are mapped to clean, standardised Monday labels in `config.py`. Any unrecognised status defaults to `"Not Started"` for engagements and `"To Do"` for deliverables.

**Engagement deduplication**
Since each engagement appears once per deliverable row in the CSV, the migration script uses `engagement_id` as the deduplication key. An engagement is only created once regardless of how many deliverable rows reference it.

**Board relation API limitation**
Monday.com's standard GraphQL API returns empty string for `board_relation` column values even when links exist. The validation script handles this by using a separate typed GraphQL query (`... on BoardRelationValue`) to check engagement links — the only reliable way to read this data via the API.

---

## Configuration

All board IDs, column IDs, and status maps are centralised in `config.py`. If column IDs change or new status variants appear in future CSV exports, only `config.py` needs to be updated.

To find column IDs for a board, run:
```graphql
{
  boards(ids: YOUR_BOARD_ID) {
    columns { id title type }
  }
}
```
Status columns have `type: "color"` in the Monday.com API.

---

## Built With

- [Monday.com GraphQL API](https://developer.monday.com/api-reference/)
- Python 3
- `requests` — HTTP client for API calls
- `python-dotenv` — loads API token from `.env`
