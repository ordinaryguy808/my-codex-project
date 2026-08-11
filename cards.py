"SQLite-backed Tap Device and customer-request storage."

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse


DEFAULT_DATABASE_PATH = Path(__file__).resolve().parent / "data" / "tappr.db"
PRODUCT_TYPES = {"CARD", "PLAQUE", "PROPERTY_SIGN_TAG"}
REQUEST_PRODUCT_TYPES = PRODUCT_TYPES | {
    "AGENT_LAUNCH_KIT",
    "LISTING_PRO_KIT",
    "TEAM_LAUNCH_KIT",
}
REQUEST_STATUSES = {"NEW", "REVIEWING", "APPROVED", "FULFILLED", "CANCELLED"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class Card:
    id: int
    card_id: str
    customer_name: str
    destination_url: str
    active: bool
    total_taps: int
    created_at: str
    updated_at: str
    product_type: str = "CARD"


@dataclass(frozen=True)
class CustomerRequest:
    request_id: int
    customer_name: str
    business_name: str
    email: str
    phone: str
    product_type: str
    destination_type: str
    destination_url: str
    design_option: str
    uploaded_file_path: str | None
    original_file_name: str | None
    design_notes: str
    status: str
    created_at: str


@dataclass(frozen=True)
class TapEvent:
    id: int
    card_id: str
    tapped_at: str


class SQLiteCardRepository:
    """SQLite implementation of the repository used by the web layer.

    Connections are short-lived so the repository is safe to use from the
    development server's request threads and does not need explicit shutdown.
    """

    def __init__(self, database_path: str | Path = DEFAULT_DATABASE_PATH) -> None:
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def initialize(self) -> None:
        """Create tables and seed the demo card when they do not exist."""
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS cards (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    card_id TEXT NOT NULL UNIQUE COLLATE NOCASE,
                    customer_name TEXT NOT NULL,
                    destination_url TEXT NOT NULL,
                    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
                    total_taps INTEGER NOT NULL DEFAULT 0 CHECK (total_taps >= 0),
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS tap_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    card_id TEXT NOT NULL COLLATE NOCASE,
                    tapped_at TEXT NOT NULL,
                    FOREIGN KEY (card_id) REFERENCES cards(card_id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_tap_events_card_time
                ON tap_events(card_id, tapped_at DESC);

                CREATE TABLE IF NOT EXISTS customer_requests (
                    request_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    customer_name TEXT NOT NULL,
                    business_name TEXT NOT NULL DEFAULT '',
                    email TEXT NOT NULL,
                    phone TEXT NOT NULL DEFAULT '',
                    product_type TEXT NOT NULL,
                    destination_type TEXT NOT NULL,
                    destination_url TEXT NOT NULL,
                    design_option TEXT NOT NULL,
                    uploaded_file_path TEXT,
                    original_file_name TEXT,
                    design_notes TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'NEW',
                    created_at TEXT NOT NULL
                );
                """
            )
            card_columns = {
                row[1] for row in connection.execute("PRAGMA table_info(cards)")
            }
            if "product_type" not in card_columns:
                connection.execute(
                    "ALTER TABLE cards ADD COLUMN product_type TEXT NOT NULL DEFAULT 'CARD'"
                )
            connection.execute(
                "UPDATE cards SET product_type = 'CARD' "
                "WHERE product_type IS NULL OR product_type = ''"
            )
            now = utc_now()
            connection.execute(
                """
                INSERT OR IGNORE INTO cards
                    (card_id, customer_name, destination_url, active, total_taps, created_at, updated_at)
                VALUES (?, ?, ?, 1, 0, ?, ?)
                """,
                ("DEMO123", "Demo Customer", "https://www.google.com", now, now),
            )

    @staticmethod
    def _to_card(row: sqlite3.Row | None) -> Card | None:
        if row is None:
            return None
        return Card(
            id=row["id"],
            card_id=row["card_id"],
            customer_name=row["customer_name"],
            destination_url=row["destination_url"],
            active=bool(row["active"]),
            total_taps=row["total_taps"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            product_type=row["product_type"],
        )

    def list_cards(self) -> list[Card]:
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM cards ORDER BY created_at, id").fetchall()
        return [self._to_card(row) for row in rows]

    def get(self, card_id: str) -> Card | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM cards WHERE card_id = ?", (card_id,)
            ).fetchone()
        return self._to_card(row)

    def get_card_by_card_id(self, card_id: str) -> Card | None:
        return self.get(card_id)

    def create_card(
        self, card_id: str, customer_name: str, destination_url: str, active: bool = True,
        product_type: str = "CARD",
    ) -> Card:
        card_id = card_id.strip().upper()
        customer_name = customer_name.strip()
        destination_url = destination_url.strip()
        product_type = product_type.strip().upper()
        if not card_id or not card_id.replace("-", "").isalnum():
            raise ValueError("Card ID may contain only letters, numbers, and hyphens.")
        if not customer_name:
            raise ValueError("Customer name is required.")
        if urlparse(destination_url).scheme not in {"http", "https"}:
            raise ValueError("Destination must be a valid HTTP or HTTPS URL.")
        if product_type not in PRODUCT_TYPES:
            raise ValueError("Unsupported product type.")
        now = utc_now()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO cards
                    (card_id, customer_name, destination_url, active, total_taps, created_at, updated_at, product_type)
                VALUES (?, ?, ?, ?, 0, ?, ?, ?)
                """,
                (card_id, customer_name, destination_url, int(active), now, now, product_type),
            )
        return self.get(card_id)

    def _update(self, card_id: str, column: str, value: str | int) -> Card | None:
        allowed_columns = {"customer_name", "destination_url", "active", "product_type"}
        if column not in allowed_columns:
            raise ValueError(f"Unsupported card field: {column}")
        with self._connect() as connection:
            connection.execute(
                f"UPDATE cards SET {column} = ?, updated_at = ? WHERE card_id = ?",
                (value, utc_now(), card_id),
            )
        return self.get(card_id)

    def update_customer_name(self, card_id: str, customer_name: str) -> Card | None:
        customer_name = customer_name.strip()
        if not customer_name:
            raise ValueError("Customer name is required.")
        return self._update(card_id, "customer_name", customer_name)

    def update_destination_url(self, card_id: str, destination_url: str) -> Card | None:
        destination_url = destination_url.strip()
        if urlparse(destination_url).scheme not in {"http", "https"}:
            raise ValueError("Destination must be a valid HTTP or HTTPS URL.")
        return self._update(card_id, "destination_url", destination_url)

    def set_active(self, card_id: str, active: bool) -> Card | None:
        return self._update(card_id, "active", int(active))

    def update_product_type(self, card_id: str, product_type: str) -> Card | None:
        product_type = product_type.strip().upper()
        if product_type not in PRODUCT_TYPES:
            raise ValueError("Unsupported product type.")
        return self._update(card_id, "product_type", product_type)

    def create_customer_request(self, **values) -> CustomerRequest:
        product_type = str(values.get("product_type", "")).upper()
        if product_type not in REQUEST_PRODUCT_TYPES:
            raise ValueError("Unsupported product or package.")
        now = utc_now()
        fields = (
            "customer_name", "business_name", "email", "phone", "destination_type",
            "destination_url", "design_option", "uploaded_file_path", "original_file_name",
            "design_notes",
        )
        with self._connect() as connection:
            cursor = connection.execute(
                """INSERT INTO customer_requests
                (customer_name, business_name, email, phone, product_type,
                 destination_type, destination_url, design_option, uploaded_file_path,
                 original_file_name, design_notes, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'NEW', ?)""",
                tuple(values.get(field, "") for field in fields[:4])
                + (product_type,)
                + tuple(values.get(field, "") for field in fields[4:])
                + (now,),
            )
            request_id = cursor.lastrowid
        return self.get_customer_request(request_id)

    @staticmethod
    def _to_request(row: sqlite3.Row | None) -> CustomerRequest | None:
        return CustomerRequest(**dict(row)) if row is not None else None

    def list_customer_requests(self) -> list[CustomerRequest]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM customer_requests ORDER BY created_at DESC, request_id DESC"
            ).fetchall()
        return [self._to_request(row) for row in rows]

    def get_customer_request(self, request_id: int) -> CustomerRequest | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM customer_requests WHERE request_id = ?", (request_id,)
            ).fetchone()
        return self._to_request(row)

    def update_request_status(self, request_id: int, status: str) -> CustomerRequest | None:
        status = status.strip().upper()
        if status not in REQUEST_STATUSES:
            raise ValueError("Unsupported request status.")
        with self._connect() as connection:
            connection.execute(
                "UPDATE customer_requests SET status = ? WHERE request_id = ?",
                (status, request_id),
            )
        return self.get_customer_request(request_id)

    def activate_card(self, card_id: str) -> Card | None:
        return self.set_active(card_id, True)

    def deactivate_card(self, card_id: str) -> Card | None:
        return self.set_active(card_id, False)

    def get_total_taps(self, card_id: str) -> int | None:
        card = self.get(card_id)
        return card.total_taps if card else None

    def get_recent_tap_events(self, card_id: str, limit: int = 20) -> list[TapEvent]:
        safe_limit = max(0, min(limit, 100))
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, card_id, tapped_at FROM tap_events
                WHERE card_id = ? ORDER BY tapped_at DESC, id DESC LIMIT ?
                """,
                (card_id, safe_limit),
            ).fetchall()
        return [TapEvent(row["id"], row["card_id"], row["tapped_at"]) for row in rows]

    def record_tap(self, card_id: str) -> Card | None:
        """Atomically add a tap event and increment an active card's count."""
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM cards WHERE card_id = ?", (card_id,)
            ).fetchone()
            if row is None or not row["active"]:
                return None

            tapped_at = utc_now()
            canonical_id = row["card_id"]
            connection.execute(
                "INSERT INTO tap_events (card_id, tapped_at) VALUES (?, ?)",
                (canonical_id, tapped_at),
            )
            connection.execute(
                """
                UPDATE cards SET total_taps = total_taps + 1, updated_at = ?
                WHERE card_id = ?
                """,
                (tapped_at, canonical_id),
            )
            updated = connection.execute(
                "SELECT * FROM cards WHERE card_id = ?", (canonical_id,)
            ).fetchone()
        return self._to_card(updated)
