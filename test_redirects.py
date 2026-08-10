"""Tests for SQLite card persistence and the NFC redirect flow."""

import sqlite3
import json
import tempfile
import threading
import unittest
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
        self.assertEqual(
            card_columns,
            {"id", "card_id", "customer_name", "destination_url", "active", "total_taps", "created_at", "updated_at"},
        )
        self.assertEqual(tap_columns, {"id", "card_id", "tapped_at"})


class RedirectTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temp_directory = tempfile.TemporaryDirectory()
        cls.repository = SQLiteCardRepository(Path(cls.temp_directory.name) / "tappr.db")
        cls.repository.create_card("OFF123", "Inactive", "https://example.com", active=False)
        handler = type("TestHandler", (TapprRequestHandler,), {"repository": cls.repository})
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

    def test_admin_page_and_card_api(self) -> None:
        with self.opener.open(f"{self.base_url}/admin") as response:
            self.assertIn(b"Manage your tap cards", response.read())

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


if __name__ == "__main__":
    unittest.main()
