"""enricher.py — Contact enrichment pipeline. Zero Streamlit imports."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

try:
    from duckduckgo_search import DDGS
except ImportError:
    DDGS = None  # type: ignore

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────────

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "sv-SE,sv;q=0.9,en;q=0.8",
}

TIMEOUT = 10

SITE_BLOCKLIST = {
    "eniro.se", "hitta.se", "allabolag.se", "ratsit.se", "merinfo.se",
    "birthday.se", "facebook.com", "instagram.com", "twitter.com", "x.com",
    "linkedin.com", "youtube.com", "tiktok.com", "tripadvisor.com",
    "tripadvisor.se", "google.com", "google.se", "yelp.com",
    "trustpilot.com", "thefork.com", "bokabord.se",
}

EMAIL_JUNK_DOMAINS = {
    "eniro.se", "hitta.se", "allabolag.se", "google.com", "facebook.com",
    "instagram.com", "twitter.com", "x.com", "sentry.io", "wixpress.com",
    "squarespace.com", "wordpress.com", "example.com",
}

EMAIL_JUNK_LOCAL = {
    "noreply", "donotreply", "mailerdaemon", "postmaster", "webmaster",
}

EMAIL_PRIORITY = ["info@", "kontakt@", "bokning@", "hej@", "mail@"]

CONTACT_PATHS = ["/kontakt", "/kontakta-oss", "/contact", "/om-oss", "/about"]

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
PHONE_RE = re.compile(r"(?:\+46|0)\s*[\d\s\-()]{7,15}")


# ── Data model ─────────────────────────────────────────────────────────────────

@dataclass
class EnrichmentResult:
    email: str | None = None
    phone: str | None = None
    website: str | None = None
    source: str | None = None   # "webbplats" | "DDG-sökning" | "ej hittad" | "fel"
    error: str | None = None


# ── Helpers ────────────────────────────────────────────────────────────────────

def _domain(url: str) -> str:
    try:
        host = urlparse(url).netloc.lower()
        return host.removeprefix("www.")
    except Exception:
        return ""


def _is_blocked(url: str) -> bool:
    d = _domain(url)
    return any(d == b or d.endswith("." + b) for b in SITE_BLOCKLIST)


def _is_junk_email(email: str) -> bool:
    email = email.lower()
    if "@" not in email:
        return True
    local, domain = email.split("@", 1)
    if domain in EMAIL_JUNK_DOMAINS:
        return True
    normalized = re.sub(r"[-.]", "", local)
    return normalized in EMAIL_JUNK_LOCAL


def _extract_emails(soup: BeautifulSoup, html: str) -> list[str]:
    collected: list[str] = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.startswith("mailto:"):
            addr = href[7:].split("?")[0].strip().lower()
            if addr and not _is_junk_email(addr):
                collected.append(addr)
    for match in EMAIL_RE.findall(html):
        m = match.lower()
        if not _is_junk_email(m):
            collected.append(m)
    seen: set[str] = set()
    result: list[str] = []
    for e in collected:
        if e not in seen:
            seen.add(e)
            result.append(e)
    return result


def _extract_phones(soup: BeautifulSoup) -> list[str]:
    collected: list[str] = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.startswith("tel:"):
            num = href[4:].strip()
            if len(re.sub(r"\D", "", num)) >= 8:
                collected.append(num)
    text = soup.get_text(separator=" ")
    for match in PHONE_RE.findall(text):
        if len(re.sub(r"\D", "", match)) >= 8:
            collected.append(match.strip())
    seen: set[str] = set()
    result: list[str] = []
    for p in collected:
        key = re.sub(r"\D", "", p)
        if key not in seen:
            seen.add(key)
            result.append(p)
    return result


def _pick_best_email(emails: list[str]) -> str | None:
    if not emails:
        return None
    for prefix in EMAIL_PRIORITY:
        for e in emails:
            if e.startswith(prefix):
                return e
    return emails[0]


def _fetch_page(url: str) -> tuple[BeautifulSoup | None, str]:
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        return soup, r.text
    except Exception as exc:
        logger.warning("Failed to fetch %s: %s", url, exc)
        return None, ""


# ── Pipeline steps ─────────────────────────────────────────────────────────────

def _find_website(name: str, city: str) -> str | None:
    if DDGS is None:
        logger.warning("duckduckgo-search not installed, skipping DDG search.")
        return None
    query = f"{name} {city}".strip()
    try:
        with DDGS() as ddgs:
            for result in ddgs.text(query, region="se-sv", max_results=8):
                url = result.get("href", "")
                if url and not _is_blocked(url):
                    return url
    except Exception as exc:
        logger.warning("DuckDuckGo search failed for '%s': %s", query, exc)
    return None


def _scrape_site(url: str) -> tuple[list[str], list[str]]:
    """Scrape homepage + common contact sub-pages. Returns (emails, phones)."""
    all_emails: list[str] = []
    all_phones: list[str] = []
    parsed = urlparse(url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    pages = [url] + [base + path for path in CONTACT_PATHS]

    for page_url in pages:
        soup, html = _fetch_page(page_url)
        if soup is None:
            continue
        all_emails.extend(_extract_emails(soup, html))
        all_phones.extend(_extract_phones(soup))
        all_emails = list(dict.fromkeys(all_emails))
        all_phones = list(dict.fromkeys(all_phones))
        if all_emails and all_phones:
            break

    return all_emails, all_phones


def _fallback_email_search(name: str, city: str) -> str | None:
    if DDGS is None:
        return None
    query = f"{name} {city} email kontakt".strip()
    try:
        with DDGS() as ddgs:
            for result in ddgs.text(query, region="se-sv", max_results=5):
                for field_val in (result.get("body", ""), result.get("title", "")):
                    for match in EMAIL_RE.findall(field_val):
                        if not _is_junk_email(match.lower()):
                            return match.lower()
    except Exception as exc:
        logger.warning("Fallback email search failed for '%s': %s", query, exc)
    return None


# ── Public API ─────────────────────────────────────────────────────────────────

def enrich_company(name: str, city: str = "", address: str = "") -> EnrichmentResult:
    try:
        website = _find_website(name, city)

        emails: list[str] = []
        phones: list[str] = []
        if website:
            emails, phones = _scrape_site(website)

        best_email = _pick_best_email(emails)
        best_phone = phones[0] if phones else None

        if not best_email:
            fallback = _fallback_email_search(name, city)
            if fallback:
                best_email = fallback

        if website and (best_email or best_phone):
            source = "webbplats"
        elif best_email:
            source = "DDG-sökning"
        elif website:
            source = "webbplats"
        else:
            source = "ej hittad"

        return EnrichmentResult(
            email=best_email,
            phone=best_phone,
            website=website,
            source=source,
        )
    except Exception as exc:
        logger.error("Enrichment failed for '%s': %s", name, exc)
        return EnrichmentResult(source="fel", error=str(exc))
