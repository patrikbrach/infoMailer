import httpx
import re
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS

SKIP_DOMAINS = [
    "hitta.se", "eniro.se", "allabolag.se", "ratsit.se",
    "facebook.com", "instagram.com", "google.com", "yelp.com",
    "bokus.com", "pricerunner.se", "tripadvisor.com",
]

EMAIL_PRIORITY = ["info@", "kontakt@", "bokning@", "reception@"]


def enrich_row(name: str, city: str) -> tuple[str | None, str | None]:
    query = f"{name} {city}"
    url = google_first_hit(query)
    if not url:
        return None, None
    emails = fetch_emails(url)
    return pick_best_email(emails), url


def google_first_hit(query: str) -> str | None:
    try:
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=5, region="se-sv"):
                url = r.get("href", "")
                if url and not any(skip in url for skip in SKIP_DOMAINS):
                    return url
    except Exception:
        pass
    return None


def fetch_emails(url: str) -> list[str]:
    try:
        r = httpx.get(
            url,
            timeout=10,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
        )
        soup = BeautifulSoup(r.text, "html.parser")
        text = soup.get_text()
        # Also check mailto: links in HTML
        raw_html = r.text
        emails = set(re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text))
        emails |= set(re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', raw_html))
        # Filter out image/file extensions that are not emails
        emails = {e for e in emails if not re.search(r'\.(png|jpg|jpeg|gif|svg|webp|css|js)$', e, re.I)}
        return list(emails)
    except Exception:
        return []


def pick_best_email(emails: list[str]) -> str | None:
    if not emails:
        return None
    for prefix in EMAIL_PRIORITY:
        for e in emails:
            if e.lower().startswith(prefix):
                return e
    return sorted(emails)[0]
