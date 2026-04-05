"""Detect the technology stack of a website."""
import requests

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    )
}

# (tech name, list of HTML/header signatures)
SIGNATURES: list[tuple[str, list[str]]] = [
    ("WordPress",    ["wp-content", "wp-includes", "wp-json", "wordpress"]),
    ("Shopify",      ["cdn.shopify.com", "shopify.com/s/", "Shopify.theme"]),
    ("Wix",          ["wix.com", "wixstatic.com", "X-Wix-"]),
    ("Squarespace",  ["squarespace.com", "sqspcdn.com", "static1.squarespace"]),
    ("Webflow",      ["webflow.com", "webflow.io", "data-wf-page"]),
    ("Joomla",       ["/components/com_", "joomla"]),
    ("Drupal",       ["drupal", "sites/default/files", "Drupal.settings"]),
    ("Magento",      ["magento", "Mage.Cookies", "/skin/frontend/"]),
    ("BigCommerce",  ["bigcommerce.com", "bigcommercecdn.com"]),
    ("GoDaddy",      ["godaddy", "secureserver.net"]),
    ("HubSpot",      ["hs-scripts.com", "hubspot.com", "_hsp"]),
    ("Cloudflare",   ["cloudflare", "__cfduid", "cf-ray"]),
    ("React",        ["react", "_react", "react-dom"]),
    ("Angular",      ["ng-version", "angular"]),
    ("Vue",          ["vue.js", "vuejs.org", "__vue__"]),
]


def detect_tech_stack(website_url: str) -> list[str]:
    """Return a list of detected technologies for the given URL."""
    if not website_url:
        return []
    try:
        resp = requests.get(website_url, headers=HEADERS, timeout=10, allow_redirects=True)
        # Combine headers + body into one searchable string
        combined = str(resp.headers).lower() + resp.text.lower()
    except Exception:
        return []

    detected = []
    for tech, sigs in SIGNATURES:
        if any(s.lower() in combined for s in sigs):
            detected.append(tech)
    return detected
