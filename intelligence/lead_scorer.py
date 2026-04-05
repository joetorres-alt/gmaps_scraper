"""Score leads so sales reps know who to call first."""
from models import Lead


def score_lead(lead: Lead) -> tuple[int, list[str]]:
    """
    Return (score, reasons) where score is an integer priority ranking.
    Higher = better lead.
    """
    score = 0
    reasons: list[str] = []

    if lead.phone:
        score += 10
        reasons.append("+10  Has phone number")

    if lead.website:
        score += 10
        reasons.append("+10  Has website")
    else:
        reasons.append(" 0   No website (potential web-dev opportunity)")

    if lead.email:
        score += 15
        reasons.append("+15  Has email address")

    if lead.email_verified:
        score += 10
        reasons.append("+10  Email verified (MX record confirmed)")

    if lead.rating >= 4.5:
        score += 15
        reasons.append(f"+15  Excellent rating ({lead.rating}★)")
    elif lead.rating >= 4.0:
        score += 10
        reasons.append(f"+10  Good rating ({lead.rating}★)")
    elif 0 < lead.rating < 3.0:
        score -= 5
        reasons.append(f"-5   Low rating ({lead.rating}★) — may have pain points")

    if lead.review_count >= 200:
        score += 15
        reasons.append(f"+15  High review volume ({lead.review_count})")
    elif lead.review_count >= 50:
        score += 8
        reasons.append(f"+8   Solid review volume ({lead.review_count})")
    elif lead.review_count >= 10:
        score += 3
        reasons.append(f"+3   Some reviews ({lead.review_count})")

    if lead.social_facebook:
        score += 5
        reasons.append("+5   Active on Facebook")
    if lead.social_instagram:
        score += 5
        reasons.append("+5   Active on Instagram")
    if lead.social_twitter:
        score += 3
        reasons.append("+3   Active on Twitter/X")
    if lead.linkedin_url:
        score += 10
        reasons.append("+10  LinkedIn company page found")

    if lead.tech_stack:
        score += 5
        reasons.append(f"+5   Tech stack detected: {lead.tech_stack}")

    return score, reasons


def score_all(leads: list[Lead]) -> list[Lead]:
    """Score and sort all leads (highest score first)."""
    for lead in leads:
        s, reasons = score_lead(lead)
        lead.score = s
        lead.score_reasons = " | ".join(reasons)
    return sorted(leads, key=lambda l: l.score, reverse=True)
