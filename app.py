"""
Sales Lead Generator Pro — Web UI
Run: python app.py  then open http://localhost:5000
"""

import asyncio
import json
import os
import queue
import sys
import threading
import uuid
import zipfile
from datetime import datetime
from pathlib import Path

from flask import Flask, Response, jsonify, render_template, request, send_file

app = Flask(__name__)
app.config["OUTPUT_DIR"] = Path("outputs")
app.config["OUTPUT_DIR"].mkdir(exist_ok=True)

# ── In-memory job store ────────────────────────────────────────────────────────
jobs: dict[str, dict] = {}


# ── Stdout → SSE queue forwarder ──────────────────────────────────────────────

class _QueueWriter:
    """Redirect print() output into an SSE queue."""
    def __init__(self, q: queue.Queue):
        self._q = q
        self._buf = ""

    def write(self, text: str):
        self._buf += text
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            stripped = line.strip()
            if stripped:
                self._q.put({"type": "log", "msg": stripped})

    def flush(self):
        pass


# ── Pipeline runner (runs in background thread) ───────────────────────────────

def _run_pipeline(job_id: str, cfg: dict, q: queue.Queue):
    old_stdout = sys.stdout
    sys.stdout = _QueueWriter(q)

    output_dir = app.config["OUTPUT_DIR"] / job_id
    output_dir.mkdir(parents=True, exist_ok=True)
    base = str(output_dir / "leads")
    files: list[str] = []

    try:
        from models import Lead
        from sources import GoogleMapsScraper, YelpScraper, YellowPagesScraper
        from enrichment import verify_email, find_socials, detect_tech_stack, find_linkedin
        from intelligence.lead_scorer import score_all
        from intelligence.deduplicator import deduplicate
        from outreach.email_generator import generate_all_emails
        from outreach.crm_export import (
            export_csv, export_hubspot, export_salesforce,
            export_pipedrive, export_report,
        )

        keyword  = cfg.get("keyword", "")
        location = cfg.get("location", "")
        max_res  = int(cfg.get("max_results", 30))
        headless = True

        # ── Scraping ──────────────────────────────────────────────────────────
        all_leads: list[Lead] = []

        async def scrape_all():
            if cfg.get("google"):
                print("── Scraping Google Maps ──")
                leads = await GoogleMapsScraper(headless=headless).scrape(keyword, location, max_res)
                all_leads.extend(leads)
            if cfg.get("yelp"):
                print("── Scraping Yelp ──")
                leads = await YelpScraper(headless=headless).scrape(keyword, location, max_res)
                all_leads.extend(leads)
            if cfg.get("yellowpages"):
                print("── Scraping Yellow Pages ──")
                leads = await YellowPagesScraper(headless=headless).scrape(keyword, location, max_res)
                all_leads.extend(leads)

        asyncio.run(scrape_all())
        print(f"Total scraped: {len(all_leads)}")

        # ── Dedup ─────────────────────────────────────────────────────────────
        all_leads, removed = deduplicate(all_leads)
        print(f"Deduplication: removed {removed} → {len(all_leads)} unique leads")

        # ── Enrichment ────────────────────────────────────────────────────────
        total = len(all_leads)
        for idx, lead in enumerate(all_leads, 1):
            print(f"[{idx}/{total}] Enriching: {lead.name[:45]}")
            if cfg.get("social") and lead.website:
                socials = find_socials(lead.website)
                lead.social_facebook  = socials["facebook"]
                lead.social_instagram = socials["instagram"]
                lead.social_twitter   = socials["twitter"]
                if not lead.linkedin_url:
                    lead.linkedin_url = socials["linkedin"]
            if cfg.get("tech") and lead.website:
                lead.tech_stack = ", ".join(detect_tech_stack(lead.website))
            if cfg.get("linkedin") and not lead.linkedin_url:
                lead.linkedin_url = find_linkedin(lead.name, lead.city)
            if cfg.get("verify") and lead.email:
                lead.email_verified = verify_email(lead.email)

        # ── Scoring ───────────────────────────────────────────────────────────
        all_leads = score_all(all_leads)
        hot  = sum(1 for l in all_leads if l.score >= 70)
        warm = sum(1 for l in all_leads if 40 <= l.score < 70)
        cold = sum(1 for l in all_leads if l.score < 40)
        print(f"Scoring done — Hot: {hot}  Warm: {warm}  Cold: {cold}")

        # ── Cold emails ───────────────────────────────────────────────────────
        if cfg.get("cold_email") and cfg.get("service_desc"):
            if cfg.get("api_key"):
                os.environ["ANTHROPIC_API_KEY"] = cfg["api_key"]
            print("Generating cold emails with Claude AI...")
            all_leads = generate_all_emails(all_leads, cfg["service_desc"], cfg.get("sender_name", "the team"))

        # ── Export ────────────────────────────────────────────────────────────
        csv_path = f"{base}.csv"
        export_csv(all_leads, csv_path)
        files.append(csv_path)

        html_path = f"{base}_report.html"
        export_report(all_leads, html_path, title=f"{keyword} in {location}")
        files.append(html_path)

        if cfg.get("hubspot"):
            p = f"{base}_hubspot.csv"
            export_hubspot(all_leads, p)
            files.append(p)
        if cfg.get("salesforce"):
            p = f"{base}_salesforce.csv"
            export_salesforce(all_leads, p)
            files.append(p)
        if cfg.get("pipedrive"):
            p = f"{base}_pipedrive.csv"
            export_pipedrive(all_leads, p)
            files.append(p)

        # ── Zip ───────────────────────────────────────────────────────────────
        zip_path = str(output_dir / "leads_package.zip")
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in files:
                zf.write(f, Path(f).name)
        files.append(zip_path)

        # ── Stats payload ─────────────────────────────────────────────────────
        stats = {
            "total":    len(all_leads),
            "phone":    sum(1 for l in all_leads if l.phone),
            "email":    sum(1 for l in all_leads if l.email),
            "website":  sum(1 for l in all_leads if l.website),
            "verified": sum(1 for l in all_leads if l.email_verified),
            "linkedin": sum(1 for l in all_leads if l.linkedin_url),
            "emails_written": sum(1 for l in all_leads if l.cold_email and not l.cold_email.startswith("[")),
            "hot": hot, "warm": warm, "cold": cold,
        }
        jobs[job_id]["stats"]  = stats
        jobs[job_id]["files"]  = [Path(f).name for f in files]
        jobs[job_id]["status"] = "done"
        print("── All done! ──")

    except Exception as exc:
        import traceback
        print(f"ERROR: {exc}")
        print(traceback.format_exc())
        jobs[job_id]["status"] = "error"

    finally:
        sys.stdout = old_stdout
        q.put(None)  # signal stream end


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/scrape", methods=["POST"])
def start_scrape():
    cfg = request.get_json(force=True)
    job_id = uuid.uuid4().hex[:10]
    q: queue.Queue = queue.Queue()
    jobs[job_id] = {"status": "running", "queue": q, "files": [], "stats": {}}

    t = threading.Thread(target=_run_pipeline, args=(job_id, cfg, q), daemon=True)
    t.start()
    return jsonify({"job_id": job_id})


@app.route("/stream/<job_id>")
def stream(job_id: str):
    if job_id not in jobs:
        return Response("data: {}\n\n", mimetype="text/event-stream")

    def generate():
        q = jobs[job_id]["queue"]
        while True:
            msg = q.get()
            if msg is None:
                payload = {
                    "type":  "done",
                    "stats": jobs[job_id].get("stats", {}),
                    "files": jobs[job_id].get("files", []),
                    "job_id": job_id,
                }
                yield f"data: {json.dumps(payload)}\n\n"
                break
            yield f"data: {json.dumps(msg)}\n\n"

    return Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.route("/download/<job_id>/<filename>")
def download(job_id: str, filename: str):
    path = app.config["OUTPUT_DIR"] / job_id / filename
    if not path.exists():
        return "File not found", 404
    return send_file(str(path.resolve()), as_attachment=True, download_name=filename)


if __name__ == "__main__":
    import webbrowser
    print("\n Sales Lead Generator Pro")
    print(" Open your browser at: http://localhost:5000\n")
    webbrowser.open("http://localhost:5000")
    app.run(debug=False, port=5000, threaded=True)
