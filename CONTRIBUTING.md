# Contributing

Thanks for considering a contribution.

## Development setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
pytest -q
node --check app/static/app.js
```

## Pull requests

Please keep pull requests focused and include:

- a clear description of the problem
- the reason for the chosen solution
- tests for importer/backend changes when practical
- screenshots for meaningful UI changes

## Telegram fixtures

Never commit a real Telegram export.

Tests that exercise Telegram parsing must use synthetic or fully sanitized fixtures. Remove personal names, usernames, phone numbers, private message content, media, and metadata not needed by the test.

## Style

The project intentionally avoids unnecessary infrastructure. Prefer small, understandable changes over adding services or frameworks without a clear benefit.
