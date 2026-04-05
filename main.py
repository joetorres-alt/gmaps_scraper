#!/usr/bin/env python3
"""
Sales Lead Generator Pro
Scrape → Enrich → Score → Generate Emails → Export Report
"""

import asyncio
import csv
import os
import sys
import zipfile
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from models import Lead
from sources import GoogleMapsScraper, YelpScraper, YellowPagesScraper
from enrichment import verify_email, find_socials, detect_tech_stack, find_linkedin
from intelligence.lead_scorer import score_all
from intelligence.deduplicator import deduplicate
from outreach.email_generator import generate_all_emails
from outreach.crm_export import export_csv, export_hubspot, export_salesforce, export_pipedrive, export_report


# ── Helpers ────────────────────────────────────────────────────────────────────

def p(msg: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    val = input(f"{msg}{suffix}: ").strip()
    return val if val else default


def yn(msg: str, default: bool = True) -> bool:
    d = "Y/n" if default else "y/N"
    val = input(f"{msg} ({d}): ").strip().lower()
    if val == "":
        return default
    return val == "y"


def banner(text: str) -> None:
    print(f"\n{'─' * 55}")
    print(f"  {text}")
    print(f"{'─' * 55}")


def load_leads_from_csv(path: str) -> list[Lead]:
    leads = []
    try:
        with open(path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                lead = Lead()
                for key, val in row.items():
                    if hasattr(lead, key):
                        field_type = lead.__dataclass_fields__[key].type
                        if field_type in ("bool", bool):
                            setattr(lead, key, val.lower() in ("true", "1", "yes"))
                        elif field_type in ("int", int):
                            setattr(lead, key, int(val) if val.isdigit() else 0)
                        elif field_type in ("float", float):
                            try:
                                setattr(lead, key, float(val))
                            except ValueError:
                                pass
                        else:
                            setattr(lead, key, val)
                leads.append(lead)
    except FileNotFoundError:
        print(f"  File not found: {path}")
    return leads


# ── Step runners ───────────────────────────────────────────────────────────────

async def run_scraping(keyword: str, location: str, max_results: int, sources: list[str], headless: bool) -> list[Lead]:
    all_leads: list[Lead] = []

    if "google" in sources:
        banner("Scraping Google Maps")
        leads = await GoogleMapsScraper(headless=headless).scrape(keyword, location, max_results)
        all_leads.extend(leads)

    if "yelp" in sources:
        banner("Scraping Yelp")
        leads = await YelpScraper(headless=headless).scrape(keyword, location, max_results)
        all_leads.extend(leads)

    if "yellowpages" in sources:
        banner("Scraping Yellow Pages")
        leads = await YellowPagesScraper(headless=headless).scrape(keyword, location, max_results)
        all_leads.extend(leads)

    return all_leads


def run_enrichment(leads: list[Lead], options: dict) -> list[Lead]:
    total = len(leads)
    for idx, lead in enumerate(leads, 1):
        print(f"  [{idx}/{total}] Enriching: {lead.name[:45]}")

        if options.get("social") and lead.website:
            socials = find_socials(lead.website)
            lead.social_facebook = socials["facebook"]
            lead.social_instagram = socials["instagram"]
            lead.social_twitter = socials["twitter"]
            if not lead.linkedin_url:
                lead.linkedin_url = socials["linkedin"]

        if options.get("tech") and lead.website:
            stack = detect_tech_stack(lead.website)
            lead.tech_stack = ", ".join(stack)

        if options.get("linkedin") and not lead.linkedin_url:
            lead.linkedin_url = find_linkedin(lead.name, lead.city)

        if options.get("verify") and lead.email:
            lead.email_verified = verify_email(lead.email)

    return leads


# ── Main menu ──────────────────────────────────────────────────────────────────

async def main() -> None:
    print("=" * 55)
    print("   Sales Lead Generator Pro")
    print("=" * 55)
    print("""
  1. Full pipeline  (scrape → enrich → score → export)
  2. Scrape only
  3. Enrich existing CSV
  4. Generate cold emails (requires Anthropic API key)
  5. Export / Report from existing CSV
  0. Exit
""")
    choice = p("Choose an option", "1")

    if choice == "0":
        sys.exit(0)

    leads: list[Lead] = []

    # ── Option 1 & 2: Scraping ─────────────────────────────────────────────────
    if choice in ("1", "2"):
        keyword = p("Search keyword (e.g. 'plumbers')")
        location = p("Location (e.g. 'Austin TX')")
        max_results = int(p("Max results per source", "30"))

        print("\nSources to scrape:")
        use_google = yn("  Google Maps", True)
        use_yelp = yn("  Yelp", True)
        use_yp = yn("  Yellow Pages", True)

        sources = []
        if use_google:
            sources.append("google")
        if use_yelp:
            sources.append("yelp")
        if use_yp:
            sources.append("yellowpages")

        if not sources:
            print("No sources selected. Exiting.")
            sys.exit(1)

        headless = yn("Run headless (no browser window)", True)

        banner("Scraping Leads")
        leads = await run_scraping(keyword, location, max_results, sources, headless)
        print(f"\n  Total scraped: {len(leads)}")

        banner("Deduplicating")
        leads, removed = deduplicate(leads)
        print(f"  Removed {removed} duplicate(s) → {len(leads)} unique leads")

    # ── Option 3 & loading CSV for options 4/5 ────────────────────────────────
    if choice in ("3", "4", "5"):
        csv_path = p("Path to existing leads CSV", "leads.csv")
        leads = load_leads_from_csv(csv_path)
        if not leads:
            print("No leads loaded. Exiting.")
            sys.exit(1)
        print(f"  Loaded {len(leads)} leads from {csv_path}")

    # ── Enrichment ─────────────────────────────────────────────────────────────
    if choice in ("1", "3"):
        banner("Enrichment Options")
        options = {
            "social":  yn("  Find social media links (Facebook, Instagram, etc.)", True),
            "tech":    yn("  Detect website tech stack", True),
            "linkedin": yn("  Search for LinkedIn company pages", False),
            "verify":  yn("  Verify email addresses (DNS check)", True),
        }
        if any(options.values()):
            banner("Enriching Leads")
            leads = run_enrichment(leads, options)

    # ── Scoring ────────────────────────────────────────────────────────────────
    if choice in ("1", "3"):
        banner("Scoring & Ranking Leads")
        leads = score_all(leads)
        hot = sum(1 for l in leads if l.score >= 70)
        warm = sum(1 for l in leads if 40 <= l.score < 70)
        cold = sum(1 for l in leads if l.score < 40)
        print(f"  🔥 Hot (70+): {hot}   ☀ Warm (40-69): {warm}   ❄ Cold (<40): {cold}")

    # ── Cold email generation ─────────────────────────────────────────────────
    if choice in ("1", "4"):
        generate = yn("\nGenerate AI cold emails? (requires ANTHROPIC_API_KEY)", choice == "4")
        if generate:
            if not os.environ.get("ANTHROPIC_API_KEY"):
                api_key = p("  Enter your Anthropic API key (or press Enter to skip)", "")
                if api_key:
                    os.environ["ANTHROPIC_API_KEY"] = api_key
                else:
                    print("  Skipping email generation.")
                    generate = False

        if generate:
            your_service = p("  Describe your product/service in 1-2 sentences",
                             "digital marketing services for local businesses")
            sender_name = p("  Your name (for email sign-off)", "the team")
            banner("Generating Cold Emails")
            leads = generate_all_emails(leads, your_service, sender_name)

    # ── Export ─────────────────────────────────────────────────────────────────
    if choice in ("1", "2", "3", "4", "5"):
        banner("Export")
        base = p("Output file base name (no extension)", "leads")

        export_csv(leads, f"{base}.csv")

        if yn("  Export HubSpot import CSV", False):
            export_hubspot(leads, f"{base}_hubspot.csv")

        if yn("  Export Salesforce import CSV", False):
            export_salesforce(leads, f"{base}_salesforce.csv")

        if yn("  Export Pipedrive import CSV", False):
            export_pipedrive(leads, f"{base}_pipedrive.csv")

        report_title = p("  Report title", f"Sales Leads — {base}")
        export_report(leads, f"{base}_report.html", title=report_title)

        # ── Zip all output files ───────────────────────────────────────────────
        zip_name = f"{base}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
        output_files = [
            f for f in [
                f"{base}.csv",
                f"{base}_hubspot.csv",
                f"{base}_salesforce.csv",
                f"{base}_pipedrive.csv",
                f"{base}_report.html",
            ]
            if Path(f).exists()
        ]
        with zipfile.ZipFile(zip_name, "w", zipfile.ZIP_DEFLATED) as zf:
            for file in output_files:
                zf.write(file)
        print(f"\n  Zipped {len(output_files)} file(s) → {Path(zip_name).resolve()}")

    # ── Summary ────────────────────────────────────────────────────────────────
    banner("Done")
    print(f"  Total leads    : {len(leads)}")
    print(f"  With phone     : {sum(1 for l in leads if l.phone)}")
    print(f"  With website   : {sum(1 for l in leads if l.website)}")
    print(f"  With email     : {sum(1 for l in leads if l.email)}")
    print(f"  Email verified : {sum(1 for l in leads if l.email_verified)}")
    print(f"  With LinkedIn  : {sum(1 for l in leads if l.linkedin_url)}")
    print(f"  With cold email: {sum(1 for l in leads if l.cold_email and not l.cold_email.startswith('['))}")
    print()


if __name__ == "__main__":
    asyncio.run(main())
