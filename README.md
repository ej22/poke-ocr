# CodexOCR Pokémon Card Overlay

Cross-platform desktop project for scanning Pokémon cards from a webcam and showing live pricing in OBS through a transparent Browser Source overlay.

## Current MVP

- Local Python HTTP/WebSocket-style polling service.
- Static `/control` page for settings, live scan controls, and manual candidate simulation.
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

For webcam OCR, install the optional Python vision packages and the Tesseract OCR desktop app:

```powershell
python -m pip install -e ".[vision]"
```

On Windows, install Tesseract with Winget:

```powershell
winget install --id UB-Mannheim.TesseractOCR
```

Close and reopen PowerShell, then verify Tesseract is on your `PATH`:

```powershell
tesseract --version
```

If that command prints a version, restart the CodexOCR service and webcam OCR can use Tesseract.

If Winget is unavailable, install Tesseract manually from the [UB Mannheim Windows builds](https://github.com/UB-Mannheim/tesseract/wiki). The default install path is usually `C:\Program Files\Tesseract-OCR`; make sure that folder is on your user `PATH`.

Open:

- Control UI: `http://127.0.0.1:8765/control`
- OBS overlay: `http://127.0.0.1:8765/overlay`

## Testing a Card

Use **Sample Test Scan** on the control page to test matching, pricing, and the overlay without webcam OCR. Enter the card name, set code, collector number, and language, then click **Send Sample Scan**.

The bundled catalog includes a few sample cards, but high-confidence manual/sample scans can also price cards that are not yet in the local catalog by asking PokéWallet directly. For example:

```text
Card name: Aurorus
Set code: POR
Collector number: 024/088
Language: en
```

Use **Camera > Start Auto Scan** for live webcam OCR. The control page will keep sending camera frames to the local OCR service at the selected interval until you click **Stop Auto Scan**. Use **Scan Frame** when you only want to test one webcam frame.

## OBS Setup

1. Open the control page.
2. Use **Open Overlay Preview** to confirm the overlay renders in a browser tab.
3. Add a Browser Source in OBS.
4. Set the URL to `http://127.0.0.1:8765/overlay`.
5. Use a transparent background and size it to your canvas.
6. Keep the local service running while streaming or recording.

## Development Rules

- Update `handover.md` before major commits and whenever context approaches 90%.
- Commit coherent milestones.
- Never commit API keys, local SQLite databases, generated caches, logs, or captures.
