"""Tests for SQLite card persistence and the NFC redirect flow."""

import sqlite3
import json
import tempfile
import threading
import unittest
import uuid
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from cards import SQLiteCardRepository
from server import TapprRequestHandler


class NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class RepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_directory.name) / "tappr.db"
        self.repository = SQLiteCardRepository(self.database_path)

    def tearDown(self) -> None:
        self.temp_directory.cleanup()

    def test_database_initializes_and_seeds_demo_once(self) -> None:
        SQLiteCardRepository(self.database_path)
        cards = self.repository.list_cards()
        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0].card_id, "DEMO123")
        self.assertEqual(cards[0].customer_name, "Demo Customer")

    def test_admin_repository_methods(self) -> None:
        created = self.repository.create_card("NEW123", "First Name", "https://example.com")
        self.assertEqual(created.total_taps, 0)
        self.assertEqual(len(self.repository.list_cards()), 2)
        self.assertEqual(self.repository.update_customer_name("NEW123", "New Name").customer_name, "New Name")
        self.assertEqual(
            self.repository.update_destination_url("NEW123", "https://example.org").destination_url,
            "https://example.org",
        )
        self.assertFalse(self.repository.deactivate_card("NEW123").active)
        self.assertTrue(self.repository.activate_card("NEW123").active)
        self.assertEqual(self.repository.get_card_by_card_id("NEW123").customer_name, "New Name")
        self.assertEqual(self.repository.get_total_taps("NEW123"), 0)
        self.assertEqual(self.repository.get_recent_tap_events("NEW123"), [])

    def test_tap_count_and_events_persist_after_repository_restart(self) -> None:
        self.repository.record_tap("DEMO123")
        del self.repository

        restarted_repository = SQLiteCardRepository(self.database_path)
        self.assertEqual(restarted_repository.get_total_taps("DEMO123"), 1)
        events = restarted_repository.get_recent_tap_events("DEMO123")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].card_id, "DEMO123")

    def test_card_and_tap_tables_have_required_columns(self) -> None:
        with sqlite3.connect(self.database_path) as connection:
            card_columns = {row[1] for row in connection.execute("PRAGMA table_info(cards)")}
            tap_columns = {row[1] for row in connection.execute("PRAGMA table_info(tap_events)")}
            request_columns = {row[1] for row in connection.execute("PRAGMA table_info(customer_requests)")}
        self.assertEqual(
            card_columns,
            {"id", "card_id", "customer_name", "destination_url", "active", "total_taps", "created_at", "updated_at", "product_type"},
        )
        self.assertEqual(tap_columns, {"id", "card_id", "tapped_at"})
        self.assertEqual(request_columns, {"request_id", "customer_name", "business_name", "email", "phone", "product_type", "destination_type", "destination_url", "design_option", "uploaded_file_path", "design_notes", "status", "created_at"})

    def test_each_product_type_can_be_created(self) -> None:
        for index, product_type in enumerate(("CARD", "PLAQUE", "PROPERTY_SIGN_TAG")):
            device = self.repository.create_card(
                f"TYPE{index}", "Customer", "https://example.com", product_type=product_type
            )
            self.assertEqual(device.product_type, product_type)

    def test_existing_database_migrates_devices_to_card_without_losing_history(self) -> None:
        legacy_path = Path(self.temp_directory.name) / "legacy.db"
        with sqlite3.connect(legacy_path) as connection:
            connection.executescript("""
                CREATE TABLE cards (id INTEGER PRIMARY KEY AUTOINCREMENT, card_id TEXT NOT NULL UNIQUE COLLATE NOCASE, customer_name TEXT NOT NULL, destination_url TEXT NOT NULL, active INTEGER NOT NULL, total_taps INTEGER NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
                CREATE TABLE tap_events (id INTEGER PRIMARY KEY AUTOINCREMENT, card_id TEXT NOT NULL, tapped_at TEXT NOT NULL);
                INSERT INTO cards (card_id, customer_name, destination_url, active, total_taps, created_at, updated_at) VALUES ('TEST001', 'Existing Customer', 'https://example.com', 1, 1, '2026-01-01', '2026-01-01');
                INSERT INTO tap_events (card_id, tapped_at) VALUES ('TEST001', '2026-01-01');
            """)
        migrated = SQLiteCardRepository(legacy_path)
        self.assertEqual(migrated.get("TEST001").product_type, "CARD")
        self.assertEqual(migrated.get_total_taps("TEST001"), 1)
        self.assertEqual(len(migrated.get_recent_tap_events("TEST001")), 1)


class RedirectTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temp_directory = tempfile.TemporaryDirectory()
        cls.repository = SQLiteCardRepository(Path(cls.temp_directory.name) / "tappr.db")
        cls.repository.create_card("OFF123", "Inactive", "https://example.com", active=False)
        handler = type("TestHandler", (TapprRequestHandler,), {"repository": cls.repository})
        cls.upload_directory = Path(cls.temp_directory.name) / "uploads"
        handler.upload_directory = cls.upload_directory
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.server.server_port}"
        cls.opener = build_opener(NoRedirectHandler)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()
        cls.temp_directory.cleanup()

    def test_demo_card_records_event_and_redirects(self) -> None:
        before = self.repository.get_total_taps("DEMO123")
        with self.assertRaises(HTTPError) as response:
            self.opener.open(f"{self.base_url}/t/DEMO123")
        error = response.exception
        self.assertEqual(error.code, 302)
        self.assertEqual(error.headers["Location"], "https://www.google.com")
        error.close()
        self.assertEqual(self.repository.get_total_taps("DEMO123"), before + 1)
        self.assertEqual(len(self.repository.get_recent_tap_events("DEMO123")), before + 1)

    def test_inactive_and_unknown_cards_show_error(self) -> None:
        for card_id in ("OFF123", "UNKNOWN"):
            with self.subTest(card_id=card_id), self.assertRaises(HTTPError) as response:
                self.opener.open(f"{self.base_url}/t/{card_id}")
            self.assertEqual(response.exception.code, 404)
            self.assertIn(b"This card isn't available", response.exception.read())
            response.exception.close()

    def test_landing_page_still_loads(self) -> None:
        with self.opener.open(f"{self.base_url}/") as response:
            self.assertEqual(response.status, 200)
            self.assertIn(b"Get Your Tap Card", response.read())
        with self.opener.open(f"{self.base_url}/customize") as response:
            page = response.read()
            self.assertIn(b"Create your", page)
            self.assertIn(b"Property Sign Tag", page)

    def test_admin_page_and_card_api(self) -> None:
        with self.opener.open(f"{self.base_url}/admin") as response:
            self.assertIn(b"Manage physical products", response.read())

        create_request = Request(
            f"{self.base_url}/api/cards",
            data=json.dumps(
                {
                    "card_id": "TAP001",
                    "customer_name": "Joe's Barber Shop",
                    "destination_url": "https://google.com/reviews",
                    "active": True,
                }
            ).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with self.opener.open(create_request) as response:
            self.assertEqual(response.status, 201)

        patch_request = Request(
            f"{self.base_url}/api/cards/TAP001",
            data=json.dumps({"customer_name": "Joe's Barbers", "active": False}).encode(),
            headers={"Content-Type": "application/json"},
            method="PATCH",
        )
        with self.opener.open(patch_request) as response:
            updated = json.load(response)
        self.assertEqual(updated["customer_name"], "Joe's Barbers")
        self.assertFalse(updated["active"])

        with self.opener.open(f"{self.base_url}/api/cards") as response:
            card_ids = {card["card_id"] for card in json.load(response)}
        self.assertIn("TAP001", card_ids)

    @staticmethod
    def multipart(fields: dict[str, str], files: list[tuple[str, str, str, bytes]]) -> tuple[bytes, str]:
        boundary = f"----Tappr{uuid.uuid4().hex}"
        parts = []
        for name, value in fields.items():
            parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n".encode())
        for name, filename, content_type, content in files:
            parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"; filename=\"{filename}\"\r\nContent-Type: {content_type}\r\n\r\n".encode() + content + b"\r\n")
        parts.append(f"--{boundary}--\r\n".encode())
        return b"".join(parts), f"multipart/form-data; boundary={boundary}"

    def submit_request(self, files, overrides=None):
        fields = {
            "customer_name": "Ada Customer", "business_name": "Ada Studio",
            "email": "ada@example.com", "phone": "", "product_type": "PLAQUE",
            "destination_type": "GOOGLE_REVIEWS", "destination_url": "https://example.com/review",
            "design_option": "UPLOAD_OWN", "design_notes": "Purple and simple",
            "rights_confirmed": "true",
        }
        fields.update(overrides or {})
        body, content_type = self.multipart(fields, files)
        request = Request(f"{self.base_url}/api/requests", data=body, headers={"Content-Type": content_type}, method="POST")
        try:
            response = self.opener.open(request)
            return response.status, json.load(response)
        except HTTPError as error:
            result = json.load(error); status = error.code; error.close(); return status, result

    def test_customization_request_with_image_is_stored_and_listed(self) -> None:
        png = b"\x89PNG\r\n\x1a\n" + b"image-data"
        status, result = self.submit_request([("own_design", "design.png", "image/png", png)])
        self.assertEqual(status, 201)
        self.assertEqual(result["status"], "NEW")
        self.assertNotEqual(result["uploaded_files"][0]["stored_name"], "design.png")
        self.assertTrue((self.upload_directory / result["uploaded_files"][0]["stored_name"]).is_file())
        self.assertIsNotNone(self.repository.get_customer_request(result["request_id"]))
        with self.opener.open(f"{self.base_url}/api/requests") as response:
            self.assertIn(result["request_id"], {item["request_id"] for item in json.load(response)})
        file_name = result["uploaded_files"][0]["stored_name"]
        with self.opener.open(f"{self.base_url}/api/requests/{result['request_id']}/files/{file_name}") as response:
            self.assertEqual(response.headers["Content-Disposition"], 'attachment; filename="design.png"')
            self.assertEqual(response.read(), png)

    def test_valid_pdf_upload_and_status_update(self) -> None:
        status, result = self.submit_request([("own_design", "art.pdf", "application/pdf", b"%PDF-1.4\ncontent")])
        self.assertEqual(status, 201)
        patch = Request(f"{self.base_url}/api/requests/{result['request_id']}", data=b'{"status":"REVIEWING"}', headers={"Content-Type":"application/json"}, method="PATCH")
        with self.opener.open(patch) as response:
            self.assertEqual(json.load(response)["status"], "REVIEWING")

    def test_upload_size_type_and_signature_rejections(self) -> None:
        cases = [
            ("large.png", "image/png", b"\x89PNG\r\n\x1a\n" + b"x" * (10 * 1024 * 1024), "10 MB"),
            ("bad.svg", "image/svg+xml", b"<svg></svg>", "PNG"),
            ("fake.jpg", "image/jpeg", b"not-an-image", "match"),
        ]
        for filename, content_type, content, message in cases:
            with self.subTest(filename=filename):
                status, result = self.submit_request([("own_design", filename, content_type, content)])
                self.assertEqual(status, 400)
                self.assertIn(message, result["error"])

    def test_path_traversal_filename_is_never_used_for_storage(self) -> None:
        png = b"\x89PNG\r\n\x1a\ncontent"
        status, result = self.submit_request([("own_design", "../../escape.png", "image/png", png)])
        self.assertEqual(status, 201)
        stored_name = result["uploaded_files"][0]["stored_name"]
        self.assertNotIn("..", stored_name)
        self.assertEqual((self.upload_directory / stored_name).parent, self.upload_directory)

    def test_rights_confirmation_is_required(self) -> None:
        png = b"\x89PNG\r\n\x1a\ncontent"
        status, result = self.submit_request([("own_design", "a.png", "image/png", png)], {"rights_confirmed": "false"})
        self.assertEqual(status, 400)
        self.assertIn("rights", result["error"])


if __name__ == "__main__":
    unittest.main()
