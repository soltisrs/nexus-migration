# ---------------------------------------------------------------
# utils.py — Shared helper functions for migrate.py and validate.py
# ---------------------------------------------------------------

import os
import requests
from dotenv import load_dotenv
from config import ENG_BOARD_ID, DELIV_BOARD_ID, DELIV_LINK_COL

# Load API token from .env and build the auth header used by all requests
load_dotenv()
API_URL = "https://api.monday.com/v2"
HEADERS = {
    "Authorization": os.getenv("MONDAY_API_TOKEN"),
    "Content-Type": "application/json",
}


def to_iso(date_str):
    """Convert MM/DD/YYYY to YYYY-MM-DD. Returns None if blank or malformed."""
    if not date_str or "/" not in date_str.strip():
        return None
    try:
        mm, dd, yyyy = date_str.strip().split("/")
        return f"{yyyy}-{mm.zfill(2)}-{dd.zfill(2)}"
    except ValueError:
        print(f"  WARNING: Could not parse date '{date_str}' - skipping")
        return None


def safe_float(value, fallback=0.0):
    """Parse a numeric string, stripping $ and commas. Returns fallback on failure."""
    try:
        return float(str(value).replace("$", "").replace(",", "").strip())
    except (ValueError, TypeError):
        return fallback


def clean_budget(value):
    """Strip $ and commas from a budget string so it can be sent as a numeric value."""
    return str(value).replace("$", "").replace(",", "").strip()


def run_query(query, variables=None):
    """Execute a GraphQL mutation or query against the Monday API.
    Returns the parsed JSON response, or an empty dict on failure."""
    try:
        res = requests.post(API_URL, json={"query": query, "variables": variables}, headers=HEADERS)
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        print(f"  ERROR: API request failed: {e}")
        return {}


def fetch_board_data(board_id):
    """Fetch all items from a Monday board.
    Returns a dict keyed by item name mapping to {column_id: text_value}.
    Note: board_relation columns always return empty text — use
    fetch_linked_deliverables() to check engagement connections instead."""
    query = """
    {
        boards(ids: %s) {
            items_page(limit: 500) {
                items {
                    name
                    column_values { id text }
                }
            }
        }
    }
    """ % board_id
    try:
        res = requests.post(API_URL, json={"query": query}, headers=HEADERS)
        res.raise_for_status()
        items = res.json()["data"]["boards"][0]["items_page"]["items"]
        return {
            item["name"].strip(): {cv["id"]: (cv["text"] or "") for cv in item["column_values"]}
            for item in items
        }
    except Exception as e:
        print(f"  WARNING: API fetch failed for board {board_id}: {e}")
        return {}


def fetch_linked_deliverables():
    """Return a set of deliverable names that have at least one linked engagement.
    Uses a typed GraphQL inline fragment (... on BoardRelationValue) because
    board_relation columns always return empty string via standard text/value fields.
    This is a Monday API limitation — the typed query is the only way to read links."""
    query = """
    {
        boards(ids: %s) {
            items_page(limit: 500) {
                items {
                    name
                    column_values {
                        id
                        ... on BoardRelationValue {
                            linked_items { id }
                        }
                    }
                }
            }
        }
    }
    """ % DELIV_BOARD_ID
    try:
        res = requests.post(API_URL, json={"query": query}, headers=HEADERS)
        res.raise_for_status()
        items = res.json()["data"]["boards"][0]["items_page"]["items"]
        return {
            item["name"].strip()
            for item in items
            for cv in item["column_values"]
            if cv.get("id") == DELIV_LINK_COL and cv.get("linked_items")
        }
    except Exception as e:
        print(f"  WARNING: Could not fetch linked deliverables: {e}")
        return set()
