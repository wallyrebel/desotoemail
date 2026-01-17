# DeSoto Email RSS Digest

A production-reliable automated RSS digest system that reads RSS feeds, rewrites articles in AP style using OpenAI, and sends a daily email digest via Gmail SMTP.

## Features

- **Multi-feed support**: Configure multiple RSS/Atom feeds in `feeds.yml`
- **AP-style rewriting**: Articles rewritten using OpenAI (gpt-5-mini with gpt-4.1-nano fallback)
- **Featured image extraction**: Automatically extracts images from RSS or article pages
- **Deduplication**: Tracks processed articles to prevent duplicate sends
- **Chicago timezone aware**: Sends at 5 PM Chicago time, handles DST correctly
- **Reliable**: Automatic retries, exponential backoff, graceful error handling
- **GitHub Actions**: Fully automated via scheduled workflow

## Quick Start

### 1. Clone the repository

```bash
git clone https://github.com/wallyrebel/desotoemail.git
cd desotoemail
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure feeds

Edit `feeds.yml` to add your RSS feeds:

```yaml
feeds:
  - name: "Your News Source"
    url: "https://example.com/feed.xml"
    category: "local"
```

### 4. Set up environment variables

```bash
# Required
export OPENAI_API_KEY="sk-..."
export GMAIL_USER="your@gmail.com"
export GMAIL_APP_PASSWORD="xxxx xxxx xxxx xxxx"
export RECIPIENTS="email1@example.com,email2@example.com"

# Optional
export DRY_RUN="true"  # Test without sending emails
export NO_NEWS_BEHAVIOR="skip"  # or "send_empty"
```

### 5. Run locally

```bash
python -m app.main
```

## Gmail App Password Setup

Gmail requires an **App Password** for SMTP authentication:

1. **Enable 2-Step Verification**:
   - Go to [Google Account Security](https://myaccount.google.com/security)
   - Click "2-Step Verification" and follow the setup

2. **Create App Password**:
   - Go to [App Passwords](https://myaccount.google.com/apppasswords)
   - Select "Mail" and "Windows Computer" (or any)
   - Click "Generate"
   - Copy the 16-character password (format: `xxxx xxxx xxxx xxxx`)

3. **Use in Environment**:
   ```bash
   export GMAIL_APP_PASSWORD="xxxx xxxx xxxx xxxx"  # Keep the spaces
   ```

## GitHub Actions Setup

### 1. Add Secrets

Go to your repo → Settings → Secrets and variables → Actions → New repository secret:

| Secret Name | Value |
|-------------|-------|
| `OPENAI_API_KEY` | Your OpenAI API key |
| `GMAIL_USER` | Your Gmail address |
| `GMAIL_APP_PASSWORD` | Your Gmail App Password |
| `RECIPIENTS` | Comma-separated recipient emails |

### 2. (Optional) Add Variables

Settings → Secrets and variables → Actions → Variables tab:

| Variable Name | Value | Description |
|---------------|-------|-------------|
| `DRY_RUN` | `false` | Set to `true` to test without sending |
| `NO_NEWS_BEHAVIOR` | `skip` | `skip` or `send_empty` |

### 3. Workflow triggers

The workflow runs:
- **Every 30 minutes** (cron schedule in UTC)
- **Manually** via "Run workflow" button

The script checks if it's 5 PM Chicago time before sending.

## State Management

The `state.json` file tracks:
- **processed_ids**: Articles already sent (by feed URL)
- **last_sent_date**: Last date a digest was sent

```json
{
  "processed_ids": {
    "https://example.com/feed.xml": ["id1", "id2"]
  },
  "last_sent_date": "2026-01-17"
}
```

This file is automatically committed back to the repo by GitHub Actions.

## Testing

Run the test suite:

```bash
pytest tests/ -v
```

Run with coverage:

```bash
pytest tests/ -v --cov=app --cov-report=term-missing
```

## Project Structure

```
├── app/
│   ├── __init__.py
│   ├── main.py              # Entrypoint & orchestration
│   ├── config.py            # Configuration & env vars
│   ├── rss_reader.py        # RSS/Atom parsing
│   ├── content_extractor.py # HTML cleanup & image extraction
│   ├── openai_client.py     # OpenAI API wrapper
│   ├── rewriter.py          # AP-style rewriting
│   ├── emailer.py           # Email composition & SMTP
│   ├── state_store.py       # Persistence
│   └── utils.py             # Helpers
├── tests/
│   ├── test_dedupe.py
│   ├── test_time_filter.py
│   ├── test_rss_parsing.py
│   └── test_image_extraction.py
├── .github/workflows/
│   └── daily_digest.yml
├── feeds.yml
├── state.json
├── requirements.txt
└── README.md
```

## Configuration Options

| Environment Variable | Required | Default | Description |
|---------------------|----------|---------|-------------|
| `OPENAI_API_KEY` | Yes | - | OpenAI API key |
| `GMAIL_USER` | Yes | - | Gmail address |
| `GMAIL_APP_PASSWORD` | Yes | - | Gmail App Password |
| `RECIPIENTS` | Yes | - | Comma-separated emails |
| `DRY_RUN` | No | `false` | Skip actual email sending |
| `NO_NEWS_BEHAVIOR` | No | `skip` | `skip` or `send_empty` |
| `OPENAI_MODEL` | No | `gpt-5-mini` | Primary OpenAI model |

## Troubleshooting

### "Authentication failed" error
- Verify Gmail App Password is correct (16 chars with spaces)
- Ensure 2-Step Verification is enabled on your Google account
- Check GMAIL_USER matches the account with the App Password

### "No new items" every run
- Check your feeds are returning recent items (within 24 hours)
- Verify feed URLs are accessible
- Check `state.json` for already-processed IDs

### OpenAI API errors
- Verify API key is valid and has credits
- Check for rate limiting (the script retries automatically)
- Primary model falls back to gpt-4.1-nano on failure

### Workflow not running
- Check Actions tab for workflow status
- Verify secrets are correctly named
- Manually trigger with "Run workflow" to test

## License

MIT
