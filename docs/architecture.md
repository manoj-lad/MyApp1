# First implementation milestone

CLI -> TiffinService -> Database (SQLite). Domain classes represent employees,
vendors, tiffin types, and individual orders. The service validates operations;
storage owns database connections. Prices are integer paise. Each order means
one tiffin; quantity is deliberately absent. CLI requester defaults to recipient.
The billing recipient defaults to recipient but may be the requester instead.

This slice uses standard-library prompts and sqlite3 rather than the proposed
Typer/Rich/SQLAlchemy/Alembic stack. This avoids installation requirements while
we review the first flow. There is no schema migration mechanism yet: this initial
schema must be migrated explicitly before changing a database containing real data.
Services are deliberately grouped for this milestone; they can be split into
OrderService, MenuService and BillingPeriodService as workflows grow.

Implemented: employees, vendors, standard offerings, period creation with coordinator
and UPI destination, daily menus with multiple vendors, order entry, price snapshots,
cutoff overrides, and vendor summaries. One nonoverlapping open period is allowed.

Pending: coordinator handover/history, menu/order editing, summary-sent tracking,
cancellation acceptance/rejection, period closure/reopening and bill revisions,
employee receipts/credits/refunds, vendor settlements, reports, backup/restore.
No payment or billing screens are represented as complete in this milestone.

Future rules: a handover transfers the period's collection responsibility to its
latest coordinator; older periods retain their final coordinator. Collections
normally happen at period close. Payments preserve the actual receiver. Accepted
cancellations remove both charges; rejected cancellations retain both. Payments
and vendor settlements allow multiple partial receipts/payments. Overpayments
remain period-specific credits, with explicit refunds and no automatic carry-forward.

Version 2 adds authenticated LAN web access through services. Version 3 adds AI
through those same validated operations. Neither interface should issue SQL directly.
