import unittest
from datetime import datetime

from tiffin.domain import TiffinType
from tiffin.services import TiffinService, ValidationError
from tiffin.storage import Database


class OrderWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.db = Database(":memory:")
        self.service = TiffinService(self.db, clock=lambda: datetime(2026, 10, 8, 11))
        self.rahul = self.service.add_employee("Rahul")
        self.amit = self.service.add_employee("Amit")
        self.vendor = self.service.add_vendor("Vendor A")
        for kind in TiffinType:
            self.service.set_offering(self.vendor.id, kind, 8000, 1000)
        self.period = self.service.open_period("2026-10-05", "2026-10-09", self.amit.id, "amit@upi")
        self.menu = self.service.publish_menu(self.period, "2026-10-08", self.vendor.id, list(TiffinType), ["Gavari", "Tomato"])

    def tearDown(self):
        self.db.close()

    def order(self, **kwargs):
        return self.service.place_order(self.menu, kwargs.pop("kind", TiffinType.CHAPATI),
            self.rahul.id, self.amit.id, **kwargs)

    def test_defaults_extras_and_separate_orders(self):
        first = self.order(bhaji="Gavari", extra_chapatis=2)
        second = self.order(bhaji="Tomato")
        self.assertNotEqual(first.id, second.id)
        self.assertEqual(first.billed_to_id, self.rahul.id)
        self.assertEqual(first.placed_by_id, self.rahul.id)
        self.assertEqual(first.calculate_total(), 10000)
        self.assertEqual(sum(r["tiffins"] for r in self.service.vendor_summary(self.menu)), 2)

    def test_requester_can_pay(self):
        order = self.order(bhaji="Gavari", placed_by_id=self.amit.id, billed_to_id=self.amit.id)
        self.assertEqual(order.recipient_id, self.rahul.id)
        self.assertEqual(order.billed_to_id, self.amit.id)

    def test_price_changes_preserve_menu_and_orders(self):
        first = self.order(bhaji="Gavari")
        self.service.set_offering(self.vendor.id, TiffinType.CHAPATI, 99900, 3000)
        second = self.order(bhaji="Gavari")
        self.assertEqual(first.calculate_total(), second.calculate_total())

    def test_selection_rules(self):
        for kwargs in ({}, {"bhaji": "Unknown"}, {"bhaji": "Gavari", "extra_chapatis": -1},
                       {"kind": TiffinType.DAAL, "bhaji": "Gavari"},
                       {"kind": TiffinType.KHICHDI, "extra_chapatis": 1}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValidationError):
                self.order(**kwargs)
        self.assertEqual(self.order(kind=TiffinType.DAAL).calculate_total(), 8000)

    def test_cutoff_override(self):
        self.service.clock = lambda: datetime(2026, 10, 8, 12)
        with self.assertRaises(ValidationError):
            self.order(bhaji="Gavari")
        self.order(bhaji="Gavari", override_reason="Vendor agreed by phone")

    def test_multiple_vendors_same_day(self):
        vendor = self.service.add_vendor("Vendor B")
        self.service.set_offering(vendor.id, TiffinType.DAAL, 7000, 0)
        menu = self.service.publish_menu(self.period, "2026-10-08", vendor.id, [TiffinType.DAAL], [])
        self.assertNotEqual(menu, self.menu)

    def test_menu_outside_period_rejected(self):
        with self.assertRaises(ValidationError):
            self.service.publish_menu(self.period, "2026-10-10", self.vendor.id, [TiffinType.DAAL], [])

    def test_weekly_summary_groups_billed_employee_and_vendor(self):
        self.order(bhaji="Gavari", extra_chapatis=2)
        self.order(bhaji="Tomato", placed_by_id=self.amit.id, billed_to_id=self.amit.id)
        vendor = self.service.add_vendor("Vendor B")
        self.service.set_offering(vendor.id, TiffinType.DAAL, 7000, 0)
        menu = self.service.publish_menu(self.period, "2026-10-08", vendor.id, [TiffinType.DAAL], [])
        self.service.place_order(menu, TiffinType.DAAL, self.rahul.id, self.amit.id)
        summary = self.service.weekly_summary(self.period)
        self.assertEqual(summary["total"], 25000)
        self.assertEqual(summary["employees"], [("Amit", 1, 0, 8000), ("Rahul", 2, 2, 17000)])
        self.assertEqual(summary["vendors"], [("Vendor A", 2, 2, 18000), ("Vendor B", 1, 0, 7000)])
        self.assertEqual(summary["days"], [("2026-10-08", 3, 2, 25000)])

    def test_weekly_summary_excludes_other_period(self):
        self.order(bhaji="Gavari")
        with self.db.connection:
            self.db.connection.execute("UPDATE periods SET status='closed' WHERE id=?", (self.period,))
        other = self.service.open_period("2026-10-12", "2026-10-16", self.amit.id, "amit@upi")
        self.assertEqual(self.service.weekly_summary(other)["total"], 0)
        self.assertEqual(self.service.weekly_summary(other)["orders"], [])

    def test_weekly_summary_empty_and_unknown(self):
        self.assertEqual(self.service.weekly_summary(self.period)["total"], 0)
        with self.assertRaises(ValidationError):
            self.service.weekly_summary(999)


if __name__ == "__main__":
    unittest.main()
