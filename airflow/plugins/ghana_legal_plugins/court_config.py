"""Court configuration for Ghana Legal AI pipeline."""

from dataclasses import dataclass
from typing import Dict

# Unified listing URL for all courts
ALL_JUDGMENTS_URL = "https://ghalii.org/judgments/all/"

# Rate limiting
DEFAULT_REQUEST_DELAY = 1.5
DEFAULT_MAX_PAGES = 100


@dataclass(frozen=True)
class CourtConfig:
    court_id: str
    name: str
    url_slug: str  # e.g. "ghasc" as it appears in /akn/gh/judgment/ghasc/


# Known courts and their URL slugs
COURTS: Dict[str, CourtConfig] = {
    "GHASC": CourtConfig(court_id="GHASC", name="Ghana Supreme Court", url_slug="ghasc"),
    "GHACA": CourtConfig(court_id="GHACA", name="Ghana Court of Appeal", url_slug="ghaca"),
    "GHAHC": CourtConfig(court_id="GHAHC", name="Ghana High Court", url_slug="ghahc"),
    "GHACC": CourtConfig(court_id="GHACC", name="Ghana Commercial Court", url_slug="ghacc"),
    "GHADC": CourtConfig(court_id="GHADC", name="Ghana District Court", url_slug="ghadc"),
    "ECOWASCJ": CourtConfig(court_id="ECOWASCJ", name="ECOWAS Court of Justice", url_slug="ecowascj"),
    "AFCHPR": CourtConfig(court_id="AFCHPR", name="African Court on Human and Peoples' Rights", url_slug="afchpr"),
}

# Reverse lookup: url_slug -> court_id
SLUG_TO_COURT_ID: Dict[str, str] = {c.url_slug: c.court_id for c in COURTS.values()}


def court_id_from_url(url: str) -> str:
    """Extract court_id from a ghalii case URL.

    e.g. /akn/gh/judgment/ghasc/2025/10/eng@2025-02-16 -> GHASC
    """
    for slug, court_id in SLUG_TO_COURT_ID.items():
        if f"/judgment/{slug}/" in url:
            return court_id
    return "UNKNOWN"
