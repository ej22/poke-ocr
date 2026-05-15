# Handover

## Current Status

- Project initialized as a Git repository on 2026-05-15.
- Greenfield MVP scaffold is implemented and committed as `8a38415 scaffold desktop overlay app`.
- The architecture is a local Python service serving a browser-based OBS overlay and control UI, with an Electron wrapper prepared for desktop packaging.
- Baseline Python tests pass with the stdlib fallback runner.
- Browser webcam capture and `/api/scan/frame` are implemented. The frame endpoint gracefully reports `vision_unavailable` when OpenCV/Tesseract extras are not installed.

## Decisions Made

- OBS integration starts with Browser Source instead of a native plugin.
- PokéWallet is the primary pricing provider, with quota tracking and local cache.
- PriceCharting scraping is out of scope for v1.
- Local SQLite stores app settings, card index, price cache, quota state, and scan history.
- `handover.md` is the durable memory file and must be updated before major commits and near 90% context usage.
- Prefixed collector numbers such as `TG05` and `SWSH050` preserve canonical padding; plain numeric numbers such as `020/189` normalize to `20/189`.
- SQLite is opened with `check_same_thread=False` and guarded by a re-entrant lock because the service uses `ThreadingHTTPServer`.
- The first webcam OCR implementation is optional-dependency based: OpenCV locates a likely card rectangle, Tesseract OCR reads top/bottom/full-card crops, and the existing scan engine handles matching/pricing.

## Files/Areas Created

- `.gitignore` for secrets, local databases, caches, logs, and build outputs.
- `README.md` with quick start and OBS setup notes.
- Python package under `src/codexocr/` with models, normalization, database, matcher, pricing provider, scan engine, and HTTP service.
- Static web UI under `web/` for `/control` and `/overlay`.
- Electron wrapper under `electron/`.
- Tests under `tests/`, including `tests/run_tests.py` for environments without pytest.
- `src/codexocr/vision.py` for data URL parsing and optional OCR analysis.
- `/api/scan/frame` endpoint for browser-captured webcam frames.
- Control UI camera preview and scan-frame controls.

## Commands Run

- `git init`
- `python3 -m pytest` failed because pytest is not installed in the base environment.
- `python3 tests/run_tests.py` passed.
- `env PYTHONPATH=src CODEXOCR_PORT=8765 python3 -m codexocr.server` required escalated localhost binding and started successfully.
- `curl -s http://127.0.0.1:8765/api/status` succeeded after the SQLite threading fix.
- `curl -s -X POST http://127.0.0.1:8765/api/scan/simulate ...` succeeded.
- `curl -s -X POST http://127.0.0.1:8765/api/scan/frame ...` returned the expected `vision_unavailable` response because vision extras are not installed.

## Known Issues / Next Steps

- Commit the camera/OCR endpoint slice.
- Install/test the `vision` extra on a machine with OpenCV/Tesseract available.
- Replace sample catalog with a synced local card index.
- Add robust PokéWallet response mapping once real API responses are available.
- Add OBS WebSocket setup helper.
