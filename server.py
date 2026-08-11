"Development web server for the Tappr landing page and NFC redirects."

import argparse
import json
import mimetypes
import sqlite3
import uuid
from email.parser import BytesParser
from email.policy import default
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlparse

from cards import PRODUCT_TYPES, REQUEST_PRODUCT_TYPES, REQUEST_STATUSES, SQLiteCardRepository


PROJECT_ROOT = Path(__file__).resolve().parent
UPLOAD_ROOT = PROJECT_ROOT / "data" / "uploads"
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
DESTINATION_TYPES = {
    "Instagram", "Facebook", "Google Reviews", "Website", "Booking Page",
    "Property Listing", "Menu", "Portfolio", "Other",
}
DESIGN_OPTIONS = {"UPLOAD", "TAPPR_DESIGN"}
UPLOAD_TYPES = {
    ".png": ("image/png", lambda data: data.startswith(b"\x89PNG\r\n\x1a\n")),
    ".jpg": ("image/jpeg", lambda data: data.startswith(b"\xff\xd8\xff")),
    ".jpeg": ("image/jpeg", lambda data: data.startswith(b"\xff\xd8\xff")),
    ".pdf": ("application/pdf", lambda data: data.startswith(b"%PDF-")),
}
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


class TapprRequestHandler(BaseHTTPRequestHandler):
    repository: SQLiteCardRepository

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path in {"/api/cards", "/api/devices"}:
            self._send_json([self._serialize_card(card) for card in self.repository.list_cards()])
            return
        if path == "/api/requests":
            self._send_json([
                self._serialize_request(request)
                for request in self.repository.list_customer_requests()
            ])
            return
        if path.startswith("/api/requests/") and path.endswith("/artwork"):
            self._download_artwork(path)
            return
        if path.startswith("/api/requests/"):
            self._get_request(path)
            return
        if path.startswith("/t/"):
            self._handle_card_tap(unquote(path.removeprefix("/t/")))
            return
        self._serve_public_file(path)

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/api/requests":
            self._create_request()
            return
        if path not in {"/api/cards", "/api/devices"}:
            self.send_error(404, "Page not found")
            return
        payload = self._read_json()
        if payload is None:
            return
        tap_id = payload.get("tap_id", payload.get("card_id", ""))
        if not str(tap_id).strip() or any(
            not str(payload.get(field, "")).strip()
            for field in ("customer_name", "destination_url")
        ):
            self._send_json({"error": "Tap ID, customer name, and destination URL are required."}, 400)
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

    def do_PATCH(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path.startswith("/api/requests/"):
            self._patch_request(path)
            return
        if not (path.startswith("/api/cards/") or path.startswith("/api/devices/")):
            self.send_error(404, "Page not found")
            return
        card_id = unquote(path.removeprefix("/api/cards/").removeprefix("/api/devices/"))
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
            "tap_id": card.card_id,
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
    def _serialize_request(request) -> dict:
        return {
            "request_id": request.request_id,
            "customer_name": request.customer_name,
            "business_name": request.business_name,
            "email": request.email,
            "phone": request.phone,
            "product_type": request.product_type,
            "destination_type": request.destination_type,
            "destination_url": request.destination_url,
            "design_option": request.design_option,
            "has_artwork": bool(request.uploaded_file_path),
            "original_file_name": request.original_file_name,
            "design_notes": request.design_notes,
            "status": request.status,
            "created_at": request.created_at,
        }

    def _parse_multipart(self) -> tuple[dict[str, str], tuple[str, str, bytes] | None]:
        content_type = self.headers.get("Content-Type", "")
        if not content_type.lower().startswith("multipart/form-data"):
            raise ValueError("Request must use multipart form data.")
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as error:
            raise ValueError("Invalid request data.") from error
        if length <= 0 or length > MAX_UPLOAD_BYTES + 64 * 1024:
            raise ValueError("Uploaded files must be 10 MB or smaller.")
        message = BytesParser(policy=default).parsebytes(
            f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode()
            + self.rfile.read(length)
        )
        fields: dict[str, str] = {}
        upload = None
        for part in message.iter_parts():
            name = part.get_param("name", header="content-disposition")
            filename = part.get_filename()
            data = part.get_payload(decode=True) or b""
            if not name:
                continue
            if filename is not None and name == "artwork" and data:
                upload = (filename, part.get_content_type().lower(), data)
            elif filename is None:
                fields[name] = data.decode("utf-8", errors="replace").strip()
        return fields, upload

    @staticmethod
    def _valid_url(value: str) -> bool:
        parsed = urlparse(value)
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)

    def _create_request(self) -> None:
        stored_path = None
        try:
            fields, upload = self._parse_multipart()
            required = (
                "customer_name", "email", "product_type", "destination_type",
                "destination_url", "design_option",
            )
            if any(not fields.get(field) for field in required):
                raise ValueError("Please complete all required fields.")
            if fields["product_type"] not in REQUEST_PRODUCT_TYPES:
                raise ValueError("Unsupported product or package.")
            if fields["destination_type"] not in DESTINATION_TYPES:
                raise ValueError("Unsupported destination type.")
            if fields["design_option"] not in DESIGN_OPTIONS:
                raise ValueError("Unsupported design option.")
            if not self._valid_url(fields["destination_url"]):
                raise ValueError("Destination must be a valid HTTP or HTTPS URL.")
            if "@" not in fields["email"] or fields["email"].startswith("@"):
                raise ValueError("Please enter a valid email address.")
            if fields.get("artwork_rights") not in {"on", "true", "1", "yes"}:
                raise ValueError("You must confirm your rights to uploaded artwork.")
            if fields["design_option"] == "UPLOAD" and upload is None:
                raise ValueError("Please upload your design.")

            original_name = None
            if upload:
                supplied_name, supplied_mime, data = upload
                if len(data) > MAX_UPLOAD_BYTES:
                    raise ValueError("Uploaded files must be 10 MB or smaller.")
                original_name = PurePosixPath(supplied_name.replace("\\", "/")).name
                suffix = Path(original_name).suffix.lower()
                expected = UPLOAD_TYPES.get(suffix)
                if not original_name or expected is None:
                    raise ValueError("Artwork must be a PNG, JPG, JPEG, or PDF file.")
                expected_mime, signature_check = expected
                if supplied_mime != expected_mime or not signature_check(data):
                    raise ValueError("The uploaded file type does not match its contents.")
                UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
                stored_name = f"{uuid.uuid4().hex}{suffix}"
                destination = (UPLOAD_ROOT / stored_name).resolve()
                if destination.parent != UPLOAD_ROOT.resolve():
                    raise ValueError("Invalid upload path.")
                destination.write_bytes(data)
                stored_path = stored_name

            request = self.repository.create_customer_request(
                customer_name=fields["customer_name"], business_name=fields.get("business_name", ""),
                email=fields["email"], phone=fields.get("phone", ""), product_type=fields["product_type"],
                destination_type=fields["destination_type"], destination_url=fields["destination_url"],
                design_option=fields["design_option"], uploaded_file_path=stored_path,
                original_file_name=original_name, design_notes=fields.get("design_notes", ""),
            )
        except ValueError as error:
            if stored_path:
                (UPLOAD_ROOT / stored_path).unlink(missing_ok=True)
            self._send_json({"error": str(error)}, 400)
            return
        self._send_json(self._serialize_request(request), 201)

    @staticmethod
    def _request_id(path: str, artwork: bool = False) -> int | None:
        tail = path.removeprefix("/api/requests/")
        if artwork:
            tail = tail.removesuffix("/artwork").rstrip("/")
        try:
            return int(tail) if tail and "/" not in tail else None
        except ValueError:
            return None

    def _get_request(self, path: str) -> None:
        request_id = self._request_id(path)
        request = self.repository.get_customer_request(request_id) if request_id else None
        if request is None:
            self._send_json({"error": "Request not found."}, 404)
            return
        self._send_json(self._serialize_request(request))

    def _patch_request(self, path: str) -> None:
        request_id = self._request_id(path)
        payload = self._read_json()
        if payload is None:
            return
        if request_id is None or self.repository.get_customer_request(request_id) is None:
            self._send_json({"error": "Request not found."}, 404)
            return
        try:
            status = str(payload.get("status", ""))
            if status not in REQUEST_STATUSES:
                raise ValueError("Unsupported request status.")
            request = self.repository.update_request_status(request_id, status)
        except ValueError as error:
            self._send_json({"error": str(error)}, 400)
            return
        self._send_json(self._serialize_request(request))

    def _download_artwork(self, path: str) -> None:
        request_id = self._request_id(path, artwork=True)
        request = self.repository.get_customer_request(request_id) if request_id else None
        if request is None or not request.uploaded_file_path:
            self._send_json({"error": "Artwork not found."}, 404)
            return
        stored_name = Path(request.uploaded_file_path).name
        file_path = (UPLOAD_ROOT / stored_name).resolve()
        if file_path.parent != UPLOAD_ROOT.resolve() or not file_path.is_file():
            self._send_json({"error": "Artwork not found."}, 404)
            return
        content = file_path.read_bytes()
        safe_download_name = "".join(
            character for character in (request.original_file_name or "artwork")
            if character.isalnum() or character in {" ", ".", "-", "_"}
        ) or "artwork"
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Disposition", f'attachment; filename="{safe_download_name}"')
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "no-store")
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
