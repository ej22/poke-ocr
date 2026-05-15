from __future__ import annotations

import json
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from .database import AppDatabase
from .scanner import ScanEngine
from .vision import VisionUnavailable, analyze_frame_data_url

ROOT = Path(__file__).resolve().parents[2]
WEB_ROOT = ROOT / "web"


class AppState:
    def __init__(self) -> None:
        self.database = AppDatabase()
        self.scanner = ScanEngine(self.database)


STATE = AppState()


class Handler(BaseHTTPRequestHandler):
    server_version = "CodexOCR/0.1"

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/":
            self._redirect("/control")
        elif path == "/control":
            self._serve_file("control.html", "text/html")
        elif path == "/overlay":
            self._serve_file("overlay.html", "text/html")
        elif path == "/static/app.css":
            self._serve_file("app.css", "text/css")
        elif path == "/static/app.js":
            self._serve_file("app.js", "application/javascript")
        elif path == "/static/overlay.js":
            self._serve_file("overlay.js", "application/javascript")
        elif path == "/api/status":
            self._json(
                {
                    "scan": STATE.scanner.current.to_dict(),
                    "settings": _public_settings(),
                    "quota": _quota_dict(),
                    "cards": [card.to_dict() for card in STATE.database.list_cards()],
                }
            )
        else:
            self._json({"error": "Not found"}, HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        payload = self._read_json()
        if path == "/api/settings":
            allowed = {"pokewallet_api_key", "currency", "camera_id", "overlay_layout", "confidence_threshold"}
            for key, value in payload.items():
                if key in allowed:
                    STATE.database.set_setting(key, value)
            self._json({"ok": True, "settings": _public_settings()})
        elif path == "/api/scan/pause":
            self._json({"scan": STATE.scanner.pause().to_dict()})
        elif path == "/api/scan/resume":
            self._json({"scan": STATE.scanner.resume().to_dict()})
        elif path == "/api/scan/simulate":
            self._json({"scan": STATE.scanner.ingest_ocr(payload).to_dict()})
        elif path == "/api/scan/frame":
            try:
                result = analyze_frame_data_url(str(payload.get("image") or ""))
                scan = STATE.scanner.ingest_ocr(
                    {
                        "name": result.candidate.name,
                        "set_code": result.candidate.set_code,
                        "collector_number": result.candidate.collector_number,
                        "language": result.candidate.language,
                        "confidence": result.candidate.confidence,
                        "ocr_text": result.ocr_text,
                        "source": "webcam",
                    }
                )
                self._json({"scan": scan.to_dict(), "vision": {"card_bounds": result.card_bounds}})
            except VisionUnavailable as exc:
                STATE.scanner.current = STATE.scanner.current.__class__(
                    state="vision_unavailable",
                    message=str(exc),
                )
                self._json({"scan": STATE.scanner.current.to_dict(), "error": str(exc)}, HTTPStatus.SERVICE_UNAVAILABLE)
            except (ValueError, TypeError) as exc:
                self._json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        else:
            self._json({"error": "Not found"}, HTTPStatus.NOT_FOUND)

    def log_message(self, format: str, *args: object) -> None:
        return

    def _read_json(self) -> dict[str, object]:
        length = int(self.headers.get("content-length") or 0)
        if length == 0:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def _serve_file(self, filename: str, content_type: str) -> None:
        path = WEB_ROOT / filename
        if not path.exists():
            self._json({"error": f"Missing {filename}"}, HTTPStatus.NOT_FOUND)
            return
        body = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _redirect(self, location: str) -> None:
        self.send_response(HTTPStatus.FOUND)
        self.send_header("Location", location)
        self.end_headers()

    def _json(self, payload: dict[str, object], status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def _public_settings() -> dict[str, object]:
    api_key = STATE.database.get_setting("pokewallet_api_key")
    return {
        "pokewallet_api_key_configured": bool(api_key),
        "currency": STATE.database.get_setting("currency", "USD"),
        "camera_id": STATE.database.get_setting("camera_id", "default"),
        "overlay_layout": STATE.database.get_setting("overlay_layout", "lower-third"),
        "confidence_threshold": STATE.database.get_setting("confidence_threshold", 0.68),
    }


def _quota_dict() -> dict[str, object] | None:
    quota = STATE.database.get_quota("pokewallet")
    return quota.to_dict() if quota else None


def main() -> None:
    host = os.getenv("CODEXOCR_HOST", "127.0.0.1")
    port = int(os.getenv("CODEXOCR_PORT", "8765"))
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"CodexOCR service running at http://{host}:{port}/control")
    server.serve_forever()


if __name__ == "__main__":
    main()
