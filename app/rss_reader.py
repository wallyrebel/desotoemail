"""
RSS feed reader for DeSoto Email RSS Digest.
Parses RSS2 and Atom feeds, extracts items from the last 24 hours.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from zoneinfo import ZoneInfo

import feedparser
from dateutil import parser as dateutil_parser

from app.config import CHICAGO_TZ, RSS_LOOKBACK_HOURS, FEEDS_FILE
from app.utils import create_http_session, generate_item_id

logger = logging.getLogger(__name__)


def load_feeds_config() -> List[Dict[str, str]]:
    """Load feed configuration from feeds.yml file."""
    import yaml
    
    try:
        with open(FEEDS_FILE, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        
        feeds = config.get("feeds", [])
        logger.info(f"Loaded {len(feeds)} feeds from {FEEDS_FILE}")
        return feeds
        
    except Exception as e:
        logger.error(f"Failed to load feeds config: {e}")
        raise


def parse_entry_datetime(entry: Dict[str, Any]) -> Optional[datetime]:
    """
    Extract datetime from an RSS entry using fallback cascade:
    1. entry.published_parsed (struct_time)
    2. entry.updated_parsed (struct_time)
    3. Parse common string date fields
    4. Return None if all fail
    """
    # Try parsed timestamps first (feedparser provides these as time.struct_time)
    for field in ["published_parsed", "updated_parsed"]:
        parsed = entry.get(field)
        if parsed:
            try:
                # Convert struct_time to datetime (feedparser gives UTC)
                dt = datetime(*parsed[:6], tzinfo=ZoneInfo("UTC"))
                return dt
            except (ValueError, TypeError):
                continue
    
    # Try string date fields
    for field in ["published", "updated", "pubDate", "date", "created"]:
        date_str = entry.get(field)
        if date_str and isinstance(date_str, str):
            try:
                # Use dateutil for flexible parsing
                dt = dateutil_parser.parse(date_str)
                
                # If naive, assume UTC
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=ZoneInfo("UTC"))
                
                return dt
            except (ValueError, TypeError):
                continue
    
    # No date found
    return None


def is_within_lookback_window(
    item_dt: datetime,
    now_chicago: datetime,
    lookback_hours: int = RSS_LOOKBACK_HOURS
) -> bool:
    """
    Check if an item datetime is within the lookback window.
    Both datetimes should be timezone-aware.
    """
    # Convert item datetime to Chicago timezone for comparison
    item_chicago = item_dt.astimezone(CHICAGO_TZ)
    cutoff = now_chicago - timedelta(hours=lookback_hours)
    
    return item_chicago >= cutoff


def fetch_feed(feed_url: str) -> Optional[feedparser.FeedParserDict]:
    """
    Fetch and parse an RSS/Atom feed.
    Returns the parsed feed or None on failure.
    """
    session = create_http_session()
    
    try:
        response = session.get(feed_url, timeout=30)
        response.raise_for_status()
        
        # Parse the feed content
        feed = feedparser.parse(response.content)
        
        # Check for parsing errors
        if feed.bozo and feed.bozo_exception:
            logger.warning(f"Feed parsing warning for {feed_url}: {feed.bozo_exception}")
        
        return feed
        
    except Exception as e:
        logger.error(f"Failed to fetch feed {feed_url}: {e}")
        return None


def process_feed(
    feed_config: Dict[str, str],
    now_chicago: datetime,
    processed_ids: set
) -> List[Dict[str, Any]]:
    """
    Process a single feed and return items from the last 24 hours
    that haven't been processed yet.
    
    Returns a list of dicts with:
    - id: unique item identifier
    - title: item title
    - link: item URL
    - content: item content/summary
    - published: datetime object
    - source_name: feed name
    - feed_url: feed URL
    """
    feed_url = feed_config["url"]
    feed_name = feed_config.get("name", feed_url)
    category = feed_config.get("category", "")
    
    logger.info(f"Processing feed: {feed_name}")
    
    feed = fetch_feed(feed_url)
    if not feed:
        return []
    
    items = []
    skipped_no_date = 0
    skipped_old = 0
    skipped_duplicate = 0
    
    for entry in feed.entries:
        # Generate unique ID
        item_id = generate_item_id(entry)
        
        # Skip if already processed
        if item_id in processed_ids:
            skipped_duplicate += 1
            continue
        
        # Parse datetime
        item_dt = parse_entry_datetime(entry)
        if item_dt is None:
            logger.debug(f"Skipping item with no date: {entry.get('title', 'Unknown')[:50]}")
            skipped_no_date += 1
            continue
        
        # Check if within lookback window
        if not is_within_lookback_window(item_dt, now_chicago):
            skipped_old += 1
            continue
        
        # Extract content (prefer content:encoded, then summary, then description)
        content = ""
        if "content" in entry and entry.content:
            content = entry.content[0].get("value", "")
        elif "summary" in entry:
            content = entry.get("summary", "")
        elif "description" in entry:
            content = entry.get("description", "")
        
        items.append({
            "id": item_id,
            "title": entry.get("title", "Untitled"),
            "link": entry.get("link", ""),
            "content": content,
            "published": item_dt,
            "source_name": feed_name,
            "feed_url": feed_url,
            "category": category,
        })
    
    logger.info(
        f"  Found {len(items)} new items, "
        f"skipped: {skipped_duplicate} duplicates, {skipped_old} old, {skipped_no_date} no date"
    )
    
    return items


def fetch_all_feeds(now_chicago: datetime, state_store) -> List[Dict[str, Any]]:
    """
    Fetch all feeds and return all new items from the last 24 hours.
    """
    feeds_config = load_feeds_config()
    all_items = []
    
    for feed_config in feeds_config:
        feed_url = feed_config["url"]
        processed_ids = state_store.get_processed_ids(feed_url)
        
        items = process_feed(feed_config, now_chicago, processed_ids)
        all_items.extend(items)
    
    # Sort by published date (newest first)
    all_items.sort(key=lambda x: x["published"], reverse=True)
    
    logger.info(f"Total new items from all feeds: {len(all_items)}")
    return all_items
