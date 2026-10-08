"""Human-readable terminal presentation; amounts are integer paise."""


def inr(paise):
    return f"INR {paise // 100:,}.{paise % 100:02d}"


def table(headers, rows, empty="No records found."):
    rows = [[str(value) if value is not None else "-" for value in row] for row in rows]
    if not rows:
        print(empty)
        return
    widths = [max(len(str(header)), *(len(row[i]) for row in rows)) for i, header in enumerate(headers)]
    def line(row):
        return " | ".join(str(cell).ljust(width) for cell, width in zip(row, widths))
    print(line(headers))
    print("-+-".join("-" * width for width in widths))
    for row in rows:
        print(line(row))


def order_table(orders):
    table(["Order", "Date", "Vendor", "Recipient", "Placed by", "Billed to", "Tiffin", "Bhaji", "Extras", "Amount"],
          [(o["id"], o["day"], o["vendor"], o["recipient"], o["placed_by"], o["billed_to"],
            o["tiffin_type"], o["bhaji"], o["extra_chapatis"], inr(o["total"])) for o in orders],
          empty="No orders found.")


def show_week(service, period_id):
    summary = service.weekly_summary(period_id)
    period = summary["period"]
    coordinator = service._require("employees", period["coordinator_id"])["name"]
    print(f"\nWeekly order summary: {period['start']} to {period['end']}")
    print(f"Coordinator: {coordinator} | Status: {period['status'].title()} | UPI: {period['upi']}")
    print(f"Orders: {len(summary['orders'])} | Extra chapatis: "
          f"{sum(o['extra_chapatis'] for o in summary['orders'])} | Total: {inr(summary['total'])}")
    if not summary["orders"]:
        print("No orders in this billing period.")
        return
    for title, key, heading in [("By employee (billed to)", "employees", "Employee"),
                                ("By vendor", "vendors", "Vendor"), ("By date", "days", "Date")]:
        print("\n" + title)
        table([heading, "Tiffins", "Extra chapatis", "Order amount"],
              [(name, count, extras, inr(total)) for name, count, extras, total in summary[key]])
    print("\nOrder details")
    order_table(summary["orders"])
