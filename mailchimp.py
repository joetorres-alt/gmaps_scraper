"""
Mailchimp integration — sync leads to an audience and optionally create a campaign.
Requires: MAILCHIMP_API_KEY and MAILCHIMP_LIST_ID environment variables (or pass directly).
"""

import hashlib
import os
import re
import requests
from models import Lead


def _client(api_key: str):
    """Return (base_url, headers) for the Mailchimp API."""
    # Data centre is the last part of the key e.g. "us21"
    dc = api_key.split("-")[-1]
    base = f"https://{dc}.api.mailchimp.com/3.0"
    headers = {"Authorization": f"apikey {api_key}"}
    return base, headers


def verify_api_key(api_key: str) -> tuple[bool, str]:
    """Check the API key is valid. Returns (ok, message)."""
    try:
        base, headers = _client(api_key)
        r = requests.get(f"{base}/ping", headers=headers, timeout=10)
        if r.status_code == 200:
            return True, "Connected to Mailchimp"
        return False, r.json().get("detail", "Invalid API key")
    except Exception as exc:
        return False, str(exc)


def get_audiences(api_key: str) -> list[dict]:
    """Return list of {id, name} for all audiences in the account."""
    try:
        base, headers = _client(api_key)
        r = requests.get(f"{base}/lists?count=100", headers=headers, timeout=10)
        lists = r.json().get("lists", [])
        return [{"id": l["id"], "name": l["name"]} for l in lists]
    except Exception:
        return []


def _subscriber_hash(email: str) -> str:
    return hashlib.md5(email.lower().encode()).hexdigest()


def _score_tag(score: int) -> str:
    if score >= 70:
        return "Hot Lead"
    if score >= 40:
        return "Warm Lead"
    return "Cold Lead"


def sync_leads(
    leads: list[Lead],
    api_key: str,
    list_id: str,
    log_fn=print,
) -> dict:
    """
    Upsert all leads with an email address into a Mailchimp audience.
    Returns summary dict.
    """
    base, headers = _client(api_key)
    synced, skipped, errors = 0, 0, 0

    eligible = [l for l in leads if l.email and "@" in l.email]
    log_fn(f"Syncing {len(eligible)} leads with emails to Mailchimp...")

    for lead in eligible:
        tags = [_score_tag(lead.score)]
        if lead.source:
            tags.append(lead.source.replace("_", " ").title())
        if lead.category:
            tags.append(lead.category[:50])

        merge_fields = {
            "FNAME": lead.name,
            "PHONE": lead.phone,
            "ADDRESS": lead.address,
            "WEBSITE": lead.website,
            "SCORE":   str(lead.score),
            "SOURCE":  lead.source,
        }

        payload = {
            "email_address": lead.email,
            "status_if_new": "subscribed",
            "merge_fields":  merge_fields,
            "tags":          tags,
        }

        url = f"{base}/lists/{list_id}/members/{_subscriber_hash(lead.email)}"
        try:
            r = requests.put(url, json=payload, headers=headers, timeout=10)
            if r.status_code in (200, 201):
                synced += 1
                log_fn(f"  ✓ {lead.email}")
            else:
                errors += 1
                log_fn(f"  ✗ {lead.email} — {r.json().get('detail', r.status_code)}")
        except Exception as exc:
            errors += 1
            log_fn(f"  ✗ {lead.email} — {exc}")

        skipped += (1 if lead not in eligible else 0)

    log_fn(f"Mailchimp sync done — {synced} synced, {errors} errors, {len(leads) - len(eligible)} skipped (no email)")
    return {"synced": synced, "errors": errors, "skipped": len(leads) - len(eligible)}


def create_campaign(
    api_key: str,
    list_id: str,
    subject: str,
    from_name: str,
    reply_to: str,
    body_html: str,
    log_fn=print,
) -> tuple[bool, str]:
    """
    Create a Mailchimp email campaign (saved as Draft — you send it from Mailchimp).
    Returns (success, campaign_url_or_error).
    """
    base, headers = _client(api_key)

    try:
        # 1. Create campaign
        campaign_payload = {
            "type": "regular",
            "recipients": {"list_id": list_id},
            "settings": {
                "subject_line": subject,
                "from_name":    from_name,
                "reply_to":     reply_to,
                "title":        subject,
            },
        }
        r = requests.post(f"{base}/campaigns", json=campaign_payload, headers=headers, timeout=10)
        if r.status_code != 200:
            return False, r.json().get("detail", "Failed to create campaign")

        campaign_id = r.json()["id"]
        log_fn(f"Campaign created: {campaign_id}")

        # 2. Set content
        content_payload = {"html": body_html}
        r2 = requests.put(
            f"{base}/campaigns/{campaign_id}/content",
            json=content_payload,
            headers=headers,
            timeout=10,
        )
        if r2.status_code != 200:
            return False, r2.json().get("detail", "Failed to set campaign content")

        campaign_url = f"https://us1.admin.mailchimp.com/campaigns/edit?id={campaign_id}"
        log_fn(f"Campaign ready as Draft → {campaign_url}")
        return True, campaign_url

    except Exception as exc:
        return False, str(exc)


def build_campaign_html(leads: list[Lead], subject: str) -> str:
    """Build a simple HTML email body listing all leads with cold emails."""
    rows = ""
    for lead in leads:
        if not lead.cold_email or lead.cold_email.startswith("["):
            continue
        rows += f"""
        <tr>
          <td style="padding:16px;border-bottom:1px solid #eee;">
            <strong>{lead.name}</strong><br>
            <small style="color:#666;">{lead.address}</small><br><br>
            <em style="color:#444;">{lead.cold_email}</em>
          </td>
        </tr>"""

    return f"""
    <html><body style="font-family:sans-serif;max-width:600px;margin:0 auto;">
      <h2 style="color:#1a1a2e;">{subject}</h2>
      <table width="100%" cellpadding="0" cellspacing="0">
        {rows or '<tr><td>No cold emails generated.</td></tr>'}
      </table>
    </body></html>"""
