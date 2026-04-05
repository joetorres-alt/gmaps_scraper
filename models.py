from dataclasses import dataclass, field


@dataclass
class Lead:
    # ── Core info ──────────────────────────────────────────────────────────────
    name: str = ""
    category: str = ""
    address: str = ""
    city: str = ""
    state: str = ""
    phone: str = ""
    website: str = ""
    email: str = ""

    # ── Source ─────────────────────────────────────────────────────────────────
    source: str = ""          # google_maps | yelp | yellow_pages

    # ── Ratings ────────────────────────────────────────────────────────────────
    rating: float = 0.0
    review_count: int = 0

    # ── Social / enrichment ────────────────────────────────────────────────────
    social_facebook: str = ""
    social_instagram: str = ""
    social_twitter: str = ""
    linkedin_url: str = ""
    tech_stack: str = ""      # comma-separated list

    # ── Verification ───────────────────────────────────────────────────────────
    email_verified: bool = False

    # ── Scoring ────────────────────────────────────────────────────────────────
    score: int = 0
    score_reasons: str = ""

    # ── Outreach ───────────────────────────────────────────────────────────────
    cold_email: str = ""
