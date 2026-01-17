"""
State management for DeSoto Email RSS Digest.
Handles persistence of processed item IDs and last send date.
"""

import json
import logging
import os
import tempfile
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional, Set

from app.config import STATE_FILE

logger = logging.getLogger(__name__)


class StateStore:
    """
    Manages persistent state for the digest system.
    
    State schema:
    {
        "processed_ids": {
            "<feed_url>": ["id1", "id2", ...]
        },
        "last_sent_date": "YYYY-MM-DD" or null
    }
    """
    
    def __init__(self, state_file: Path = STATE_FILE):
        self.state_file = state_file
        self._state: Dict = self._load_state()
    
    def _load_state(self) -> Dict:
        """Load state from JSON file, creating default if missing or invalid."""
        default_state = {
            "processed_ids": {},
            "last_sent_date": None
        }
        
        if not self.state_file.exists():
            logger.info(f"State file not found, creating new: {self.state_file}")
            return default_state
        
        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                state = json.load(f)
            
            # Validate schema
            if not isinstance(state.get("processed_ids"), dict):
                logger.warning("Invalid processed_ids in state, resetting")
                state["processed_ids"] = {}
            
            if "last_sent_date" not in state:
                state["last_sent_date"] = None
            
            logger.info(
                f"Loaded state: {len(state['processed_ids'])} feeds tracked, "
                f"last sent: {state['last_sent_date']}"
            )
            return state
            
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Failed to load state file: {e}")
            logger.info("Creating new state file")
            return default_state
    
    def save(self) -> None:
        """
        Save state to JSON file atomically (write to temp, then rename).
        This prevents corruption if the process is interrupted.
        """
        try:
            # Write to temporary file first
            fd, temp_path = tempfile.mkstemp(
                suffix=".json",
                dir=self.state_file.parent
            )
            
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(self._state, f, indent=2, ensure_ascii=False)
            
            # Atomic rename (on most systems)
            os.replace(temp_path, self.state_file)
            logger.info(f"State saved to {self.state_file}")
            
        except IOError as e:
            logger.error(f"Failed to save state: {e}")
            raise
    
    def is_processed(self, feed_url: str, item_id: str) -> bool:
        """Check if an item has already been processed for a given feed."""
        feed_ids = self._state["processed_ids"].get(feed_url, [])
        return item_id in feed_ids
    
    def mark_processed(self, feed_url: str, item_id: str) -> None:
        """Mark an item as processed for a given feed."""
        if feed_url not in self._state["processed_ids"]:
            self._state["processed_ids"][feed_url] = []
        
        if item_id not in self._state["processed_ids"][feed_url]:
            self._state["processed_ids"][feed_url].append(item_id)
    
    def mark_batch_processed(self, feed_url: str, item_ids: List[str]) -> None:
        """Mark multiple items as processed for a given feed."""
        if feed_url not in self._state["processed_ids"]:
            self._state["processed_ids"][feed_url] = []
        
        current_ids = set(self._state["processed_ids"][feed_url])
        new_ids = [iid for iid in item_ids if iid not in current_ids]
        self._state["processed_ids"][feed_url].extend(new_ids)
    
    def get_processed_ids(self, feed_url: str) -> Set[str]:
        """Get all processed IDs for a feed."""
        return set(self._state["processed_ids"].get(feed_url, []))
    
    def get_last_sent_date(self) -> Optional[str]:
        """Get the last date a digest was sent (YYYY-MM-DD format)."""
        return self._state.get("last_sent_date")
    
    def set_last_sent_date(self, date_str: str) -> None:
        """Set the last sent date (YYYY-MM-DD format)."""
        self._state["last_sent_date"] = date_str
    
    def already_sent_today(self, today_str: str) -> bool:
        """Check if we already sent a digest today."""
        return self.get_last_sent_date() == today_str
    
    def cleanup_old_ids(self, feed_url: str, max_ids: int = 1000) -> None:
        """
        Remove oldest IDs if we have too many to prevent state file bloat.
        Keeps the most recent max_ids entries.
        """
        if feed_url not in self._state["processed_ids"]:
            return
        
        ids = self._state["processed_ids"][feed_url]
        if len(ids) > max_ids:
            logger.info(f"Cleaning up old IDs for {feed_url}: {len(ids)} -> {max_ids}")
            self._state["processed_ids"][feed_url] = ids[-max_ids:]
    
    def has_changes(self) -> bool:
        """
        Check if state has changes that need to be saved.
        For simplicity, we always return True after any operation.
        """
        # In a more sophisticated implementation, we'd track dirty state
        return True
