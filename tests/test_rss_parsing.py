"""
Tests for RSS feed parsing functionality.
"""

import pytest
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from unittest.mock import Mock, patch

from app.rss_reader import process_feed
from app.config import CHICAGO_TZ


class TestProcessFeed:
    """Tests for RSS feed processing."""
    
    @pytest.fixture
    def mock_feed(self):
        """Create a mock feed with sample entries."""
        import time
        
        now = datetime.now(ZoneInfo("UTC"))
        
        entry_recent = Mock()
        entry_recent.get = lambda k, d=None: {
            "id": "recent-123",
            "title": "Recent Article",
            "link": "https://example.com/recent",
            "published_parsed": now.timetuple(),
            "summary": "This is a recent article summary."
        }.get(k, d)
        entry_recent.id = "recent-123"
        entry_recent.title = "Recent Article"
        entry_recent.link = "https://example.com/recent"
        entry_recent.published_parsed = now.timetuple()
        entry_recent.summary = "This is a recent article summary."
        entry_recent.content = None
        
        entry_old = Mock()
        old_time = (now - timedelta(hours=48)).timetuple()
        entry_old.get = lambda k, d=None: {
            "id": "old-456",
            "title": "Old Article",
            "link": "https://example.com/old",
            "published_parsed": old_time,
            "summary": "This is an old article."
        }.get(k, d)
        entry_old.id = "old-456"
        entry_old.title = "Old Article"
        entry_old.link = "https://example.com/old"
        entry_old.published_parsed = old_time
        entry_old.summary = "This is an old article."
        entry_old.content = None
        
        feed = Mock()
        feed.entries = [entry_recent, entry_old]
        feed.bozo = False
        feed.bozo_exception = None
        
        return feed
    
    @patch('app.rss_reader.fetch_feed')
    def test_filters_old_items(self, mock_fetch, mock_feed):
        """Test that items older than 24 hours are filtered out."""
        mock_fetch.return_value = mock_feed
        
        feed_config = {
            "name": "Test Feed",
            "url": "https://example.com/feed",
            "category": "test"
        }
        now_chicago = datetime.now(CHICAGO_TZ)
        processed_ids = set()
        
        items = process_feed(feed_config, now_chicago, processed_ids)
        
        # Should only include the recent item
        assert len(items) == 1
        assert items[0]["title"] == "Recent Article"
    
    def test_skips_already_processed_items(self):
        """Test that already-processed items are skipped."""
        # This would need a more complete mock setup
        pass  # Placeholder for integration test


class TestRSSParsingSamples:
    """Tests with sample RSS/Atom content."""
    
    def test_rss2_item_structure(self):
        """Verify expected RSS2 item fields."""
        # Sample RSS2 entry dict (as feedparser would return)
        entry = {
            "id": "guid-12345",
            "title": "Breaking News: Test Event",
            "link": "https://news.example.com/article/12345",
            "published": "Fri, 17 Jan 2026 10:30:00 GMT",
            "summary": "<p>This is the article summary with <strong>HTML</strong>.</p>",
            "author": "John Doe"
        }
        
        # Verify we can extract expected fields
        assert entry.get("id") == "guid-12345"
        assert "Breaking News" in entry.get("title", "")
    
    def test_atom_item_structure(self):
        """Verify expected Atom entry fields."""
        # Sample Atom entry dict
        entry = {
            "id": "urn:uuid:12345-67890",
            "title": "Atom Entry Title",
            "link": "https://blog.example.com/post/123",
            "updated": "2026-01-17T10:30:00Z",
            "content": [{"value": "<p>Full content here.</p>", "type": "text/html"}],
            "author_detail": {"name": "Jane Smith"}
        }
        
        # Verify we can extract expected fields
        assert entry.get("id") == "urn:uuid:12345-67890"
        assert entry.get("content")[0].get("value") is not None


class TestMissingDateHandling:
    """Tests for handling entries without dates."""
    
    def test_entry_without_any_date_fields(self):
        """Entry with no date should return None from parsing."""
        from app.rss_reader import parse_entry_datetime
        
        entry = {
            "title": "Article Without Date",
            "link": "https://example.com/no-date",
            "summary": "No date information available."
        }
        
        result = parse_entry_datetime(entry)
        assert result is None
