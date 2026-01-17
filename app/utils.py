"""
Utility functions for DeSoto Email RSS Digest.
Provides HTTP session with retries, text processing, and helper functions.
"""

import hashlib
import logging
import re
from typing import Optional
from urllib.parse import urlparse, urlunparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from app.config import HTTP_TIMEOUT, HTTP_MAX_RETRIES, HTTP_BACKOFF_FACTOR

logger = logging.getLogger(__name__)


def create_http_session() -> requests.Session:
    """
    Create an HTTP session with automatic retries and exponential backoff.
    Handles transient failures gracefully.
    """
    session = requests.Session()
    
    retry_strategy = Retry(
        total=HTTP_MAX_RETRIES,
        backoff_factor=HTTP_BACKOFF_FACTOR,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "POST"],
        raise_on_status=False,
    )
    
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    
    # Set default timeout and user agent
    session.headers.update({
        "User-Agent": "DeSotoEmailDigest/1.0 (+https://github.com/wallyrebel/desotoemail)"
    })
    
    return session


def fetch_url(url: str, session: Optional[requests.Session] = None) -> Optional[str]:
    """
    Fetch content from a URL with timeout and error handling.
    Returns the response text or None on failure.
    """
    if session is None:
        session = create_http_session()
    
    try:
        response = session.get(url, timeout=HTTP_TIMEOUT)
        response.raise_for_status()
        return response.text
    except requests.RequestException as e:
        logger.warning(f"Failed to fetch {url}: {e}")
        return None


def normalize_url(url: str) -> str:
    """
    Normalize a URL for deduplication purposes.
    Removes fragments, trailing slashes, and normalizes case.
    """
    if not url:
        return ""
    
    parsed = urlparse(url.lower())
    
    # Remove fragment and normalize
    normalized = urlunparse((
        parsed.scheme,
        parsed.netloc,
        parsed.path.rstrip("/"),
        parsed.params,
        parsed.query,
        ""  # Remove fragment
    ))
    
    return normalized


def generate_item_id(entry: dict) -> str:
    """
    Generate a unique ID for an RSS entry using the following cascade:
    1. entry.id or GUID
    2. Normalized entry.link
    3. Hash of title + link + published date
    """
    # Try entry.id first (this is the standard GUID)
    if entry.get("id"):
        return str(entry["id"])
    
    # Try normalized link
    link = entry.get("link", "")
    if link:
        return normalize_url(link)
    
    # Fallback to hash of content
    title = entry.get("title", "")
    published = str(entry.get("published", entry.get("updated", "")))
    
    content = f"{title}|{link}|{published}"
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:32]


def truncate_text(text: str, max_chars: int, preserve_start: bool = True) -> str:
    """
    Truncate text to max_chars, optionally preserving the start (for articles,
    the lead paragraphs are most important).
    """
    if len(text) <= max_chars:
        return text
    
    if preserve_start:
        # Find a good break point (sentence or paragraph)
        truncated = text[:max_chars]
        
        # Try to break at the last complete sentence
        last_period = truncated.rfind(".")
        last_newline = truncated.rfind("\n")
        
        break_point = max(last_period, last_newline)
        if break_point > max_chars * 0.7:  # Only use if we keep at least 70%
            return truncated[:break_point + 1].strip()
        
        return truncated.strip() + "..."
    else:
        return text[:max_chars].strip() + "..."


def clean_whitespace(text: str) -> str:
    """
    Clean up excessive whitespace in text.
    Normalizes multiple spaces/newlines to single ones.
    """
    if not text:
        return ""
    
    # Replace multiple whitespace with single space
    text = re.sub(r"[ \t]+", " ", text)
    
    # Replace multiple newlines with double newline (paragraph break)
    text = re.sub(r"\n{3,}", "\n\n", text)
    
    return text.strip()


def format_summary_log(
    feeds_checked: int,
    items_found: int,
    items_rewritten: int,
    email_sent: bool,
    email_reason: str
) -> str:
    """
    Format a summary log message for the end of a run.
    """
    lines = [
        "=" * 50,
        "RUN SUMMARY",
        "=" * 50,
        f"Feeds checked:    {feeds_checked}",
        f"Items found (24h): {items_found}",
        f"Items rewritten:  {items_rewritten}",
        f"Email sent:       {'Yes' if email_sent else 'No'} ({email_reason})",
        "=" * 50,
    ]
    return "\n".join(lines)
