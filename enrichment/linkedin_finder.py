"""Find a LinkedIn company profile via DuckDuckGo search."""
import re
import time
import requests

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    )
}

LI_RE = re.compile(r'https?://(?:www\.)?linkedin\.com/company/[^\s"\'<>&]+', re.I)


def find_linkedin(business_name: str, city: str = "") -> str:
    """Search DuckDuckGo for a LinkedIn company page for the given business."""
    if not business_name:
        return ""
    query = f'site:linkedin.com/company "{business_name}" {city}'.strip()
    try:
        resp = requests.get(
            "https://html.duckduckgo.com/html/",
            params={"q": query},
            headers=HEADERS,
            timeout=10,
        )
        matches = LI_RE.findall(resp.text)
        if matches:
            url = matches[0].rstrip('/"\'').split("?")[0]
            return url
    except Exception:
        pass

    time.sleep(1)  # polite delay between searches
    return ""
