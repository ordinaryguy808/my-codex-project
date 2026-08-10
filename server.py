"""Development web server for the Tappr landing page and NFC redirects."""

import argparse
import json
import mimetypes
import sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

from cards import SQLiteCardRepository


PROJECT_ROOT = Path(__file__).resolve().parent
PUBLIC_FILES = {
    "/": "index.html",
    "/index.html": "index.html",
    "/styles.css": "styles.css",
    "/script.js": "script.js",
    "/admin": "admin.html",
    "/admin.html": "admin.html",
    "/admin.css": "admin.css",
    "/admin.js": "admin.js",
}


class TapprRequestHandler(BaseHTTPRequestHandler):
    repository: SQLiteCardRepository

    def do_GET(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler
        path = urlparse(self.path).path
        if path == "/api/cards":
            self._send_json([self._serialize_card(card) for card in self.repository.list_cards()])
            return
        if path.startswith("/t/"):
            self._handle_card_tap(unquote(path.removeprefix("/t/")))
            return
        self._serve_public_file(path)

    def do_POST(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler
        if urlparse(self.path).path != "/api/cards":
            self.send_error(404, "Page not found")
            return
        payload = self._read_json()
        if payload is None:
            return
        required = ("card_id", "customer_name", "destination_url")
        if any(not str(payload.get(field, "")).strip() for field in required):
            self._send_json({"error": "Card ID, customer name, and destination URL are required."}, 400)
            return
        try:
            card = self.repository.create_card(
                str(payload["card_id"]).strip(),
                str(payload["customer_name"]).strip(),
                str(payload["destination_url"]).strip(),
                bool(payload.get("active", True)),
            )
        except ValueError as error:
            self._send_json({"error": str(error)}, 400)
            return
        except sqlite3.IntegrityError:
            self._send_json({"error": "That card ID already exists."}, 409)
            return
        self._send_json(self._serialize_card(card), 201)

    def do_PATCH(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler
        path = urlparse(self.path).path
        if not path.startswith("/api/cards/"):
            self.send_error(404, "Page not found")
            return
        card_id = unquote(path.removeprefix("/api/cards/"))
        payload = self._read_json()
        if payload is None:
            return
        if self.repository.get_card_by_card_id(card_id) is None:
            self._send_json({"error": "Card not found."}, 404)
            return
        try:
            if "customer_name" in payload:
                self.repository.update_customer_name(card_id, str(payload["customer_name"]).strip())
            if "destination_url" in payload:
                self.repository.update_destination_url(card_id, str(payload["destination_url"]).strip())
            if "active" in payload:
                self.repository.set_active(card_id, bool(payload["active"]))
        except ValueError as error:
            self._send_json({"error": str(error)}, 400)
            return
        self._send_json(self._serialize_card(self.repository.get_card_by_card_id(card_id)))

    def _read_json(self) -> dict | None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length > 16_384:
                raise ValueError
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict):
                raise ValueError
            return payload
        except (ValueError, json.JSONDecodeError):
            self._send_json({"error": "Invalid request data."}, 400)
            return None

    @staticmethod
    def _serialize_card(card) -> dict:
        return {
            "card_id": card.card_id,
            "customer_name": card.customer_name,
            "destination_url": card.destination_url,
            "active": card.active,
            "total_taps": card.total_taps,
            "created_at": card.created_at,
            "updated_at": card.updated_at,
        }

    def _send_json(self, payload, status: int = 200) -> None:
        content = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _handle_card_tap(self, card_id: str) -> None:
        # IDs are a single path segment. Reject empty or nested values.
        if not card_id or "/" in card_id:
            self._send_card_error()
            return

        card = self.repository.record_tap(card_id)
        if card is None:
            self._send_card_error()
            return

        self.send_response(302)
        self.send_header("Location", card.destination_url)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _serve_public_file(self, path: str) -> None:
        filename = PUBLIC_FILES.get(path)
        if filename is None:
            self.send_error(404, "Page not found")
            return

        content = (PROJECT_ROOT / filename).read_bytes()
        content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _send_card_error(self) -> None:
        content = b"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Card unavailable - Tappr</title><style>
body{margin:0;min-height:100vh;display:grid;place-items:center;background:#f6f3ff;color:#17171d;font-family:Arial,sans-serif;text-align:center}main{max-width:420px;padding:36px}i{display:grid;place-items:center;width:64px;height:64px;margin:0 auto 24px;border-radius:18px;background:#7657e8;color:white;font-size:30px;font-style:normal}h1{font-size:30px;margin:0 0 12px}p{color:#6d6e78;line-height:1.6;margin:0 0 24px}a{display:inline-block;padding:14px 22px;border-radius:10px;background:#7657e8;color:white;text-decoration:none;font-weight:bold}
</style></head><body><main><i>!</i><h1>This card isn't available</h1><p>It may be inactive or the link may have changed. Please check the card and try again.</p><a href="/">Visit Tappr</a></main></body></html>"""
        self.send_response(404)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)


def run(host: str = "127.0.0.1", port: int = 4173) -> None:
    TapprRequestHandler.repository = SQLiteCardRepository()
    server = ThreadingHTTPServer((host, port), TapprRequestHandler)
    print(f"Tappr is running at http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Tappr server.")
    finally:
        server.server_close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the Tappr development server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=4173, type=int)
    args = parser.parse_args()
    run(args.host, args.port)
