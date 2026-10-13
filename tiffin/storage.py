import sqlite3


class Database:
    """Owns persistence; services own business decisions."""

    def __init__(self, path):
        self.connection = sqlite3.connect(path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.connection.executescript("""
        CREATE TABLE IF NOT EXISTS employees (
            id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE COLLATE NOCASE);
        CREATE TABLE IF NOT EXISTS vendors (
            id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE COLLATE NOCASE);
        CREATE TABLE IF NOT EXISTS offerings (
            vendor_id INTEGER REFERENCES vendors(id), kind TEXT NOT NULL,
            price INTEGER NOT NULL CHECK(price >= 0),
            extra_price INTEGER NOT NULL CHECK(extra_price >= 0),
            PRIMARY KEY(vendor_id, kind));
        CREATE TABLE IF NOT EXISTS periods (
            id INTEGER PRIMARY KEY, start TEXT NOT NULL, end TEXT NOT NULL,
            coordinator_id INTEGER NOT NULL REFERENCES employees(id),
            upi TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'open');
        CREATE TABLE IF NOT EXISTS menus (
            id INTEGER PRIMARY KEY, period_id INTEGER NOT NULL REFERENCES periods(id),
            day TEXT NOT NULL, vendor_id INTEGER NOT NULL REFERENCES vendors(id),
            cutoff TEXT NOT NULL, UNIQUE(day, vendor_id));
        CREATE TABLE IF NOT EXISTS menu_offerings (
            menu_id INTEGER REFERENCES menus(id), kind TEXT NOT NULL,
            price INTEGER NOT NULL, extra_price INTEGER NOT NULL,
            PRIMARY KEY(menu_id, kind));
        CREATE TABLE IF NOT EXISTS bhajis (
            menu_id INTEGER REFERENCES menus(id), name TEXT NOT NULL,
            PRIMARY KEY(menu_id, name));
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY, menu_id INTEGER NOT NULL REFERENCES menus(id),
            tiffin_type TEXT NOT NULL,
            recipient_id INTEGER NOT NULL REFERENCES employees(id),
            placed_by_id INTEGER NOT NULL REFERENCES employees(id),
            billed_to_id INTEGER NOT NULL REFERENCES employees(id),
            entered_by_id INTEGER NOT NULL REFERENCES employees(id),
            bhaji TEXT, extra_chapatis INTEGER NOT NULL CHECK(extra_chapatis >= 0),
            base_price_paise INTEGER NOT NULL, extra_chapati_price_paise INTEGER NOT NULL,
            override_reason TEXT, created_at TEXT NOT NULL);
        """)

    def rows(self, sql, parameters=()):
        return self.connection.execute(sql, parameters).fetchall()

    def close(self):
        self.connection.close()
