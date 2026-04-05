"""
Export leads to CSV formats for HubSpot, Salesforce, Pipedrive,
and a polished HTML sales report for reps.
"""
import csv
import html
import os
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from models import Lead


# ── Generic CSV ────────────────────────────────────────────────────────────────

def export_csv(leads: list[Lead], path: str = "leads.csv") -> None:
    if not leads:
        print("No leads to export.")
        return
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(leads[0].__dataclass_fields__.keys()))
        writer.writeheader()
        writer.writerows(asdict(l) for l in leads)
    print(f"  Saved {len(leads)} leads → {Path(path).resolve()}")


# ── HubSpot ────────────────────────────────────────────────────────────────────

def export_hubspot(leads: list[Lead], path: str = "hubspot_import.csv") -> None:
    """HubSpot Contacts import format."""
    rows = []
    for l in leads:
        rows.append({
            "First Name": "",
            "Last Name": l.name,
            "Email": l.email,
            "Phone Number": l.phone,
            "Company Name": l.name,
            "Website URL": l.website,
            "Street Address": l.address,
            "City": l.city,
            "State/Region": l.state,
            "Lead Source": f"Web Scraper ({l.source})",
            "HubSpot Score": l.score,
            "Notes": l.score_reasons,
        })
    _write_csv(rows, path)
    print(f"  HubSpot import → {Path(path).resolve()}")


# ── Salesforce ─────────────────────────────────────────────────────────────────

def export_salesforce(leads: list[Lead], path: str = "salesforce_import.csv") -> None:
    """Salesforce Leads import format."""
    rows = []
    for l in leads:
        rows.append({
            "Last Name": l.name,
            "Company": l.name,
            "Phone": l.phone,
            "Email": l.email,
            "Website": l.website,
            "Street": l.address,
            "City": l.city,
            "State": l.state,
            "Lead Source": "Web",
            "Industry": l.category,
            "Rating": _sf_rating(l.score),
            "Description": l.score_reasons,
        })
    _write_csv(rows, path)
    print(f"  Salesforce import → {Path(path).resolve()}")


def _sf_rating(score: int) -> str:
    if score >= 70:
        return "Hot"
    if score >= 40:
        return "Warm"
    return "Cold"


# ── Pipedrive ──────────────────────────────────────────────────────────────────

def export_pipedrive(leads: list[Lead], path: str = "pipedrive_import.csv") -> None:
    """Pipedrive Organizations import format."""
    rows = []
    for l in leads:
        rows.append({
            "Organization Name": l.name,
            "Phone": l.phone,
            "Email": l.email,
            "Address": l.address,
            "Web": l.website,
            "Category": l.category,
            "Label": _sf_rating(l.score),
            "Note": l.score_reasons,
        })
    _write_csv(rows, path)
    print(f"  Pipedrive import → {Path(path).resolve()}")


def _write_csv(rows: list[dict], path: str) -> None:
    if not rows:
        return
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


# ── HTML Sales Report ──────────────────────────────────────────────────────────

def export_report(leads: list[Lead], path: str = "leads_report.html", title: str = "Sales Leads Report") -> None:
    """
    Generate a polished, printable HTML report for sales reps.
    Shows each lead as a card with all data and a colour-coded score badge.
    """
    if not leads:
        print("No leads to generate report for.")
        return

    now = datetime.now().strftime("%B %d, %Y  %I:%M %p")
    total = len(leads)
    with_phone = sum(1 for l in leads if l.phone)
    with_email = sum(1 for l in leads if l.email)
    with_website = sum(1 for l in leads if l.website)
    avg_score = round(sum(l.score for l in leads) / total, 1) if total else 0

    cards_html = "\n".join(_lead_card(l) for l in leads)

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{html.escape(title)}</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
          background: #f0f2f5; color: #1a1a2e; }}
  .header {{ background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
             color: white; padding: 40px 48px; }}
  .header h1 {{ font-size: 28px; font-weight: 700; letter-spacing: -0.5px; }}
  .header p {{ opacity: 0.7; margin-top: 6px; font-size: 14px; }}
  .stats {{ display: flex; gap: 20px; margin-top: 28px; flex-wrap: wrap; }}
  .stat {{ background: rgba(255,255,255,0.12); border-radius: 10px;
           padding: 14px 22px; min-width: 120px; }}
  .stat .num {{ font-size: 28px; font-weight: 700; }}
  .stat .lbl {{ font-size: 12px; opacity: 0.7; text-transform: uppercase;
                letter-spacing: 0.5px; margin-top: 2px; }}
  .container {{ max-width: 1100px; margin: 32px auto; padding: 0 24px; }}
  .section-title {{ font-size: 13px; font-weight: 600; text-transform: uppercase;
                    letter-spacing: 1px; color: #888; margin-bottom: 16px; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(340px, 1fr)); gap: 20px; }}
  .card {{ background: white; border-radius: 14px; padding: 22px 24px;
           box-shadow: 0 2px 12px rgba(0,0,0,0.07); position: relative;
           border-top: 4px solid #e2e8f0; transition: box-shadow 0.2s; }}
  .card:hover {{ box-shadow: 0 6px 24px rgba(0,0,0,0.12); }}
  .card.hot {{ border-top-color: #ef4444; }}
  .card.warm {{ border-top-color: #f59e0b; }}
  .card.cold {{ border-top-color: #3b82f6; }}
  .card-header {{ display: flex; justify-content: space-between; align-items: flex-start; }}
  .biz-name {{ font-size: 17px; font-weight: 700; color: #1a1a2e; line-height: 1.3; }}
  .category {{ font-size: 12px; color: #6b7280; margin-top: 3px; }}
  .badge {{ border-radius: 20px; padding: 4px 12px; font-size: 12px;
            font-weight: 700; white-space: nowrap; }}
  .badge.hot {{ background: #fef2f2; color: #dc2626; }}
  .badge.warm {{ background: #fffbeb; color: #d97706; }}
  .badge.cold {{ background: #eff6ff; color: #2563eb; }}
  .divider {{ height: 1px; background: #f1f5f9; margin: 14px 0; }}
  .info-row {{ display: flex; align-items: center; gap: 8px; margin-bottom: 8px;
               font-size: 13.5px; color: #374151; }}
  .info-row .icon {{ font-size: 15px; width: 20px; flex-shrink: 0; }}
  .info-row a {{ color: #2563eb; text-decoration: none; }}
  .info-row a:hover {{ text-decoration: underline; }}
  .tag-row {{ display: flex; flex-wrap: wrap; gap: 6px; margin-top: 10px; }}
  .tag {{ background: #f1f5f9; border-radius: 6px; padding: 3px 9px;
          font-size: 11px; color: #475569; font-weight: 500; }}
  .tag.verified {{ background: #f0fdf4; color: #15803d; }}
  .rating {{ display: flex; align-items: center; gap: 4px; }}
  .stars {{ color: #f59e0b; }}
  .cold-email {{ background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px;
                 padding: 12px 14px; font-size: 12.5px; color: #4b5563;
                 line-height: 1.6; margin-top: 12px; white-space: pre-wrap; }}
  .cold-email-label {{ font-size: 11px; font-weight: 600; text-transform: uppercase;
                       letter-spacing: 0.5px; color: #9ca3af; margin-bottom: 6px; }}
  .score-reasons {{ font-size: 11px; color: #9ca3af; margin-top: 8px;
                    line-height: 1.6; }}
  .source-pill {{ background: #f1f5f9; border-radius: 4px; padding: 2px 7px;
                  font-size: 10px; color: #64748b; text-transform: uppercase;
                  letter-spacing: 0.5px; font-weight: 600; }}
  @media print {{
    body {{ background: white; }}
    .card {{ break-inside: avoid; box-shadow: none; border: 1px solid #e2e8f0; }}
    .header {{ -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
  }}
</style>
</head>
<body>

<div class="header">
  <h1>{html.escape(title)}</h1>
  <p>Generated {html.escape(now)}</p>
  <div class="stats">
    <div class="stat"><div class="num">{total}</div><div class="lbl">Total Leads</div></div>
    <div class="stat"><div class="num">{with_phone}</div><div class="lbl">Have Phone</div></div>
    <div class="stat"><div class="num">{with_email}</div><div class="lbl">Have Email</div></div>
    <div class="stat"><div class="num">{with_website}</div><div class="lbl">Have Website</div></div>
    <div class="stat"><div class="num">{avg_score}</div><div class="lbl">Avg Score</div></div>
  </div>
</div>

<div class="container">
  <p class="section-title">Leads — sorted by priority score</p>
  <div class="grid">
{cards_html}
  </div>
</div>

</body>
</html>"""

    Path(path).write_text(html_content, encoding="utf-8")
    print(f"  HTML report → {Path(path).resolve()}")


def _lead_card(lead: Lead) -> str:
    score = lead.score
    if score >= 70:
        tier, label = "hot", "🔥 HOT"
    elif score >= 40:
        tier, label = "warm", "☀ WARM"
    else:
        tier, label = "cold", "❄ COLD"

    name_esc = html.escape(lead.name or "Unknown")
    cat_esc = html.escape(lead.category or "")
    addr_esc = html.escape(lead.address or "")
    phone_esc = html.escape(lead.phone or "")

    phone_row = f'<div class="info-row"><span class="icon">📞</span> {phone_esc}</div>' if phone_esc else ""

    web_row = ""
    if lead.website:
        web_esc = html.escape(lead.website)
        web_row = f'<div class="info-row"><span class="icon">🌐</span> <a href="{web_esc}" target="_blank">{web_esc[:45]}</a></div>'

    email_row = ""
    if lead.email:
        email_esc = html.escape(lead.email)
        email_row = f'<div class="info-row"><span class="icon">✉</span> <a href="mailto:{email_esc}">{email_esc}</a></div>'

    addr_row = f'<div class="info-row"><span class="icon">📍</span> {addr_esc}</div>' if addr_esc else ""

    rating_row = ""
    if lead.rating:
        stars = "★" * round(lead.rating) + "☆" * (5 - round(lead.rating))
        rating_row = f'<div class="info-row"><span class="icon">⭐</span> <span class="rating"><span class="stars">{stars}</span> {lead.rating} ({lead.review_count} reviews)</span></div>'

    # Tags
    tags = []
    if lead.email_verified:
        tags.append('<span class="tag verified">✓ Email Verified</span>')
    for platform, attr in [("Facebook", "social_facebook"), ("Instagram", "social_instagram"),
                            ("Twitter", "social_twitter"), ("LinkedIn", "linkedin_url")]:
        url = getattr(lead, attr)
        if url:
            tags.append(f'<a href="{html.escape(url)}" target="_blank" class="tag">{platform}</a>')
    if lead.tech_stack:
        for t in lead.tech_stack.split(",")[:3]:
            tags.append(f'<span class="tag">{html.escape(t.strip())}</span>')
    tag_html = f'<div class="tag-row">{"".join(tags)}</div>' if tags else ""

    source_pill = f'<span class="source-pill">{html.escape(lead.source)}</span>' if lead.source else ""

    cold_email_block = ""
    if lead.cold_email and not lead.cold_email.startswith("["):
        cold_email_block = f"""
    <div class="cold-email-label">Suggested Cold Email</div>
    <div class="cold-email">{html.escape(lead.cold_email)}</div>"""

    score_block = ""
    if lead.score_reasons:
        score_block = f'<div class="score-reasons">{html.escape(lead.score_reasons[:200])}</div>'

    return f"""    <div class="card {tier}">
      <div class="card-header">
        <div>
          <div class="biz-name">{name_esc}</div>
          <div class="category">{cat_esc}  {source_pill}</div>
        </div>
        <span class="badge {tier}">{label} {score}</span>
      </div>
      <div class="divider"></div>
      {addr_row}{phone_row}{email_row}{web_row}{rating_row}
      {tag_html}
      {score_block}
      {cold_email_block}
    </div>"""
