# Handover

## Current Status

- Project initialized as a Git repository on 2026-05-15.
- Greenfield MVP scaffold is implemented and committed as `8a38415 scaffold desktop overlay app`.
- Camera/OCR endpoint slice is committed as `251a9f4 add webcam frame ocr endpoint`.
- Catalog/pricing guard slice is committed as `a5fd507 add card catalog sync and quota guards`.
- OBS source-config helper slice is committed as `85e7e3c add obs browser source helper`.
- GitHub repository created at `https://github.com/ej22/poke-ocr` and local `main` tracks `origin/main`.
- The architecture is a local Python service serving a browser-based OBS overlay and control UI, with an Electron wrapper prepared for desktop packaging.
- Baseline Python tests pass with the stdlib fallback runner.
- Browser webcam capture and `/api/scan/frame` are implemented. The control page supports both one-off **Scan Frame** and continuous **Start Auto Scan** live OCR. The frame endpoint gracefully reports `vision_unavailable` when OpenCV/Tesseract extras are not installed.
- Webcam OCR setup on Windows: install Python vision extras with `python -m pip install -e ".[vision]"`, install Tesseract with `winget install --id UB-Mannheim.TesseractOCR`, reopen PowerShell, verify with `tesseract --version`, then restart the service. Manual installer fallback: `https://github.com/UB-Mannheim/tesseract/wiki`; default PATH folder is `C:\Program Files\Tesseract-OCR`.
- Sample Test Scan can now price high-confidence manually entered cards that are not in the local catalog by creating a temporary `CardIdentity` from typed name, set code, collector number, and language, then using PokéWallet search. Verified scenario: Aurorus, POR, 024/088, English.
- Control UI now includes an **Open Overlay Preview** link in the OBS Browser Source panel; the overlay itself is still served at `/overlay` and must be opened in a browser tab or added to OBS as a Browser Source.
- Webcam OCR now uses explicit Tesseract `--psm`/`--oem` settings per crop, OCR-only crop preprocessing, quad-based card detection, filtered set-code extraction, and filtered card-name extraction.
- Pokémon TCG catalog sync and quota-aware pricing guards are implemented.
- OBS Browser Source configuration helper is implemented.

## Decisions Made

- OBS integration starts with Browser Source instead of a native plugin.
- PokéWallet is the primary pricing provider, with quota tracking and local cache.
- PriceCharting scraping is out of scope for v1.
- Local SQLite stores app settings, card index, price cache, quota state, and scan history.
- `handover.md` is the durable memory file and must be updated before major commits and near 90% context usage.
- Prefixed collector numbers such as `TG05` and `SWSH050` preserve canonical padding; plain numeric numbers such as `020/189` normalize to `20/189`.
- SQLite is opened with `check_same_thread=False` and guarded by a re-entrant lock because the service uses `ThreadingHTTPServer`.
- The first webcam OCR implementation is optional-dependency based: OpenCV locates a likely card rectangle, Tesseract OCR reads top/bottom/full-card crops, and the existing scan engine handles matching/pricing.
- `pytesseract` is only the Python bridge; the separate Tesseract executable must be installed and discoverable on `PATH`.
- Manual/sample scans with confidence >= 0.9 may bypass the local catalog if name, set code, and collector number are present; weak OCR still requires a confident local catalog match.
- Pokémon TCG catalog entries map into the same `CardIdentity` model as sample cards, keeping matcher/overlay contracts stable.
- `PriceService` checks cached prices before quota state, then blocks live PokéWallet calls if hourly or daily remaining quota is zero.
- OBS helper returns the exact Browser Source URL and recommended transparent 1920x1080 settings for manual setup.
- Webcam OCR keeps original frames/crops untouched for card-bound detection, then preprocesses OCR crops with greyscale conversion, 2x cubic upscaling, adaptive Gaussian thresholding, and mild sharpening before Tesseract.
- Tesseract reads the top and bottom crops with single-line mode (`--psm 7 --oem 3`) and the full-card fallback crop with automatic page segmentation (`--psm 3 --oem 3`).
- Card boundary detection now looks for four-point contours with Pokémon-card-like aspect ratio (`1.35`-`1.45`) and area above 8% of the frame. If no card-shaped quad is found, `/api/scan/frame` returns a low-confidence no-bounds OCR result instead of running OCR over the whole frame.
- Set code extraction is constrained to the bottom OCR crop and filters known OCR false positives such as `HP`, `GX`, `EX`, `VMAX`, `VSTAR`, `TAG`, `TEAM`, `FULL`, `CARD`, `ART`, `ITEM`, and `TOOL`.
- Name extraction skips short, numeric, HP, and standalone rarity/noise lines before selecting the first plausible card-name line.

## Files/Areas Created

- `.gitignore` for secrets, local databases, caches, logs, and build outputs.
- `README.md` with quick start and OBS setup notes.
- Python package under `src/codexocr/` with models, normalization, database, matcher, pricing provider, scan engine, and HTTP service.
- Static web UI under `web/` for `/control` and `/overlay`.
- Electron wrapper under `electron/`.
- Tests under `tests/`, including `tests/run_tests.py` for environments without pytest.
- `src/codexocr/vision.py` for data URL parsing and optional OCR analysis.
- `src/codexocr/vision.py` includes OCR helpers `_read_ocr_text`, `_preprocess_region`, `_is_possible_card_name`, bottom-crop-aware `_candidate_from_text`, and quad-based `_find_card_bounds`.
- `src/codexocr/catalog.py` for Pokémon TCG API card sync.
- `/api/scan/frame` endpoint for browser-captured webcam frames.
- `/api/cards/sync` endpoint and control UI form for card index import.
- `/api/obs/source-config` endpoint and control UI JSON display for OBS setup.
- Control UI camera preview, one-off scan-frame controls, and continuous auto-scan controls.
- Control UI Sample Test Scan path for manual card lookup/pricing and overlay preview link for `/overlay`.

## Commands Run

- `git init`
- `python3 -m pytest` failed because pytest is not installed in the base environment.
- `python3 tests/run_tests.py` passed.
- `env PYTHONPATH=src CODEXOCR_PORT=8765 python3 -m codexocr.server` required escalated localhost binding and started successfully.
- `curl -s http://127.0.0.1:8765/api/status` succeeded after the SQLite threading fix.
- `curl -s -X POST http://127.0.0.1:8765/api/scan/simulate ...` succeeded.
- `curl -s -X POST http://127.0.0.1:8765/api/scan/frame ...` returned the expected `vision_unavailable` response because vision extras are not installed.
- `python3 tests/run_tests.py` passed after adding catalog mapping/sync tests and quota-exhaustion pricing tests.
- `python3 tests/run_tests.py` passed after adding OBS source-config tests.
- `python tests\run_tests.py` passed after adding PokéWallet API alignment, `.env` loading, Tesseract error handling, manual-card fallback, and overlay preview changes.
- `python -m compileall src tests` passed after the same changes.
- `node --check web\app.js` passed after adding continuous browser auto-scan controls.
- `python tests\run_tests.py` passed after adding continuous browser auto-scan controls.
- `python3 tests/run_tests.py` passed after adding OCR preprocessing, set-code filtering, name filtering, and no-card-bound synthetic tests. OpenCV/NumPy-specific tests skip cleanly when the optional vision extra is not installed.
- `gh auth login -h github.com --git-protocol https --web` completed successfully for GitHub account `ej22`.
- `gh repo create poke-ocr --private --source . --remote origin --push` created the private repo and pushed `main`.

## Known Issues / Next Steps

- Install/test the live auto-scan flow on a machine with OpenCV and the Tesseract executable available on `PATH`.
- Replace sample catalog with a synced local card index for better camera OCR matching; manual/sample scans can already price non-catalog cards when typed confidently.
- Continue hardening PokeWallet response mapping with more real card responses.
- Add live OBS WebSocket source creation later; current helper is manual Browser Source setup.
