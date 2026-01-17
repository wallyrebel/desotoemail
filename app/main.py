"""
Main entrypoint for DeSoto Email RSS Digest.
Orchestrates the full digest workflow: fetch feeds, filter items, rewrite, send email.
"""

import logging
import sys
from datetime import datetime

from app.config import (
    setup_logging,
    load_config,
    CHICAGO_TZ,
    SEND_HOUR,
)
from app.state_store import StateStore
from app.rss_reader import fetch_all_feeds
from app.content_extractor import prepare_article_for_rewrite
from app.openai_client import create_openai_client
from app.rewriter import rewrite_batch
from app.emailer import send_digest
from app.utils import format_summary_log

logger = logging.getLogger(__name__)


def should_send_digest(now_chicago: datetime, state: StateStore) -> tuple:
    """
    Determine if we should send the digest now.
    
    Returns:
        (should_send: bool, reason: str)
    """
    current_hour = now_chicago.hour
    today_str = now_chicago.strftime("%Y-%m-%d")
    
    # Check if it's past the send hour
    if current_hour < SEND_HOUR:
        return False, f"not yet {SEND_HOUR}:00 (currently {current_hour}:00)"
    
    # Check if we already sent today
    if state.already_sent_today(today_str):
        return False, f"already sent today ({today_str})"
    
    return True, f"time is {current_hour}:00 >= {SEND_HOUR}:00 and not yet sent today"


def main():
    """
    Main workflow:
    1. Configure logging
    2. Load config and validate secrets
    3. Load state
    4. Check if we should send (Chicago time check)
    5. Fetch all feeds, filter to last 24h, dedupe
    6. Prepare and rewrite articles
    7. Send email digest
    8. Update and save state
    9. Log summary
    """
    # Setup
    setup_logging()
    logger.info("=" * 60)
    logger.info("DeSoto Email RSS Digest - Starting")
    logger.info("=" * 60)
    
    # Get current time in Chicago
    now_chicago = datetime.now(CHICAGO_TZ)
    today_str = now_chicago.strftime("%Y-%m-%d")
    logger.info(f"Current Chicago time: {now_chicago.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    
    # Load configuration
    try:
        config = load_config()
        logger.info(f"Config loaded: {len(config['recipients'])} recipients, DRY_RUN={config['dry_run']}")
    except EnvironmentError as e:
        logger.error(f"Configuration error: {e}")
        sys.exit(1)
    
    # Load state
    state = StateStore()
    
    # Check if we should send (or if force_send is enabled)
    if config.get("force_send"):
        logger.info("FORCE_SEND enabled, skipping time check")
        should_send = True
        reason = "FORCE_SEND enabled"
    else:
        should_send, reason = should_send_digest(now_chicago, state)
    
    if not should_send:
        logger.info(f"Skipping digest: {reason}")
        logger.info("Exiting (nothing to do)")
        return
    
    logger.info(f"Proceeding with digest: {reason}")
    
    # =========================================================================
    # FETCH AND FILTER RSS ITEMS
    # =========================================================================
    logger.info("Fetching RSS feeds...")
    items = fetch_all_feeds(now_chicago, state)
    feeds_checked = len(set(item["feed_url"] for item in items)) if items else 0
    
    if not items:
        logger.info("No new items from feeds")
        
        # Send or skip based on config
        email_sent, email_reason = send_digest(
            config=config,
            articles=[],
            date_str=today_str,
            no_news_behavior=config["no_news_behavior"]
        )
        
        if email_sent or config["no_news_behavior"] == "skip":
            # Mark as sent for today even if we didn't send (to prevent retries)
            state.set_last_sent_date(today_str)
            state.save()
        
        logger.info(format_summary_log(
            feeds_checked=feeds_checked,
            items_found=0,
            items_rewritten=0,
            email_sent=email_sent,
            email_reason=email_reason
        ))
        return
    
    logger.info(f"Found {len(items)} new items across feeds")
    
    # =========================================================================
    # PREPARE ARTICLES FOR REWRITING
    # =========================================================================
    logger.info("Preparing articles for rewriting...")
    prepared_articles = []
    for item in items:
        prepared = prepare_article_for_rewrite(item)
        prepared["item_id"] = item["id"]
        prepared["feed_url"] = item["feed_url"]
        prepared_articles.append(prepared)
    
    logger.info(f"Prepared {len(prepared_articles)} articles")
    
    # =========================================================================
    # REWRITE ARTICLES WITH OPENAI
    # =========================================================================
    logger.info("Creating OpenAI client...")
    openai_client = create_openai_client(config)
    
    logger.info("Rewriting articles in AP style...")
    rewritten_articles = rewrite_batch(openai_client, prepared_articles)
    
    if not rewritten_articles:
        logger.warning("No articles were successfully rewritten")
        
        # Still mark as sent to prevent endless retries
        state.set_last_sent_date(today_str)
        state.save()
        
        logger.info(format_summary_log(
            feeds_checked=feeds_checked,
            items_found=len(items),
            items_rewritten=0,
            email_sent=False,
            email_reason="all rewrites failed"
        ))
        return
    
    # =========================================================================
    # SEND EMAIL DIGEST
    # =========================================================================
    logger.info(f"Sending digest with {len(rewritten_articles)} articles...")
    email_sent, email_reason = send_digest(
        config=config,
        articles=rewritten_articles,
        date_str=today_str,
        no_news_behavior=config["no_news_behavior"]
    )
    
    # =========================================================================
    # UPDATE STATE
    # =========================================================================
    if email_sent or config["dry_run"]:
        # Mark all processed items
        for article in prepared_articles:
            state.mark_processed(article["feed_url"], article["item_id"])
        
        # Mark today as sent
        state.set_last_sent_date(today_str)
        
        # Cleanup old IDs to prevent state bloat
        for feed_url in set(a["feed_url"] for a in prepared_articles):
            state.cleanup_old_ids(feed_url)
        
        # Save state
        state.save()
        logger.info("State updated and saved")
    else:
        logger.warning("Email not sent, state not updated (will retry next run)")
    
    # =========================================================================
    # SUMMARY
    # =========================================================================
    logger.info(format_summary_log(
        feeds_checked=feeds_checked,
        items_found=len(items),
        items_rewritten=len(rewritten_articles),
        email_sent=email_sent,
        email_reason=email_reason
    ))
    
    logger.info("DeSoto Email RSS Digest - Complete")


if __name__ == "__main__":
    main()
