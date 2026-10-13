# NovusNexus Tiffin

Local Python CLI — first milestone: setup, daily menus and individual orders.
Python 3.11+ is required; no third-party dependencies are needed.

Run from the repository directory:

```powershell
python -m tiffin
python -m tiffin --db data/demo.sqlite3
python -m unittest discover -s tests -v
```

If Windows cannot find Python, use your installed Python executable's full path.
The default database is `data/tiffin.sqlite3`; it persists between runs and is
excluded from Git. Use a separate demo database while reviewing this milestone.

Start by adding employees and a vendor, configuring vendor prices, opening a
billing period with its coordinator and UPI ID, publishing a menu, and entering
an order. IDs are displayed in selection lists. Dates use YYYY-MM-DD and prices
are entered in rupees. Each saved order is one tiffin. Late orders need an explicit
vendor-approved override reason. The CLI shows an order preview before saving.

Billing, payments, handovers and backup/restore are upcoming milestones; do not
use this first slice as a complete financial ledger. See docs/architecture.md
for the class responsibilities, implementation choices and agreed future rules.


Information screens: option 9 lists employees; option 10 lists vendors and their
configured prices. Option 11 selects a billing period and shows weekly orders,
totals by billed employee, vendor and date, and itemized order details. Amounts
include extra chapatis and use saved order prices. These are order totals,
not payment balances. All record lists use readable tables and employee/vendor names.
