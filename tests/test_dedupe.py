"""
Tests for deduplication ID generation.
"""

import pytest
from app.utils import generate_item_id, normalize_url


class TestNormalizeUrl:
    """Tests for URL normalization."""
    
    def test_removes_fragment(self):
        url = "https://example.com/article?id=123#comments"
        assert normalize_url(url) == "https://example.com/article?id=123"
    
    def test_removes_trailing_slash(self):
        url = "https://example.com/article/"
        assert normalize_url(url) == "https://example.com/article"
    
    def test_lowercases_url(self):
        url = "HTTPS://Example.COM/Article"
        assert normalize_url(url) == "https://example.com/article"
    
    def test_handles_empty_string(self):
        assert normalize_url("") == ""
    
    def test_preserves_query_params(self):
        url = "https://example.com/article?page=2&sort=date"
        assert "page=2" in normalize_url(url)


class TestGenerateItemId:
    """Tests for RSS item ID generation."""
    
    def test_uses_entry_id_if_present(self):
        entry = {"id": "unique-guid-123", "link": "https://example.com/article"}
        assert generate_item_id(entry) == "unique-guid-123"
    
    def test_uses_normalized_link_if_no_id(self):
        entry = {"link": "https://example.com/article/"}
        result = generate_item_id(entry)
        assert result == "https://example.com/article"
    
    def test_generates_hash_if_no_id_or_link(self):
        entry = {"title": "Test Article", "published": "2026-01-17"}
        result = generate_item_id(entry)
        # Should be a 32-char hash
        assert len(result) == 32
        assert result.isalnum()
    
    def test_same_content_generates_same_hash(self):
        entry1 = {"title": "Test Article", "published": "2026-01-17"}
        entry2 = {"title": "Test Article", "published": "2026-01-17"}
        assert generate_item_id(entry1) == generate_item_id(entry2)
    
    def test_different_content_generates_different_hash(self):
        entry1 = {"title": "Test Article 1", "published": "2026-01-17"}
        entry2 = {"title": "Test Article 2", "published": "2026-01-17"}
        assert generate_item_id(entry1) != generate_item_id(entry2)
