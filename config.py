# ---------------------------------------------------------------
# config.py — Shared configuration for migrate.py and validate.py
#
# All board IDs, column IDs, and status maps live here so they
# only need to be updated in one place. The API token is loaded
# separately from the .env file to keep credentials out of code.
# ---------------------------------------------------------------

# Monday.com board IDs
ENG_BOARD_ID   = "18402611530"
DELIV_BOARD_ID = "18402613812"

# Source data file
CSV_FILE = "nexus_smartsheet_export.csv"

# ---------------------------------------------------------------
# Engagement board column IDs
# To find/verify these: query { boards(ids: ENG_BOARD_ID) { columns { id title type } } }
# ---------------------------------------------------------------
ENG_LEAD_COL     = "text_mm14eh70"
ENG_CLIENT_COL   = "text_mm14kngb"
ENG_BUDGET_COL   = "numeric_mm14g4jr"
ENG_TIMELINE_COL = "timerange_mm149n7c"
ENG_STATUS_COL   = "status"

# ---------------------------------------------------------------
# Deliverables board column IDs
# To find/verify these: query { boards(ids: DELIV_BOARD_ID) { columns { id title type } } }
# ---------------------------------------------------------------
DELIV_ASSIGNEE_COL = "text_mm14cg1a"
DELIV_STATUS_COL   = "status"
DELIV_DATE_COL     = "date4"
DELIV_HOURS_COL    = "numeric_mm14c1ev"
DELIV_PRIORITY_COL = "color_mm149qgd"
DELIV_LINK_COL     = "board_relation_mm14td6p"  # connects deliverable to parent engagement

# ---------------------------------------------------------------
# Status translation maps
#
# The source CSV has inconsistent status values (e.g. "In Progress"
# and "Working on it" meaning the same thing). These maps normalise
# all variants into the clean labels used in Monday.com.
# If new variants appear in future CSV exports, add them here.
# ---------------------------------------------------------------
ENG_STATUS_MAP = {
    "in progress":   "Active",
    "working on it": "Active",
    "active":        "Active",
    "complete":      "Complete",
    "done":          "Complete",
    "on hold":       "On Hold",
    "not started":   "Not Started",
}

DELIV_STATUS_MAP = {
    "in progress":   "In Progress",
    "working on it": "In Progress",
    "active":        "In Progress",
    "complete":      "Done",
    "done":          "Done",
    "to do":         "To Do",
    "not started":   "To Do",
    "in review":     "In Review",
}