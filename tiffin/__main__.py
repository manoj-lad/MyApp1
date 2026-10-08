import argparse
import sqlite3
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path

from .domain import TiffinType
from .services import TiffinService
from .storage import Database
from .presentation import table, table as show_table, inr, order_table, show_week


def ask(label, default=None):
    value = input(f"{label}" + (f" [{default}]" if default is not None else "") + ": ").strip()
    return value or (str(default) if default is not None else "")


def money(label):
    value = Decimal(ask(label)) * 100
    if not value.is_finite() or value < 0 or value != value.to_integral_value():
        raise ValueError("Enter a non-negative price with at most two decimal places")
    return int(value)


def choose(db, table):
    rows = db.rows(f"SELECT * FROM {table} ORDER BY id")
    if not rows:
        raise ValueError(f"No {table} yet; create one first")
    if table == "periods":
        show_table(["ID", "Start", "End", "Coordinator", "Status"],
            [(r["id"], r["start"], r["end"],
              db.rows("SELECT name FROM employees WHERE id=?", (r["coordinator_id"],))[0]["name"],
              r["status"].title()) for r in rows])
    elif table == "menus":
        show_table(["ID", "Date", "Vendor", "Period", "Cutoff"],
            [(r["id"], r["day"], db.rows("SELECT name FROM vendors WHERE id=?", (r["vendor_id"],))[0]["name"],
              r["period_id"], r["cutoff"]) for r in rows])
    else:
        show_table(["ID", "Name"], [(r["id"], r["name"]) for r in rows])
    identifier = int(ask("Select ID"))
    if identifier not in [r["id"] for r in rows]:
        raise ValueError("Choose a displayed ID")
    return identifier


def kind():
    options = list(TiffinType)
    for index, item in enumerate(options, 1):
        print(f"{index}. {item.value}")
    index = int(ask("Tiffin type"))
    if not 1 <= index <= len(options):
        raise ValueError("Choose a displayed type")
    return options[index - 1]


def main():
    parser = argparse.ArgumentParser(description="NovusNexus Tiffin — first milestone")
    parser.add_argument("--db", default="data/tiffin.sqlite3", help="Local database path")
    args = parser.parse_args()
    path = Path(args.db)
    path.parent.mkdir(parents=True, exist_ok=True)
    db = Database(path)
    service = TiffinService(db)
    try:
        while True:
            print("\nNovusNexus Tiffin\n1. Add employee\n2. Add vendor\n3. Set vendor price"
                  "\n4. Open billing period / assign coordinator\n5. Publish daily menu"
                  "\n6. Enter one order\n7. Vendor summary\n8. List orders\n9. Employee Info\n10. Vendor Info\n11. Weekly order summary\n0. Exit")
            try:
                action = ask("Action")
                if action == "0":
                    break
                if action == "1":
                    employee = service.add_employee(ask("Employee name"))
                    print(f"Employee added: {employee.name} (ID {employee.id})")
                elif action == "2":
                    vendor = service.add_vendor(ask("Vendor name"))
                    print(f"Vendor added: {vendor.name} (ID {vendor.id})")
                elif action == "3":
                    vendor = choose(db, "vendors")
                    selection = kind()
                    service.set_offering(vendor, selection, money("Tiffin price (INR)"),
                        money("Extra chapati price (INR)") if selection.requires_bhaji else 0)
                    print("Price saved")
                elif action == "4":
                    monday = date.today() - timedelta(days=date.today().weekday())
                    start = ask("Start date YYYY-MM-DD", monday.isoformat())
                    end = ask("End date YYYY-MM-DD", (date.fromisoformat(start) + timedelta(days=4)).isoformat())
                    employee = choose(db, "employees")
                    upi = ask("Coordinator UPI ID")
                    if ask(f"Open {start} to {end}, coordinator {employee}, UPI {upi}? y/n", "n").lower() == "y":
                        print("Period ID:", service.open_period(start, end, employee, upi))
                elif action == "5":
                    period = choose(db, "periods")
                    vendor = choose(db, "vendors")
                    offerings = db.rows("SELECT kind FROM offerings WHERE vendor_id=?", (vendor,))
                    for index, item in enumerate(offerings, 1):
                        print(index, item["kind"])
                    indices = [int(v.strip()) for v in ask("Available offering numbers, comma-separated").split(",")]
                    if any(i < 1 or i > len(offerings) for i in indices):
                        raise ValueError("Choose displayed offerings")
                    day = ask("Menu date", date.today().isoformat())
                    bhajis = ask("Bhajis, comma-separated (blank if none)").split(",")
                    cutoff = ask("Cutoff HH:MM", "12:00")
                    print("Menu ID:", service.publish_menu(period, day, vendor,
                        [offerings[i - 1]["kind"] for i in indices], bhajis, cutoff))
                elif action == "6":
                    menu_id = choose(db, "menus")
                    menu = service._require("menus", menu_id)
                    period = service._require("periods", menu["period_id"])
                    recipient = choose(db, "employees")
                    requester = int(ask("Placed by employee ID", recipient))
                    billed = int(ask("Billed to employee ID", recipient))
                    selection = kind()
                    if selection.requires_bhaji:
                        print("Bhajis:", ", ".join(r["name"] for r in db.rows("SELECT name FROM bhajis WHERE menu_id=?", (menu_id,))))
                    bhaji = ask("Bhaji") if selection.requires_bhaji else None
                    extras = int(ask("Extra chapatis", 0)) if selection.requires_bhaji else 0
                    reason = ask("Vendor-approved late override reason (blank normally)") or None
                    prices = db.rows("SELECT * FROM menu_offerings WHERE menu_id=? AND kind=?", (menu_id, selection.value))
                    if not prices:
                        raise ValueError("Tiffin unavailable")
                    total = prices[0]["price"] + extras * prices[0]["extra_price"]
                    print(f"Recipient {recipient}; requester {requester}; billed to {billed}; "
                          f"{selection.value}; bhaji {bhaji}; extras {extras}; total INR {total / 100:.2f}")
                    if ask("Save order? y/n", "n").lower() == "y":
                        order = service.place_order(menu_id, selection, recipient, period["coordinator_id"],
                            bhaji, extras, requester, billed, reason)
                        print(f"Saved order {order.id}. Choose Enter one order again for another tiffin.")
                elif action == "7":
                    menu_id = choose(db, "menus")
                    menu = service._require("menus", menu_id)
                    vendor = service._require("vendors", menu["vendor_id"])
                    print(f"\nVendor summary: {vendor['name']} — {menu['day']}")
                    table(["Tiffin", "Bhaji", "Tiffins", "Extra chapatis"],
                        [(r["tiffin_type"], r["bhaji"], r["tiffins"], r["extra_chapatis"])
                         for r in service.vendor_summary(menu_id)], empty="No orders on this menu.")
                elif action == "8":
                    print("\nAll orders")
                    order_table(service.order_details())
                elif action == "9":
                    print("\nEmployee Info")
                    table(["ID", "Employee name"], [(r["id"], r["name"])
                        for r in db.rows("SELECT * FROM employees ORDER BY name")], empty="No employees added yet.")
                elif action == "10":
                    print("\nVendor Info")
                    vendors = db.rows("SELECT * FROM vendors ORDER BY name")
                    if not vendors:
                        print("No vendors added yet.")
                    for vendor in vendors:
                        print(f"\n{vendor['name']} (ID {vendor['id']})")
                        offerings = db.rows("SELECT * FROM offerings WHERE vendor_id=? ORDER BY kind", (vendor["id"],))
                        table(["Tiffin", "Price", "Extra chapati price"],
                            [(o["kind"], inr(o["price"]), inr(o["extra_price"]) if TiffinType(o["kind"]).requires_bhaji else "Not available")
                             for o in offerings], empty="No prices configured yet.")
                elif action == "11":
                    show_week(service, choose(db, "periods"))
                else:
                    print("Choose a displayed action")
            except (ValueError, sqlite3.Error, InvalidOperation) as error:
                print(f"Could not complete action: {error}")
    except (EOFError, KeyboardInterrupt):
        print("\nExiting")
    finally:
        db.close()


if __name__ == "__main__":
    main()
