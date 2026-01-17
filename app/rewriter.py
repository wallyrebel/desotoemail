"""
Article rewriter for DeSoto Email RSS Digest.
Rewrites articles in AP style using OpenAI.
"""

import logging
import re
from typing import Optional, Dict

from app.openai_client import OpenAIClient

logger = logging.getLogger(__name__)

# ============================================================================
# AP-STYLE REWRITING PROMPT
# ============================================================================
# This prompt is designed to produce AP-style news articles.
# It can be modified as needed.

AP_STYLE_SYSTEM_PROMPT = """You are an experienced AP-style news editor. Your job is to rewrite news articles following these strict guidelines:

## AP STYLE REQUIREMENTS:
1. **Neutral, factual tone** - No editorializing, opinions, or biased language
2. **Lead paragraph** - Start with the most important facts (who, what, when, where, why)
3. **Attribution** - Use phrases like "according to [source]" when appropriate
4. **Concise writing** - Short sentences, active voice, no unnecessary words
5. **No verbatim copying** - Paraphrase; avoid long phrases from the original
6. **Structure** - 3-8 short paragraphs, most important information first
7. **Professional language** - Avoid sensationalism, clickbait, or informal tone

## OUTPUT FORMAT:
You must return your response in this exact format (including the markers):

HEADLINE: [Your AP-style headline - concise, factual, no clickbait]

TEASER: [2-3 sentence summary of the key points]

BODY:
[Your 3-8 paragraph AP-style article]

SOURCE: [The exact source line provided in the input]

Important: The SOURCE line must appear exactly as provided - do not modify it."""

AP_STYLE_USER_PROMPT_TEMPLATE = """Please rewrite the following article in AP style.

SOURCE NAME: {source_name}
ORIGINAL URL: {url}
ORIGINAL TITLE: {title}

ORIGINAL CONTENT:
{content}

Remember to end with this exact source line:
Source: {source_name} — {url}"""


def build_rewrite_messages(
    source_name: str,
    url: str,
    title: str,
    content: str
) -> list:
    """
    Build the message list for OpenAI rewriting request.
    """
    user_message = AP_STYLE_USER_PROMPT_TEMPLATE.format(
        source_name=source_name,
        url=url,
        title=title,
        content=content
    )
    
    return [
        {"role": "system", "content": AP_STYLE_SYSTEM_PROMPT},
        {"role": "user", "content": user_message}
    ]


def parse_rewrite_response(response: str, source_name: str, url: str) -> Optional[Dict]:
    """
    Parse the structured response from OpenAI into components.
    
    Returns a dict with:
    - headline
    - body
    - short_teaser
    - source_line
    
    Returns None if parsing fails.
    """
    if not response:
        return None
    
    try:
        # Extract headline
        headline_match = re.search(r"HEADLINE:\s*(.+?)(?=\n|TEASER:)", response, re.DOTALL)
        headline = headline_match.group(1).strip() if headline_match else ""
        
        # Extract teaser
        teaser_match = re.search(r"TEASER:\s*(.+?)(?=\n\n|BODY:)", response, re.DOTALL)
        teaser = teaser_match.group(1).strip() if teaser_match else ""
        
        # Extract body
        body_match = re.search(r"BODY:\s*(.+?)(?=SOURCE:|$)", response, re.DOTALL)
        body = body_match.group(1).strip() if body_match else ""
        
        # Build source line (ensure it's correct)
        source_line = f"Source: {source_name} — {url}"
        
        # Validate we got the essential parts
        if not headline:
            logger.warning("Failed to extract headline from response")
            # Try to use first line as headline
            lines = response.strip().split("\n")
            headline = lines[0] if lines else "Untitled"
        
        if not body:
            logger.warning("Failed to extract body from response")
            # Use the whole response as body
            body = response
        
        if not teaser:
            # Generate teaser from body (first 2 sentences)
            sentences = re.split(r'(?<=[.!?])\s+', body)
            teaser = " ".join(sentences[:2]) if sentences else body[:200]
        
        return {
            "headline": headline,
            "body": body,
            "short_teaser": teaser,
            "source_line": source_line,
        }
        
    except Exception as e:
        logger.error(f"Failed to parse rewrite response: {e}")
        return None


def rewrite_article(
    client: OpenAIClient,
    source_name: str,
    url: str,
    title: str,
    content: str
) -> Optional[Dict]:
    """
    Rewrite an article in AP style.
    
    Args:
        client: OpenAI client instance
        source_name: Name of the source/feed
        url: Original article URL
        title: Original article title
        content: Clean text content (should already be truncated if needed)
    
    Returns:
        Dict with headline, body, short_teaser, source_line
        or None if rewriting fails
    """
    if not content or len(content.strip()) < 50:
        logger.warning(f"Content too short to rewrite: {title[:50]}")
        # Return minimal rewrite
        return {
            "headline": title,
            "body": content or "No content available.",
            "short_teaser": content[:200] if content else "No content available.",
            "source_line": f"Source: {source_name} — {url}",
        }
    
    logger.info(f"Rewriting article: {title[:50]}...")
    
    messages = build_rewrite_messages(source_name, url, title, content)
    
    response = client.complete(
        messages=messages,
        temperature=0.7,
        max_tokens=2000
    )
    
    if not response:
        logger.error(f"Failed to get response for: {title[:50]}")
        return None
    
    result = parse_rewrite_response(response, source_name, url)
    
    if result:
        logger.info(f"Successfully rewrote: {result['headline'][:50]}")
    
    return result


def rewrite_batch(
    client: OpenAIClient,
    articles: list,
    max_failures: int = 3
) -> list:
    """
    Rewrite a batch of articles.
    
    Args:
        client: OpenAI client
        articles: List of prepared article dicts (from content_extractor)
        max_failures: Maximum consecutive failures before stopping
    
    Returns:
        List of successfully rewritten articles with all fields
    """
    results = []
    consecutive_failures = 0
    
    for article in articles:
        result = rewrite_article(
            client=client,
            source_name=article["source_name"],
            url=article["url"],
            title=article["title"],
            content=article["clean_content"],
        )
        
        if result:
            # Add image and original metadata
            result["featured_image_url"] = article.get("featured_image_url")
            result["original_url"] = article["url"]
            result["original_title"] = article["title"]
            results.append(result)
            consecutive_failures = 0
        else:
            consecutive_failures += 1
            logger.warning(
                f"Failed to rewrite article ({consecutive_failures}/{max_failures}): "
                f"{article['title'][:50]}"
            )
            
            if consecutive_failures >= max_failures:
                logger.error(
                    f"Too many consecutive failures ({max_failures}), stopping batch"
                )
                break
    
    logger.info(f"Rewrote {len(results)}/{len(articles)} articles")
    return results
