"""Development web server for the Tappr landing page and NFC redirects."""

import argparse
from email.parser import BytesParser
from email.policy import default as email_policy
import json
import mimetypes
import sqlite3
import secrets
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
    "/customize": "customize.html",
    "/customize.html": "customize.html",
    "/customize.css": "customize.css",
    "/customize.js": "customize.js",
}

UPLOAD_DIRECTORY = PROJECT_ROOT / "data" / "uploads"
MAX_FILE_SIZE = 10 * 1024 * 1024
MAX_REQUEST_SIZE = 32 * 1024 * 1024
DESTINATION_TYPES = {
    "INSTAGRAM", "FACEBOOK", "GOOGLE_REVIEWS", "WEBSITE", "BOOKING_PAGE",
    "PROPERTY_LISTING", "MENU", "PORTFOLIO", "OTHER",
}


class TapprRequestHandler(BaseHTTPRequestHandler):
    repository: SQLiteCardRepository
    upload_directory: Path = UPLOAD_DIRECTORY

    def do_GET(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler
        path = urlparse(self.path).path
        if path == "/api/cards":
            self._send_json([self._serialize_card(card) for card in self.repository.list_cards()])
            return
        if path == "/api/requests":
            self._send_json([self._serialize_request(item) for item in self.repository.list_customer_requests()])
            return
        if path.startswith("/api/requests/") and "/files/" in path:
            self._download_request_file(path)
            return
        if path.startswith("/t/"):
            self._handle_card_tap(unquote(path.removeprefix("/t/")))
            return
        self._serve_public_file(path)

    def do_POST(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler
        path = urlparse(self.path).path
        if path == "/api/requests":
            self._create_customer_request()
            return
        if path != "/api/cards":
            self.send_error(404, "Page not found")
            return
        payload = self._read_json()
        if payload is None:
            return
        tap_id = payload.get("tap_id", payload.get("card_id", ""))
        required_values = (tap_id, payload.get("customer_name", ""), payload.get("destination_url", ""))
        if any(not str(value).strip() for value in required_values):
            self._send_json({"error": "Card ID, customer name, and destination URL are required."}, 400)
            return
        try:
            card = self.repository.create_card(
                str(tap_id).strip(),
                str(payload["customer_name"]).strip(),
                str(payload["destination_url"]).strip(),
                bool(payload.get("active", True)),
                str(payload.get("product_type", "CARD")),
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
        if path.startswith("/api/requests/"):
            self._update_request_status(unquote(path.removeprefix("/api/requests/")))
            return
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
            if "product_type" in payload:
                self.repository.update_product_type(card_id, str(payload["product_type"]))
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
            "tap_id": card.tap_id,
            # Legacy alias retained for existing API clients.
            "card_id": card.card_id,
            "customer_name": card.customer_name,
            "destination_url": card.destination_url,
            "active": card.active,
            "total_taps": card.total_taps,
            "created_at": card.created_at,
            "updated_at": card.updated_at,
            "product_type": card.product_type,
        }

    @staticmethod
    def _serialize_request(item) -> dict:
        result = dict(item.__dict__)
        try:
            result["uploaded_files"] = json.loads(item.uploaded_file_path or "[]")
        except json.JSONDecodeError:
            result["uploaded_files"] = []
        result.pop("uploaded_file_path", None)
        return result

    def _create_customer_request(self) -> None:
        try:
            fields, files = self._read_multipart()
            required = ("customer_name", "email", "product_type", "destination_type", "destination_url", "design_option")
            if any(not fields.get(name, "").strip() for name in required):
                raise ValueError("Please complete all required fields.")
            if fields.get("rights_confirmed") != "true":
                raise ValueError("You must confirm that you have rights to uploaded artwork.")
            if fields["destination_type"] not in DESTINATION_TYPES:
                raise ValueError("Unsupported destination type.")
            if fields["design_option"] not in {"UPLOAD_OWN", "TAPPR_DESIGN"}:
                raise ValueError("Unsupported design option.")
            parsed_url = urlparse(fields["destination_url"])
            if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
                raise ValueError("Destination must be a valid HTTP or HTTPS URL.")
            if fields["design_option"] == "UPLOAD_OWN" and not files:
                raise ValueError("Please upload your design.")
            stored = self._store_uploads(files)
            item = self.repository.create_customer_request(
                **fields, uploaded_file_path=json.dumps(stored)
            )
        except ValueError as error:
            self._send_json({"error": str(error)}, 400)
            return
        self._send_json(self._serialize_request(item), 201)

    def _read_multipart(self) -> tuple[dict[str, str], list[tuple[str, str, bytes, str]]]:
        content_type = self.headers.get("Content-Type", "")
        length = int(self.headers.get("Content-Length", "0"))
        if "multipart/form-data" not in content_type or length <= 0 or length > MAX_REQUEST_SIZE:
            raise ValueError("Invalid form submission or request is too large.")
        message = BytesParser(policy=email_policy).parsebytes(
            f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode()
            + self.rfile.read(length)
        )
        fields: dict[str, str] = {}
        files = []
        for part in message.iter_parts():
            name = part.get_param("name", header="content-disposition")
            filename = part.get_filename()
            payload = part.get_payload(decode=True) or b""
            if filename:
                if payload:
                    files.append((name or "file", filename, payload, part.get_content_type()))
            elif name:
                fields[name] = payload.decode("utf-8", errors="replace")
        return fields, files

    def _store_uploads(self, files: list[tuple[str, str, bytes, str]]) -> list[dict[str, str]]:
        accepted_types = {
            ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".pdf": "application/pdf"
        }
        stored = []
        self.upload_directory.mkdir(parents=True, exist_ok=True)
        try:
            for role, original_name, payload, content_type in files:
                extension = Path(original_name).suffix.lower()
                expected_type = accepted_types.get(extension)
                if expected_type is None or content_type != expected_type:
                    raise ValueError("Uploads must be PNG, JPG, JPEG, or PDF files.")
                if len(payload) > MAX_FILE_SIZE:
                    raise ValueError("Each uploaded file must be 10 MB or smaller.")
                valid_signature = (
                    extension == ".png" and payload.startswith(b"\x89PNG\r\n\x1a\n")
                    or extension in {".jpg", ".jpeg"} and payload.startswith(b"\xff\xd8\xff")
                    or extension == ".pdf" and payload.startswith(b"%PDF-")
                )
                if not valid_signature:
                    raise ValueError("An uploaded file does not match its declared format.")
                server_name = f"{secrets.token_hex(16)}{extension}"
                (self.upload_directory / server_name).write_bytes(payload)
                stored.append({"role": role, "name": Path(original_name).name, "stored_name": server_name})
        except Exception:
            for item in stored:
                (self.upload_directory / item["stored_name"]).unlink(missing_ok=True)
            raise
        return stored

    def _update_request_status(self, request_id: str) -> None:
        payload = self._read_json()
        if payload is None:
            return
        try:
            item = self.repository.update_request_status(request_id, str(payload.get("status", "")))
        except ValueError as error:
            self._send_json({"error": str(error)}, 400)
            return
        if item is None:
            self._send_json({"error": "Request not found."}, 404)
            return
        self._send_json(self._serialize_request(item))

    def _download_request_file(self, path: str) -> None:
        prefix, stored_name = path.rsplit("/files/", 1)
        request_id = unquote(prefix.removeprefix("/api/requests/"))
        if not stored_name or Path(stored_name).name != stored_name:
            self.send_error(404)
            return
        item = self.repository.get_customer_request(request_id)
        if item is None:
            self.send_error(404)
            return
        try:
            uploads = json.loads(item.uploaded_file_path or "[]")
            upload = next(entry for entry in uploads if entry["stored_name"] == stored_name)
        except (json.JSONDecodeError, KeyError, StopIteration):
            self.send_error(404)
            return
        file_path = self.upload_directory / stored_name
        if not file_path.is_file():
            self.send_error(404)
            return
        content = file_path.read_bytes()
        download_name = "".join(
            character
            if character.isascii() and (character.isalnum() or character in {".", "_", "-"})
            else "_"
            for character in Path(upload["name"]).name
        ) or f"artwork{Path(stored_name).suffix}"
        self.send_response(200)
        self.send_header("Content-Type", mimetypes.guess_type(stored_name)[0] or "application/octet-stream")
        self.send_header("Content-Disposition", f'attachment; filename="{download_name}"')
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

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
