from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from .domain import Employee, Vendor, Order, TiffinType


class ValidationError(ValueError):
    pass


class TiffinService:
    """First milestone's application operations, shared by future interfaces."""

    def __init__(self, database, clock=None):
        self.db = database
        self.clock = clock or (lambda: datetime.now(ZoneInfo("Asia/Kolkata")))

    def _require(self, table, identifier):
        rows = self.db.rows(f"SELECT * FROM {table} WHERE id = ?", (identifier,))
        if not rows:
            raise ValidationError(f"Unknown {table} ID: {identifier}")
        return rows[0]

    def add_employee(self, name):
        return self._add_person("employees", Employee, name)

    def add_vendor(self, name):
        return self._add_person("vendors", Vendor, name)

    def _add_person(self, table, cls, name):
        name = name.strip()
        if not name:
            raise ValidationError("Name cannot be empty")
        with self.db.connection:
            cursor = self.db.connection.execute(f"INSERT INTO {table}(name) VALUES (?)", (name,))
        return cls(cursor.lastrowid, name)

    def set_offering(self, vendor_id, kind, price, extra_price):
        self._require("vendors", vendor_id)
        kind = TiffinType(kind)
        if any(type(value) is not int or value < 0 for value in (price, extra_price)):
            raise ValidationError("Prices must be non-negative integer paise")
        with self.db.connection:
            self.db.connection.execute(
                "INSERT INTO offerings VALUES (?,?,?,?) ON CONFLICT(vendor_id,kind) "
                "DO UPDATE SET price=excluded.price, extra_price=excluded.extra_price",
                (vendor_id, kind.value, price, extra_price))

    def open_period(self, start, end, coordinator_id, upi):
        start, end = date.fromisoformat(start), date.fromisoformat(end)
        self._require("employees", coordinator_id)
        if end < start or not upi.strip():
            raise ValidationError("Check period dates and coordinator UPI ID")
        if self.db.rows("SELECT id FROM periods WHERE status='open'"):
            raise ValidationError("A current period is already open")
        if self.db.rows("SELECT id FROM periods WHERE start <= ? AND end >= ?", (end.isoformat(), start.isoformat())):
            raise ValidationError("Billing period dates overlap")
        with self.db.connection:
            cursor = self.db.connection.execute(
                "INSERT INTO periods(start,end,coordinator_id,upi) VALUES (?,?,?,?)",
                (start.isoformat(), end.isoformat(), coordinator_id, upi.strip()))
        return cursor.lastrowid

    def publish_menu(self, period_id, day, vendor_id, kinds, bhajis, cutoff="12:00"):
        period = self._require("periods", period_id)
        self._require("vendors", vendor_id)
        day = date.fromisoformat(day).isoformat()
        cutoff = time.fromisoformat(cutoff).isoformat()
        kinds = list(dict.fromkeys(TiffinType(k) for k in kinds))
        bhajis = list(dict.fromkeys(b.strip() for b in bhajis if b.strip()))
        if period["status"] != "open" or not period["start"] <= day <= period["end"]:
            raise ValidationError("Menu must belong to an open period and fall within its dates")
        if not kinds or (any(k.requires_bhaji for k in kinds) and not bhajis):
            raise ValidationError("Choose offerings and supply bhajis where required")
        offerings = []
        for kind in kinds:
            rows = self.db.rows("SELECT * FROM offerings WHERE vendor_id=? AND kind=?", (vendor_id, kind.value))
            if not rows:
                raise ValidationError(f"Configure vendor price for {kind.value} first")
            offerings.append(rows[0])
        with self.db.connection:
            cursor = self.db.connection.execute(
                "INSERT INTO menus(period_id,day,vendor_id,cutoff) VALUES (?,?,?,?)",
                (period_id, day, vendor_id, cutoff))
            menu_id = cursor.lastrowid
            self.db.connection.executemany("INSERT INTO menu_offerings VALUES (?,?,?,?)",
                [(menu_id, o["kind"], o["price"], o["extra_price"]) for o in offerings])
            self.db.connection.executemany("INSERT INTO bhajis VALUES (?,?)", [(menu_id, b) for b in bhajis])
        return menu_id

    def place_order(self, menu_id, kind, recipient_id, entered_by_id,
                    bhaji=None, extra_chapatis=0, placed_by_id=None, billed_to_id=None,
                    override_reason=None):
        menu = self._require("menus", menu_id)
        period = self._require("periods", menu["period_id"])
        kind = TiffinType(kind)
        placed_by_id = recipient_id if placed_by_id is None else placed_by_id
        billed_to_id = recipient_id if billed_to_id is None else billed_to_id
        for employee_id in (recipient_id, entered_by_id, placed_by_id, billed_to_id):
            self._require("employees", employee_id)
        if entered_by_id != period["coordinator_id"]:
            raise ValidationError("Entered by must be the period's coordinator")
        if billed_to_id not in (recipient_id, placed_by_id):
            raise ValidationError("Bill the recipient or the person placing the order")
        if period["status"] != "open":
            raise ValidationError("Period must be open for orders")
        if type(extra_chapatis) is not int or extra_chapatis < 0:
            raise ValidationError("Extra chapatis must be a non-negative integer")
        if kind.requires_bhaji:
            if not self.db.rows("SELECT name FROM bhajis WHERE menu_id=? AND name=?", (menu_id, bhaji)):
                raise ValidationError("Select a bhaji from this menu")
        elif bhaji is not None or extra_chapatis:
            raise ValidationError("This tiffin does not allow bhaji selection or extra chapatis")
        offerings = self.db.rows("SELECT * FROM menu_offerings WHERE menu_id=? AND kind=?", (menu_id, kind.value))
        if not offerings:
            raise ValidationError("Tiffin is not available on this menu")
        now = self.clock()
        deadline = datetime.fromisoformat(f"{menu['day']}T{menu['cutoff']}").replace(tzinfo=now.tzinfo)
        if now >= deadline and not (override_reason and override_reason.strip()):
            raise ValidationError("Cutoff passed; enter a vendor-approved override reason")
        offering = offerings[0]
        fields = (menu_id, kind.value, recipient_id, placed_by_id, billed_to_id,
                  entered_by_id, bhaji, extra_chapatis, offering["price"], offering["extra_price"])
        with self.db.connection:
            cursor = self.db.connection.execute(
                "INSERT INTO orders(menu_id,tiffin_type,recipient_id,placed_by_id,billed_to_id,"
                "entered_by_id,bhaji,extra_chapatis,base_price_paise,extra_chapati_price_paise,"
                "override_reason,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (*fields, override_reason, now.isoformat()))
        return Order(cursor.lastrowid, *fields)

    def vendor_summary(self, menu_id):
        self._require("menus", menu_id)
        return self.db.rows(
            "SELECT tiffin_type,bhaji,COUNT(*) AS tiffins,SUM(extra_chapatis) AS extra_chapatis "
            "FROM orders WHERE menu_id=? GROUP BY tiffin_type,bhaji", (menu_id,))


    def order_details(self, period_id=None):
        if period_id is not None:
            self._require("periods", period_id)
        return self.db.rows(
            "SELECT o.id,m.day,v.name AS vendor,r.name AS recipient,"
            "p.name AS placed_by,b.name AS billed_to,o.tiffin_type,o.bhaji,"
            "o.extra_chapatis,o.base_price_paise + o.extra_chapatis * "
            "o.extra_chapati_price_paise AS total "
            "FROM orders o JOIN menus m ON m.id=o.menu_id "
            "JOIN vendors v ON v.id=m.vendor_id "
            "JOIN employees r ON r.id=o.recipient_id "
            "JOIN employees p ON p.id=o.placed_by_id "
            "JOIN employees b ON b.id=o.billed_to_id "
            + ("WHERE m.period_id=? " if period_id is not None else "")
            + "ORDER BY m.day,o.id", () if period_id is None else (period_id,))

    def weekly_summary(self, period_id):
        period = self._require("periods", period_id)
        orders = self.order_details(period_id)
        def group(field):
            totals = {}
            for order in orders:
                key = order[field]
                item = totals.setdefault(key, [0, 0, 0])
                item[0] += 1
                item[1] += order["extra_chapatis"]
                item[2] += order["total"]
            return [(name, *values) for name, values in sorted(totals.items())]
        return {"period": period, "orders": orders,
                "employees": group("billed_to"), "vendors": group("vendor"),
                "days": group("day"), "total": sum(o["total"] for o in orders)}
