# CodexOCR Pokémon Card Overlay

Cross-platform desktop project for scanning Pokémon cards from a webcam and showing live pricing in OBS through a transparent Browser Source overlay.

## Current MVP

- Local Python HTTP/WebSocket-style polling service.
- Static `/control` page for settings, scan controls, and manual candidate simulation.
- Transparent `/overlay` page suitable for OBS Browser Source.
- SQLite-backed settings, card index, price cache, quota state, and scan history.
- PokéWallet provider with quota tracking and cache-first lookups.
- OCR/card matching modules with deterministic tests.

## Quick Start

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
python -m codexocr.server
```

Open:

- Control UI: `http://127.0.0.1:8765/control`
- OBS overlay: `http://127.0.0.1:8765/overlay`

## OBS Setup

1. Add a Browser Source.
2. Set the URL to `http://127.0.0.1:8765/overlay`.
3. Use a transparent background and size it to your canvas.
4. Keep the local service running while streaming or recording.

## Development Rules

- Update `handover.md` before major commits and whenever context approaches 90%.
- Commit coherent milestones.
- Never commit API keys, local SQLite databases, generated caches, logs, or captures.
