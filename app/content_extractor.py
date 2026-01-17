"""
Content extraction for DeSoto Email RSS Digest.
Handles HTML cleanup, text extraction, and featured image detection.
"""

import logging
import re
from typing import Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from app.utils import create_http_session, clean_whitespace

logger = logging.getLogger(__name__)


def strip_html_to_text(html_content: str) -> str:
    """
    Convert HTML content to clean plain text.
    Removes all tags, scripts, styles, and normalizes whitespace.
    """
    if not html_content:
        return ""
    
    try:
        soup = BeautifulSoup(html_content, "lxml")
        
        # Remove script and style elements
        for element in soup(["script", "style", "nav", "footer", "header", "aside"]):
            element.decompose()
        
        # Get text
        text = soup.get_text(separator="\n")
        
        # Clean up whitespace
        return clean_whitespace(text)
        
    except Exception as e:
        logger.warning(f"HTML parsing failed: {e}")
        # Fallback: simple regex-based tag removal
        text = re.sub(r"<[^>]+>", "", html_content)
        return clean_whitespace(text)


def extract_image_from_rss(entry: dict) -> Optional[str]:
    """
    Extract featured image URL from RSS entry using cascade:
    1. media:content, media:thumbnail, enclosures
    2. First <img> in content:encoded or summary HTML
    
    Returns image URL or None.
    """
    # Check media:content (common in RSS feeds)
    media_content = entry.get("media_content")
    if media_content:
        for media in media_content:
            url = media.get("url", "")
            media_type = media.get("type", "")
            if url and ("image" in media_type or not media_type):
                logger.debug(f"Found image in media:content: {url[:60]}")
                return url
    
    # Check media:thumbnail
    media_thumbnail = entry.get("media_thumbnail")
    if media_thumbnail:
        for thumb in media_thumbnail:
            url = thumb.get("url", "")
            if url:
                logger.debug(f"Found image in media:thumbnail: {url[:60]}")
                return url
    
    # Check enclosures
    enclosures = entry.get("enclosures")
    if enclosures:
        for enclosure in enclosures:
            url = enclosure.get("url", "") or enclosure.get("href", "")
            enc_type = enclosure.get("type", "")
            if url and "image" in enc_type:
                logger.debug(f"Found image in enclosure: {url[:60]}")
                return url
    
    # Check for image in content or summary HTML
    for field in ["content", "summary", "description"]:
        content = ""
        if field == "content":
            content_list = entry.get("content")
            if content_list and isinstance(content_list, list) and len(content_list) > 0:
                content = content_list[0].get("value", "")
        else:
            content = entry.get(field, "")
        
        if content:
            img_url = extract_first_img_from_html(content)
            if img_url:
                logger.debug(f"Found image in {field} HTML: {img_url[:60]}")
                return img_url
    
    return None


def extract_first_img_from_html(html: str) -> Optional[str]:
    """
    Extract the first <img> src from HTML content.
    """
    if not html:
        return None
    
    try:
        soup = BeautifulSoup(html, "lxml")
        img = soup.find("img")
        
        if img:
            # Try src first, then data-src (for lazy loading)
            src = img.get("src") or img.get("data-src")
            if src and not src.startswith("data:"):  # Skip base64 images
                return src
        
        return None
        
    except Exception as e:
        logger.warning(f"Failed to extract img from HTML: {e}")
        return None


def extract_image_from_article_page(article_url: str) -> Optional[str]:
    """
    Fetch the article page and extract featured image from meta tags:
    - og:image
    - twitter:image
    
    Returns image URL or None.
    """
    if not article_url:
        return None
    
    session = create_http_session()
    
    try:
        response = session.get(article_url, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, "lxml")
        
        # Try og:image first
        og_image = soup.find("meta", property="og:image")
        if og_image and og_image.get("content"):
            img_url = og_image["content"]
            # Make absolute URL if relative
            img_url = urljoin(article_url, img_url)
            logger.debug(f"Found og:image: {img_url[:60]}")
            return img_url
        
        # Try twitter:image
        twitter_image = soup.find("meta", attrs={"name": "twitter:image"})
        if twitter_image and twitter_image.get("content"):
            img_url = twitter_image["content"]
            img_url = urljoin(article_url, img_url)
            logger.debug(f"Found twitter:image: {img_url[:60]}")
            return img_url
        
        # Try first large image as fallback
        # (looking for images with reasonable dimensions)
        
        return None
        
    except Exception as e:
        logger.warning(f"Failed to fetch article for image extraction: {e}")
        return None


def extract_featured_image(entry: dict, article_url: str) -> Optional[str]:
    """
    Extract featured image using full cascade:
    1. From RSS entry (media, enclosure, content HTML)
    2. From article page meta tags
    
    Returns image URL or None.
    """
    # Try RSS first (faster, no extra request)
    img_url = extract_image_from_rss(entry)
    if img_url:
        return img_url
    
    # Try article page (requires HTTP request)
    img_url = extract_image_from_article_page(article_url)
    if img_url:
        return img_url
    
    logger.debug(f"No featured image found for: {article_url[:50]}")
    return None


def prepare_article_for_rewrite(item: dict) -> dict:
    """
    Prepare an article item for OpenAI rewriting.
    
    Returns a dict with:
    - source_name
    - url
    - title
    - clean_content (plain text, truncated if needed)
    - featured_image_url (or None)
    """
    from app.config import OPENAI_MAX_INPUT_CHARS
    from app.utils import truncate_text
    
    # Clean the content
    clean_content = strip_html_to_text(item.get("content", ""))
    
    # Truncate if too long (keep the lead paragraphs)
    if len(clean_content) > OPENAI_MAX_INPUT_CHARS:
        clean_content = truncate_text(clean_content, OPENAI_MAX_INPUT_CHARS)
        logger.debug(f"Truncated content for: {item.get('title', 'Unknown')[:50]}")
    
    # Extract featured image
    # We need to reconstruct the entry dict for image extraction
    entry = {
        "media_content": item.get("media_content"),
        "media_thumbnail": item.get("media_thumbnail"),
        "enclosures": item.get("enclosures"),
        "content": [{"value": item.get("content", "")}] if item.get("content") else None,
        "summary": item.get("summary"),
        "description": item.get("description"),
    }
    featured_image = extract_featured_image(entry, item.get("link", ""))
    
    return {
        "source_name": item.get("source_name", "Unknown Source"),
        "url": item.get("link", ""),
        "title": item.get("title", "Untitled"),
        "clean_content": clean_content,
        "featured_image_url": featured_image,
    }
