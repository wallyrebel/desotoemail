"""
Tests for time window filtering with Chicago timezone.
"""

import pytest
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.rss_reader import is_within_lookback_window, parse_entry_datetime
from app.config import CHICAGO_TZ


class TestIsWithinLookbackWindow:
    """Tests for 24-hour lookback window filtering."""
    
    def test_item_from_12_hours_ago_is_included(self):
        now_chicago = datetime.now(CHICAGO_TZ)
        item_dt = now_chicago - timedelta(hours=12)
        
        assert is_within_lookback_window(item_dt, now_chicago)
    
    def test_item_from_23_hours_ago_is_included(self):
        now_chicago = datetime.now(CHICAGO_TZ)
        item_dt = now_chicago - timedelta(hours=23, minutes=59)
        
        assert is_within_lookback_window(item_dt, now_chicago)
    
    def test_item_from_exactly_24_hours_ago_is_included(self):
        now_chicago = datetime.now(CHICAGO_TZ)
        item_dt = now_chicago - timedelta(hours=24)
        
        # Exactly 24h should be included (>=)
        assert is_within_lookback_window(item_dt, now_chicago)
    
    def test_item_from_25_hours_ago_is_excluded(self):
        now_chicago = datetime.now(CHICAGO_TZ)
        item_dt = now_chicago - timedelta(hours=25)
        
        assert not is_within_lookback_window(item_dt, now_chicago)
    
    def test_item_from_future_is_included(self):
        now_chicago = datetime.now(CHICAGO_TZ)
        item_dt = now_chicago + timedelta(hours=1)
        
        # Future items should be included
        assert is_within_lookback_window(item_dt, now_chicago)
    
    def test_handles_utc_item_with_chicago_now(self):
        """Test that UTC items are correctly compared to Chicago time."""
        now_chicago = datetime.now(CHICAGO_TZ)
        
        # Create an item 12 hours ago in UTC
        utc_tz = ZoneInfo("UTC")
        item_dt = datetime.now(utc_tz) - timedelta(hours=12)
        
        assert is_within_lookback_window(item_dt, now_chicago)
    
    def test_dst_transition_handling(self):
        """Test behavior around DST transitions."""
        # Create a specific Chicago time
        chicago = ZoneInfo("America/Chicago")
        # Use a winter date to avoid DST complexity in this test
        now_chicago = datetime(2026, 1, 17, 17, 0, 0, tzinfo=chicago)
        
        # Item from 23 hours ago
        item_dt = now_chicago - timedelta(hours=23)
        assert is_within_lookback_window(item_dt, now_chicago)


class TestParseEntryDatetime:
    """Tests for RSS entry datetime parsing."""
    
    def test_parses_published_parsed(self):
        import time
        # Create a struct_time for 2026-01-17 12:00:00 UTC
        entry = {
            "published_parsed": time.strptime("2026-01-17 12:00:00", "%Y-%m-%d %H:%M:%S")
        }
        
        result = parse_entry_datetime(entry)
        assert result is not None
        assert result.year == 2026
        assert result.month == 1
        assert result.day == 17
    
    def test_parses_updated_parsed_as_fallback(self):
        import time
        entry = {
            "updated_parsed": time.strptime("2026-01-17 12:00:00", "%Y-%m-%d %H:%M:%S")
        }
        
        result = parse_entry_datetime(entry)
        assert result is not None
    
    def test_parses_string_date_fields(self):
        entry = {
            "published": "2026-01-17T12:00:00Z"
        }
        
        result = parse_entry_datetime(entry)
        assert result is not None
        assert result.year == 2026
    
    def test_parses_various_date_formats(self):
        test_dates = [
            "2026-01-17T12:00:00Z",
            "2026-01-17 12:00:00",
            "Fri, 17 Jan 2026 12:00:00 GMT",
            "17 Jan 2026 12:00:00 +0000",
        ]
        
        for date_str in test_dates:
            entry = {"published": date_str}
            result = parse_entry_datetime(entry)
            assert result is not None, f"Failed to parse: {date_str}"
    
    def test_returns_none_for_missing_date(self):
        entry = {"title": "No date here"}
        result = parse_entry_datetime(entry)
        assert result is None
    
    def test_returns_none_for_invalid_date(self):
        entry = {"published": "not a date at all"}
        result = parse_entry_datetime(entry)
        assert result is None
