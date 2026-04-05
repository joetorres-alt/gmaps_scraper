"""Generate personalized cold emails using the Claude API."""
import os
import anthropic
from models import Lead


def generate_cold_email(lead: Lead, your_service: str, sender_name: str = "the team") -> str:
    """
    Use Claude to write a short, personalised cold email for a lead.
    Requires ANTHROPIC_API_KEY environment variable.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return "[No ANTHROPIC_API_KEY set — skipping email generation]"

    client = anthropic.Anthropic(api_key=api_key)

    tech_note = f"Their website uses: {lead.tech_stack}." if lead.tech_stack else ""
    rating_note = f"They have a {lead.rating}★ rating with {lead.review_count} reviews." if lead.rating else ""
    social_note = ""
    if lead.social_facebook or lead.social_instagram:
        platforms = ", ".join(filter(None, [
            "Facebook" if lead.social_facebook else "",
            "Instagram" if lead.social_instagram else "",
        ]))
        social_note = f"They're active on {platforms}."
    no_website_note = "They currently have no website." if not lead.website else ""

    context_lines = " ".join(filter(None, [tech_note, rating_note, social_note, no_website_note]))

    prompt = f"""Write a short, personalized cold outreach email for a sales rep.

Business name: {lead.name}
Location: {lead.address or lead.city}
Category: {lead.category or "local business"}
Context: {context_lines or "Local business found on Google Maps."}

Our product/service: {your_service}
Sender name: {sender_name}

Requirements:
- 3 short paragraphs, under 120 words total
- Opening line references something specific about their business
- Middle paragraph connects our service to their situation
- Closing has a single low-pressure CTA (e.g. "open to a quick 10-min call?")
- Friendly, human tone — not salesy
- Do NOT include a subject line
- Do NOT use placeholder text like [FIRST NAME]
- Address the recipient as the business owner"""

    try:
        message = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=400,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text.strip()
    except Exception as exc:
        return f"[Email generation failed: {exc}]"


def generate_all_emails(leads: list[Lead], your_service: str, sender_name: str = "") -> list[Lead]:
    """Generate cold emails for all leads that have a name."""
    total = len(leads)
    for idx, lead in enumerate(leads, 1):
        if lead.name:
            print(f"  [{idx}/{total}] Generating email for {lead.name[:45]}...")
            lead.cold_email = generate_cold_email(lead, your_service, sender_name)
    return leads
