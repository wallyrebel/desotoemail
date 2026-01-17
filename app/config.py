"""
Configuration module for DeSoto Email RSS Digest.
Loads all settings from environment variables and validates required secrets.
"""

import os
import logging
from zoneinfo import ZoneInfo
from pathlib import Path

# ============================================================================
# TIMEZONE CONFIGURATION
# ============================================================================
CHICAGO_TZ = ZoneInfo("America/Chicago")
SEND_HOUR = 17  # 5:00 PM Chicago time

# ============================================================================
# FILE PATHS
# ============================================================================
PROJECT_ROOT = Path(__file__).parent.parent
FEEDS_FILE = PROJECT_ROOT / "feeds.yml"
STATE_FILE = PROJECT_ROOT / "state.json"

# ============================================================================
# HTTP CONFIGURATION
# ============================================================================
HTTP_TIMEOUT = 30  # seconds
HTTP_MAX_RETRIES = 3
HTTP_BACKOFF_FACTOR = 2  # exponential backoff multiplier

# ============================================================================
# OPENAI CONFIGURATION
# ============================================================================
OPENAI_PRIMARY_MODEL = "gpt-5-mini"
OPENAI_FALLBACK_MODEL = "gpt-4.1-nano"
OPENAI_MAX_RETRIES = 5
OPENAI_MAX_INPUT_CHARS = 12000  # Truncate content beyond this

# ============================================================================
# GMAIL SMTP CONFIGURATION
# ============================================================================
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 465  # SSL port
SMTP_MAX_RETRIES = 3

# ============================================================================
# RSS CONFIGURATION
# ============================================================================
RSS_LOOKBACK_HOURS = 24  # Only consider items from last 24 hours

# ============================================================================
# ENVIRONMENT VARIABLES (loaded at runtime)
# ============================================================================

def get_required_env(name: str) -> str:
    """Get a required environment variable or raise an error."""
    value = os.environ.get(name)
    if not value:
        raise EnvironmentError(f"Required environment variable '{name}' is not set")
    return value


def get_optional_env(name: str, default: str = "") -> str:
    """Get an optional environment variable with a default value."""
    return os.environ.get(name, default)


def load_config() -> dict:
    """
    Load and validate all configuration from environment variables.
    Returns a dict with all config values.
    Raises EnvironmentError if required variables are missing.
    """
    config = {
        # Required secrets
        "openai_api_key": get_required_env("OPENAI_API_KEY"),
        "gmail_user": get_required_env("GMAIL_USER"),
        "gmail_app_password": get_required_env("GMAIL_APP_PASSWORD"),
        "recipients": [
            r.strip() 
            for r in get_required_env("RECIPIENTS").split(",") 
            if r.strip()
        ],
        
        # Optional settings
        "dry_run": get_optional_env("DRY_RUN", "false").lower() == "true",
        "force_send": get_optional_env("FORCE_SEND", "false").lower() == "true",
        "no_news_behavior": get_optional_env("NO_NEWS_BEHAVIOR", "skip"),  # skip or send_empty
        
        # Model configuration
        "openai_primary_model": get_optional_env("OPENAI_MODEL", OPENAI_PRIMARY_MODEL),
        "openai_fallback_model": OPENAI_FALLBACK_MODEL,
    }
    
    # Validate recipients
    if len(config["recipients"]) == 0:
        raise EnvironmentError("RECIPIENTS must contain at least one email address")
    
    # Validate no_news_behavior
    if config["no_news_behavior"] not in ("skip", "send_empty"):
        logging.warning(
            f"Invalid NO_NEWS_BEHAVIOR '{config['no_news_behavior']}', using 'skip'"
        )
        config["no_news_behavior"] = "skip"
    
    return config


def setup_logging() -> None:
    """
    Configure structured logging for GitHub Actions.
    Uses a format that's readable in Actions logs.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[logging.StreamHandler()]
    )
    
    # Reduce noise from third-party libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
