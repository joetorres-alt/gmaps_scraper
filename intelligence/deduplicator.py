"""Remove duplicate leads across multiple sources."""
import re
from models import Lead


def _normalize(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s]", "", text)
    text = re.sub(r"\s+", " ", text)
    for word in ["llc", "inc", "ltd", "co", "the", "and", "&"]:
        text = re.sub(rf"\b{word}\b", "", text)
    return text.strip()


def deduplicate(leads: list[Lead]) -> tuple[list[Lead], int]:
    """
    Deduplicate leads by phone number (primary) or normalized business name.
    Returns (deduped_list, removed_count).
    Merges data from duplicates so no info is lost.
    """
    by_phone: dict[str, Lead] = {}
    by_name: dict[str, Lead] = {}
    result: list[Lead] = []
    removed = 0

    for lead in leads:
        phone_key = re.sub(r"\D", "", lead.phone) if lead.phone else ""
        name_key = _normalize(lead.name) if lead.name else ""

        matched: Lead | None = None

        if phone_key and phone_key in by_phone:
            matched = by_phone[phone_key]
        elif name_key and name_key in by_name:
            matched = by_name[name_key]

        if matched:
            _merge(matched, lead)
            removed += 1
        else:
            result.append(lead)
            if phone_key:
                by_phone[phone_key] = lead
            if name_key:
                by_name[name_key] = lead

    return result, removed


def _merge(base: Lead, other: Lead) -> None:
    """Fill empty fields in base with values from other."""
    for field_name in base.__dataclass_fields__:
        base_val = getattr(base, field_name)
        other_val = getattr(other, field_name)
        if not base_val and other_val:
            setattr(base, field_name, other_val)
    # Combine sources
    if other.source and other.source not in base.source:
        base.source = f"{base.source},{other.source}".strip(",")
