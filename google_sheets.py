"""
Google Sheets integration — append leads directly to a spreadsheet.
Uses a Google Service Account JSON key for authentication.
"""

import json
from dataclasses import asdict
from models import Lead

import gspread
from google.oauth2.service_account import Credentials


SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

HEADERS = [
    "Name", "Category", "Address", "City", "State",
    "Phone", "Website", "Email", "Email Verified",
    "Rating", "Reviews", "Source",
    "Facebook", "Instagram", "Twitter", "LinkedIn",
    "Tech Stack", "Score", "Score Reasons", "Cold Email",
]


def _get_client(service_account_json: dict):
    creds = Credentials.from_service_account_info(service_account_json, scopes=SCOPES)
    return gspread.authorize(creds)


def verify_connection(service_account_json: dict, sheet_url: str) -> tuple[bool, str]:
    """Check the credentials and sheet are accessible. Returns (ok, message)."""
    try:
        client = _get_client(service_account_json)
        sheet = client.open_by_url(sheet_url)
        return True, f"Connected to: {sheet.title}"
    except gspread.exceptions.APIError as e:
        return False, f"API error: {e}"
    except Exception as e:
        return False, str(e)


def sync_leads(
    leads: list[Lead],
    service_account_json: dict,
    sheet_url: str,
    worksheet_name: str = "Leads",
    log_fn=print,
) -> dict:
    """
    Append all leads to the Google Sheet.
    Creates the worksheet if it doesn't exist.
    Adds a header row if the sheet is empty.
    Returns summary dict.
    """
    try:
        client = _get_client(service_account_json)
        spreadsheet = client.open_by_url(sheet_url)
        log_fn(f"Connected to sheet: {spreadsheet.title}")

        # Get or create worksheet
        try:
            ws = spreadsheet.worksheet(worksheet_name)
            log_fn(f"Using worksheet: {worksheet_name}")
        except gspread.exceptions.WorksheetNotFound:
            ws = spreadsheet.add_worksheet(title=worksheet_name, rows=1000, cols=len(HEADERS))
            log_fn(f"Created worksheet: {worksheet_name}")

        # Add header row if sheet is empty
        existing = ws.get_all_values()
        if not existing:
            ws.append_row(HEADERS)
            log_fn("Added header row")

        # Build rows
        rows = []
        for lead in leads:
            rows.append([
                lead.name,
                lead.category,
                lead.address,
                lead.city,
                lead.state,
                lead.phone,
                lead.website,
                lead.email,
                "Yes" if lead.email_verified else "No",
                lead.rating,
                lead.review_count,
                lead.source,
                lead.social_facebook,
                lead.social_instagram,
                lead.social_twitter,
                lead.linkedin_url,
                lead.tech_stack,
                lead.score,
                lead.score_reasons[:200] if lead.score_reasons else "",
                lead.cold_email[:500] if lead.cold_email and not lead.cold_email.startswith("[") else "",
            ])

        # Batch append
        if rows:
            ws.append_rows(rows, value_input_option="RAW")
            log_fn(f"Appended {len(rows)} leads to Google Sheets")

        return {"synced": len(rows), "sheet": spreadsheet.title, "worksheet": worksheet_name}

    except Exception as exc:
        log_fn(f"Google Sheets error: {exc}")
        return {"synced": 0, "error": str(exc)}
