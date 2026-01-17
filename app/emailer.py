"""
Email composition and sending for DeSoto Email RSS Digest.
Sends HTML + plaintext emails via Gmail SMTP.
"""

import logging
import smtplib
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
from typing import List, Dict, Optional

from app.config import CHICAGO_TZ, SMTP_SERVER, SMTP_PORT, SMTP_MAX_RETRIES

logger = logging.getLogger(__name__)


def compose_html_email(articles: List[Dict], date_str: str) -> str:
    """
    Compose the HTML body of the email digest.
    
    Args:
        articles: List of rewritten article dicts
        date_str: Date string for the digest (YYYY-MM-DD)
    
    Returns:
        HTML string for the email body
    """
    html_parts = [
        """<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {
            font-family: Georgia, 'Times New Roman', serif;
            line-height: 1.6;
            color: #333;
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f9f9f9;
        }
        .header {
            background-color: #1a1a2e;
            color: white;
            padding: 20px;
            text-align: center;
            border-radius: 8px 8px 0 0;
        }
        .header h1 {
            margin: 0;
            font-size: 24px;
        }
        .header p {
            margin: 5px 0 0;
            opacity: 0.8;
            font-size: 14px;
        }
        .content {
            background-color: white;
            padding: 20px;
            border-radius: 0 0 8px 8px;
        }
        .article {
            margin-bottom: 30px;
            padding-bottom: 25px;
            border-bottom: 1px solid #eee;
        }
        .article:last-child {
            border-bottom: none;
            margin-bottom: 0;
        }
        .article h2 {
            font-size: 20px;
            margin: 0 0 10px;
            color: #1a1a2e;
        }
        .article h2 a {
            color: #1a1a2e;
            text-decoration: none;
        }
        .article h2 a:hover {
            text-decoration: underline;
        }
        .article-image {
            max-width: 100%;
            height: auto;
            border-radius: 4px;
            margin: 10px 0;
        }
        .teaser {
            font-size: 16px;
            color: #555;
            margin-bottom: 10px;
        }
        .body {
            font-size: 15px;
            color: #333;
        }
        .body p {
            margin: 0 0 12px;
        }
        .source {
            font-size: 13px;
            color: #777;
            font-style: italic;
            margin-top: 15px;
        }
        .read-more {
            display: inline-block;
            margin-top: 10px;
            color: #0066cc;
            text-decoration: none;
            font-weight: bold;
        }
        .read-more:hover {
            text-decoration: underline;
        }
        .footer {
            text-align: center;
            font-size: 12px;
            color: #999;
            margin-top: 20px;
            padding-top: 20px;
            border-top: 1px solid #eee;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>📰 Daily RSS Digest</h1>
        <p>""" + date_str + """ • DeSoto County</p>
    </div>
    <div class="content">
"""
    ]
    
    for article in articles:
        html_parts.append('<div class="article">')
        
        # Headline
        headline = article.get("headline", article.get("original_title", "Untitled"))
        url = article.get("original_url", "")
        html_parts.append(f'<h2><a href="{url}">{headline}</a></h2>')
        
        # Featured image (only if present)
        image_url = article.get("featured_image_url")
        if image_url:
            html_parts.append(
                f'<img src="{image_url}" alt="" class="article-image" '
                f'style="max-width: 100%; max-height: 300px; object-fit: cover;">'
            )
        
        # Teaser
        teaser = article.get("short_teaser", "")
        if teaser:
            html_parts.append(f'<p class="teaser">{teaser}</p>')
        
        # Body (convert newlines to paragraphs)
        body = article.get("body", "")
        if body:
            paragraphs = body.split("\n\n")
            html_parts.append('<div class="body">')
            for para in paragraphs[:5]:  # Limit to first 5 paragraphs in email
                para = para.strip()
                if para:
                    html_parts.append(f'<p>{para}</p>')
            html_parts.append('</div>')
        
        # Source line
        source_line = article.get("source_line", "")
        if source_line:
            html_parts.append(f'<p class="source">{source_line}</p>')
        
        # Read more link
        if url:
            html_parts.append(f'<a href="{url}" class="read-more">Read original →</a>')
        
        html_parts.append('</div>')
    
    html_parts.append("""
    </div>
    <div class="footer">
        <p>This digest was automatically compiled from your RSS feeds.</p>
        <p>DeSoto Email Digest</p>
    </div>
</body>
</html>
""")
    
    return "".join(html_parts)


def compose_plain_text_email(articles: List[Dict], date_str: str) -> str:
    """
    Compose the plain text body of the email digest.
    """
    parts = [
        f"DAILY RSS DIGEST — {date_str}",
        "=" * 50,
        "",
    ]
    
    for i, article in enumerate(articles, 1):
        headline = article.get("headline", article.get("original_title", "Untitled"))
        url = article.get("original_url", "")
        teaser = article.get("short_teaser", "")
        body = article.get("body", "")
        source_line = article.get("source_line", "")
        
        parts.append(f"{i}. {headline}")
        parts.append("-" * 40)
        
        if teaser:
            parts.append(teaser)
            parts.append("")
        
        if body:
            # Use first 2 paragraphs in plain text
            paragraphs = body.split("\n\n")[:2]
            for para in paragraphs:
                parts.append(para.strip())
                parts.append("")
        
        if source_line:
            parts.append(source_line)
        
        if url:
            parts.append(f"Read more: {url}")
        
        parts.append("")
        parts.append("")
    
    parts.append("=" * 50)
    parts.append("This digest was automatically compiled from your RSS feeds.")
    
    return "\n".join(parts)


def compose_no_news_email(date_str: str) -> tuple:
    """
    Compose a "no news" email when NO_NEWS_BEHAVIOR is send_empty.
    Returns (html, plain_text) tuple.
    """
    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{ font-family: Georgia, serif; max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background-color: #1a1a2e; color: white; padding: 20px; text-align: center; }}
        .content {{ padding: 20px; text-align: center; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>📰 Daily RSS Digest</h1>
        <p>{date_str}</p>
    </div>
    <div class="content">
        <p>No new articles were published in the last 24 hours.</p>
        <p>Check back tomorrow!</p>
    </div>
</body>
</html>
"""
    
    plain = f"""DAILY RSS DIGEST — {date_str}
{'=' * 50}

No new articles were published in the last 24 hours.
Check back tomorrow!
"""
    
    return html, plain


def send_email(
    gmail_user: str,
    gmail_app_password: str,
    recipients: List[str],
    subject: str,
    html_body: str,
    plain_body: str,
    dry_run: bool = False
) -> bool:
    """
    Send an email via Gmail SMTP.
    
    Args:
        gmail_user: Gmail address
        gmail_app_password: Gmail App Password
        recipients: List of recipient email addresses
        subject: Email subject
        html_body: HTML email body
        plain_body: Plain text email body
        dry_run: If True, don't actually send
    
    Returns:
        True if sent successfully, False otherwise
    """
    if dry_run:
        logger.info(f"DRY_RUN: Would send email to {recipients}")
        logger.info(f"DRY_RUN: Subject: {subject}")
        logger.info(f"DRY_RUN: HTML body length: {len(html_body)} chars")
        return True
    
    # Create message
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = gmail_user
    msg["To"] = ", ".join(recipients)
    
    # Attach both plain text and HTML versions
    part1 = MIMEText(plain_body, "plain", "utf-8")
    part2 = MIMEText(html_body, "html", "utf-8")
    
    msg.attach(part1)
    msg.attach(part2)  # HTML is preferred if client supports it
    
    # Send with retry
    for attempt in range(SMTP_MAX_RETRIES):
        try:
            with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
                server.login(gmail_user, gmail_app_password)
                server.sendmail(gmail_user, recipients, msg.as_string())
            
            logger.info(f"Email sent successfully to {recipients}")
            return True
            
        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"SMTP authentication failed: {e}")
            logger.error("Check GMAIL_USER and GMAIL_APP_PASSWORD")
            return False  # Don't retry auth failures
            
        except smtplib.SMTPException as e:
            logger.warning(
                f"SMTP error (attempt {attempt + 1}/{SMTP_MAX_RETRIES}): {e}"
            )
            if attempt < SMTP_MAX_RETRIES - 1:
                wait_time = 5 * (2 ** attempt)
                logger.info(f"Retrying in {wait_time}s...")
                time.sleep(wait_time)
            
        except Exception as e:
            logger.error(f"Unexpected error sending email: {e}")
            return False
    
    logger.error(f"Failed to send email after {SMTP_MAX_RETRIES} attempts")
    return False


def send_digest(
    config: dict,
    articles: List[Dict],
    date_str: str,
    no_news_behavior: str = "skip"
) -> tuple:
    """
    Send the daily digest email.
    
    Returns:
        (sent: bool, reason: str)
    """
    recipients = config["recipients"]
    
    if not articles:
        if no_news_behavior == "send_empty":
            logger.info("No articles, sending 'no news' email")
            html, plain = compose_no_news_email(date_str)
            subject = f"Daily RSS Digest — {date_str} (No New Items)"
            
            success = send_email(
                gmail_user=config["gmail_user"],
                gmail_app_password=config["gmail_app_password"],
                recipients=recipients,
                subject=subject,
                html_body=html,
                plain_body=plain,
                dry_run=config["dry_run"]
            )
            return success, "no articles (sent empty notice)"
        else:
            logger.info("No articles to send, skipping digest")
            return False, "no articles (skipped)"
    
    # Compose email
    html_body = compose_html_email(articles, date_str)
    plain_body = compose_plain_text_email(articles, date_str)
    subject = f"Daily RSS Digest — {date_str}"
    
    # Send
    success = send_email(
        gmail_user=config["gmail_user"],
        gmail_app_password=config["gmail_app_password"],
        recipients=recipients,
        subject=subject,
        html_body=html_body,
        plain_body=plain_body,
        dry_run=config["dry_run"]
    )
    
    if success:
        return True, f"sent {len(articles)} articles"
    else:
        return False, "send failed"
