"""Email verification via DNS MX lookup."""
import dns.resolver


def verify_email(email: str) -> bool:
    """Return True if the email's domain has valid MX records."""
    if not email or "@" not in email:
        return False
    domain = email.split("@")[1].lower().strip()
    try:
        dns.resolver.resolve(domain, "MX")
        return True
    except Exception:
        return False
