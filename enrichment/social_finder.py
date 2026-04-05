"""Extract social media profile links from a business website."""
import re
import requests
from dataclasses import dataclass

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    )
}

PATTERNS = {
    "facebook": re.compile(r'https?://(?:www\.)?facebook\.com/(?!sharer|share|dialog|plugins|tr\b)[^\s"\'<>]+', re.I),
    "instagram": re.compile(r'https?://(?:www\.)?instagram\.com/[^\s"\'<>/]+', re.I),
    "twitter": re.compile(r'https?://(?:www\.)?(?:twitter|x)\.com/(?!intent|share|home)[^\s"\'<>]+', re.I),
    "linkedin": re.compile(r'https?://(?:www\.)?linkedin\.com/company/[^\s"\'<>]+', re.I),
}

SKIP_SUFFIXES = {
    "facebook.com/", "instagram.com/", "twitter.com/", "x.com/",
    "linkedin.com/company/", "linkedin.com/",
}


def _clean(url: str) -> str:
    return url.rstrip('/"\'').split("?")[0]


def find_socials(website_url: str) -> dict[str, str]:
    """Fetch the website and return social profile URLs found."""
    result = {"facebook": "", "instagram": "", "twitter": "", "linkedin": ""}
    if not website_url:
        return result
    try:
        resp = requests.get(website_url, headers=HEADERS, timeout=10, allow_redirects=True)
        html = resp.text
    except Exception:
        return result

    for platform, pattern in PATTERNS.items():
        matches = pattern.findall(html)
        for m in matches:
            cleaned = _clean(m)
            if not any(cleaned.rstrip("/") == s.rstrip("/") for s in SKIP_SUFFIXES):
                result[platform] = cleaned
                break

    return result
