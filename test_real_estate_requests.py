"""Tests for Tappr real-estate product and package request support."""

import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.request import Request, build_opener

import server as server_module
from cards import PRODUCT_TYPES, REQUEST_PRODUCT_TYPES, SQLiteCardRepository
from server import TapprRequestHandler


def multipart(fields: dict[str, str]) -> tuple[bytes, str]:
    boundary = "----TapprRealEstateTest"
    parts = []
    for name, value in fields.items():
        parts.append(
            f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode()
        )
    parts.append(f"--{boundary}--\r\n".encode())
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


class RealEstateRequestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temp_directory = tempfile.TemporaryDirectory()
        cls.original_upload_root = server_module.UPLOAD_ROOT
        server_module.UPLOAD_ROOT = Path(cls.temp_directory.name) / "uploads"
        cls.repository = SQLiteCardRepository(Path(cls.temp_directory.name) / "tappr.db")
        handler = type("TestHandler", (TapprRequestHandler,), {"repository": cls.repository})
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.server.server_port}"
        cls.opener = build_opener()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()
        server_module.UPLOAD_ROOT = cls.original_upload_root
        cls.temp_directory.cleanup()

    def test_device_types_stay_separate_from_package_request_types(self) -> None:
        self.assertEqual(PRODUCT_TYPES, {"CARD", "PLAQUE", "PROPERTY_SIGN_TAG"})
        self.assertTrue({"AGENT_LAUNCH_KIT", "LISTING_PRO_KIT", "TEAM_LAUNCH_KIT"}.issubset(REQUEST_PRODUCT_TYPES))

    def test_landing_and_customize_pages_show_real_estate_launch_content(self) -> None:
        with self.opener.open(f"{self.base_url}/") as response:
            body = response.read()
        self.assertIn(b"Smart physical marketing for real estate", body)
        self.assertIn(b"Premium from the first tap", body)
        self.assertIn(b"Listing Pro Kit", body)

        with self.opener.open(f"{self.base_url}/customize") as response:
            body = response.read()
        self.assertIn(b"Estimated request total", body)
        self.assertIn(b"LISTING_PRO_KIT", body)

    def test_listing_pro_package_request_is_saved(self) -> None:
        fields = {
            "customer_name": "Test Agent",
            "business_name": "Test Realty",
            "email": "agent@example.com",
            "phone": "555-0100",
            "product_type": "LISTING_PRO_KIT",
            "destination_type": "Property Listing",
            "destination_url": "https://example.com/listing",
            "design_option": "TAPPR_DESIGN",
            "design_notes": "Listing Pro test",
            "artwork_rights": "on",
        }
        body, content_type = multipart(fields)
        request = Request(
            f"{self.base_url}/api/requests",
            data=body,
            headers={"Content-Type": content_type},
            method="POST",
        )
        with self.opener.open(request) as response:
            created = json.load(response)
        self.assertEqual(created["status"], "NEW")
        self.assertEqual(created["product_type"], "LISTING_PRO_KIT")


if __name__ == "__main__":
    unittest.main()
