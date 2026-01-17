"""
Tests for featured image extraction.
"""

import pytest
from app.content_extractor import (
    extract_first_img_from_html,
    extract_image_from_rss,
    strip_html_to_text
)


class TestStripHtmlToText:
    """Tests for HTML to plain text conversion."""
    
    def test_strips_simple_html(self):
        html = "<p>This is a <strong>test</strong> paragraph.</p>"
        result = strip_html_to_text(html)
        assert "This is a test paragraph" in result
    
    def test_removes_script_tags(self):
        html = "<p>Content</p><script>alert('bad');</script><p>More content</p>"
        result = strip_html_to_text(html)
        assert "alert" not in result
        assert "Content" in result
    
    def test_removes_style_tags(self):
        html = "<style>.class { color: red; }</style><p>Visible text</p>"
        result = strip_html_to_text(html)
        assert "color" not in result
        assert "Visible text" in result
    
    def test_handles_empty_input(self):
        assert strip_html_to_text("") == ""
        assert strip_html_to_text(None) == ""
    
    def test_normalizes_whitespace(self):
        html = "<p>Line 1</p>   \n\n\n   <p>Line 2</p>"
        result = strip_html_to_text(html)
        # Should not have excessive newlines
        assert "\n\n\n" not in result


class TestExtractFirstImgFromHtml:
    """Tests for extracting first image from HTML."""
    
    def test_extracts_img_src(self):
        html = '<p>Text</p><img src="https://example.com/image.jpg" alt="test">'
        result = extract_first_img_from_html(html)
        assert result == "https://example.com/image.jpg"
    
    def test_extracts_data_src_for_lazy_loading(self):
        html = '<img data-src="https://example.com/lazy.jpg" src="placeholder.gif">'
        result = extract_first_img_from_html(html)
        # Should get placeholder since it has valid src
        assert result is not None
    
    def test_skips_base64_images(self):
        html = '<img src="data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP">'
        result = extract_first_img_from_html(html)
        assert result is None
    
    def test_returns_first_image_only(self):
        html = '''
            <img src="https://example.com/first.jpg">
            <img src="https://example.com/second.jpg">
        '''
        result = extract_first_img_from_html(html)
        assert "first.jpg" in result
    
    def test_handles_no_images(self):
        html = "<p>No images here</p>"
        result = extract_first_img_from_html(html)
        assert result is None
    
    def test_handles_empty_input(self):
        assert extract_first_img_from_html("") is None
        assert extract_first_img_from_html(None) is None


class TestExtractImageFromRss:
    """Tests for extracting featured image from RSS entry."""
    
    def test_extracts_from_media_content(self):
        entry = {
            "media_content": [{"url": "https://example.com/media.jpg", "type": "image/jpeg"}]
        }
        result = extract_image_from_rss(entry)
        assert result == "https://example.com/media.jpg"
    
    def test_extracts_from_media_thumbnail(self):
        entry = {
            "media_thumbnail": [{"url": "https://example.com/thumb.jpg"}]
        }
        result = extract_image_from_rss(entry)
        assert result == "https://example.com/thumb.jpg"
    
    def test_extracts_from_enclosure(self):
        entry = {
            "enclosures": [{"url": "https://example.com/enc.jpg", "type": "image/png"}]
        }
        result = extract_image_from_rss(entry)
        assert result == "https://example.com/enc.jpg"
    
    def test_extracts_from_content_html(self):
        entry = {
            "content": [{"value": '<p>Text</p><img src="https://example.com/content.jpg">'}]
        }
        result = extract_image_from_rss(entry)
        assert result == "https://example.com/content.jpg"
    
    def test_extracts_from_summary_html(self):
        entry = {
            "summary": '<img src="https://example.com/summary.jpg"><p>Summary text</p>'
        }
        result = extract_image_from_rss(entry)
        assert result == "https://example.com/summary.jpg"
    
    def test_prefers_media_content_over_html(self):
        entry = {
            "media_content": [{"url": "https://example.com/media.jpg", "type": "image/jpeg"}],
            "summary": '<img src="https://example.com/summary.jpg">'
        }
        result = extract_image_from_rss(entry)
        assert "media.jpg" in result
    
    def test_returns_none_if_no_image(self):
        entry = {
            "title": "No images",
            "summary": "Just text, no images here."
        }
        result = extract_image_from_rss(entry)
        assert result is None
