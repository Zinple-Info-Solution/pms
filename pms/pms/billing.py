# Copyright (c) 2026, admin and contributors
# Central rent-invoicing engine:
#  - make_rent_invoice()  -> called by the Lease form button AND the daily scheduler
#  - on_invoice_change()  -> Sales Invoice doc_events keep the Rent Schedule in sync

import frappe
from frappe.utils import flt, today, add_days


CHARGE_ITEM = "PMS Additional Charges"


def ensure_item(item_code, item_group="Services"):
    """Create a simple non-stock service Item if it doesn't exist."""
    if frappe.db.exists("Item", item_code):
        return item_code

    if not frappe.db.exists("Item Group", item_group):
        item_group = frappe.db.get_value("Item Group", {"is_group": 0}, "name")

    frappe.get_doc({
        "doctype": "Item",
        "item_code": item_code,
        "item_name": item_code,
        "item_group": item_group,
        "is_stock_item": 0,
        "is_sales_item": 1,
        "stock_uom": "Nos",
    }).insert(ignore_permissions=True)
    return item_code


@frappe.whitelist()
def make_rent_invoice(lease_name, schedule_row=None):
    """Create a draft Sales Invoice for the next Pending row of a lease's
    rent schedule (or a specific row). Returns the invoice name."""
    lease = frappe.get_doc("Lease Agreement", lease_name)

    if lease.docstatus != 1:
        frappe.throw("Lease Agreement must be submitted first.")
    if not lease.customer:
        frappe.throw(
            f"Lease <b>{lease.name}</b> has no linked Customer. "
            f"Open the Tenant <b>{lease.tenant}</b> and save it once to "
            f"auto-create the Customer, then reload the lease."
        )

    # Pick the schedule row
    row = None
    if schedule_row:
        row = next((r for r in lease.rent_schedule if r.name == schedule_row), None)
    else:
        row = next((r for r in lease.rent_schedule if r.status == "Pending"), None)

    if not row:
        frappe.throw("No pending row found in the Rent Collection Schedule.")
    if row.status != "Pending":
        frappe.throw(f"Schedule row for {row.billing_period} is already {row.status}.")

    monthly_rent = flt(lease.rent_amount) or flt(lease.total_rent)
    months = flt(row.rent_amount) / monthly_rent if monthly_rent else 1

    # --- Build items ---
    items = []

    if getattr(lease, "billing_based_on", None) == "Building Wise":
        # One consolidated line for the whole building
        unit_list = ", ".join(
            filter(None, [u.unit_id for u in lease.units])
        )
        items.append({
            "item_code": ensure_item(f"Building-{lease.building}"),
            "qty": months or 1,
            "uom": "Nos",
            "rate": monthly_rent,
            "description": " | ".join(filter(None, [
                f"Building rent {row.billing_period}",
                f"Building: {lease.building}",
                f"Units: {unit_list}" if unit_list else "",
                f"{len(lease.units)} unit(s)",
            ])),
            "custom_lease_agreement": lease.name,
        })
        return_items_built = True
    else:
        return_items_built = False

    for unit in (lease.units if not return_items_built else []):
        rate = flt(unit.monthly_rent) or monthly_rent
        items.append({
            "item_code": ensure_item(f"Building Unit-{unit.unit_type or 'Apartment'}"),
            "qty": months or 1,
            "uom": "Nos",
            "rate": rate,
            "asset": unit.unit_id or "",
            "description": " | ".join(filter(None, [
                f"Rent {row.billing_period}",
                f"Unit: {unit.unit_id}" if unit.unit_id else "",
                f"Type: {unit.unit_type}" if unit.unit_type else "",
                f"Floor: {unit.floor_no}" if unit.floor_no else "",
                f"Area: {unit.area_sqft} sq.ft" if unit.area_sqft else "",
            ])),
            "custom_lease_agreement": lease.name,
            "custom_unit_type": unit.unit_type or "",
            "custom_floor_no": unit.floor_no or 0,
            "custom_unit_no": unit.unit_id or 0,
            "custom_area_sqft": unit.area_sqft or 0,
        })

    # --- Additional charges as one line ---
    if flt(row.charges_amount):
        charge_names = ", ".join(
            c.charge_name for c in (lease.additional_charges or [])
        ) or "Additional charges"
        items.append({
            "item_code": ensure_item(CHARGE_ITEM),
            "qty": 1,
            "uom": "Nos",
            "rate": flt(row.charges_amount),
            "description": f"{charge_names} — {row.billing_period}",
            "custom_lease_agreement": lease.name,
        })

    si = frappe.get_doc({
        "doctype": "Sales Invoice",
        "customer": lease.customer,
        "posting_date": today(),
        "due_date": max(str(row.due_date), today()),
        "ignore_pricing_rule": 1,
        "items": items,
        "apply_discount_on": "Net Total",
        "discount_amount": flt(row.discount_amount),
        "remarks": "\n".join(filter(None, [
            f"Lease Agreement : {lease.name}",
            f"Tenant          : {lease.tenant}",
            f"Billing Period  : {row.billing_period}",
            f"Building        : {lease.building}" if lease.building else "",
        ])),
    })
    si.insert(ignore_permissions=True)

    # Mark the schedule row
    frappe.db.set_value("Rent Schedule", row.name, {
        "status": "Invoiced",
        "sales_invoice": si.name,
    })

    return si.name


def generate_due_invoices():
    """Called by the daily scheduler: auto-create invoices for every
    Pending schedule row that is due within the next 3 days."""
    rows = frappe.db.sql("""
        SELECT rs.name AS row_name, rs.parent AS lease
        FROM `tabRent Schedule` rs
        INNER JOIN `tabLease Agreement` la ON la.name = rs.parent
        WHERE rs.status = 'Pending'
          AND rs.due_date <= %s
          AND la.docstatus = 1
          AND la.status = 'Active'
        ORDER BY rs.due_date
    """, add_days(today(), 3), as_dict=True)

    for r in rows:
        try:
            invoice = make_rent_invoice(r.lease, r.row_name)
            lease_owner = frappe.db.get_value("Lease Agreement", r.lease, "owner")
            frappe.get_doc({
                "doctype": "Notification Log",
                "subject": f"Rent invoice {invoice} created for lease {r.lease}",
                "for_user": lease_owner,
                "type": "Alert",
                "document_type": "Sales Invoice",
                "document_name": invoice,
            }).insert(ignore_permissions=True)
        except Exception:
            frappe.log_error(
                frappe.get_traceback(),
                f"Auto rent invoice failed: lease {r.lease}",
            )


def on_invoice_change(doc, method=None):
    """Sales Invoice doc_events hook — keeps Rent Schedule status in sync.
    Submitted & fully paid -> Paid.  Cancelled -> back to Pending."""
    rows = frappe.get_all(
        "Rent Schedule",
        filters={"sales_invoice": doc.name},
        pluck="name",
    )
    if not rows:
        return

    for row_name in rows:
        if doc.docstatus == 2:
            frappe.db.set_value("Rent Schedule", row_name, {
                "status": "Pending",
                "sales_invoice": None,
            })
        elif doc.docstatus == 1 and flt(doc.outstanding_amount) <= 0:
            frappe.db.set_value("Rent Schedule", row_name, "status", "Paid")
        elif doc.docstatus == 1:
            frappe.db.set_value("Rent Schedule", row_name, "status", "Invoiced")


def on_payment_entry(doc, method=None):
    """Payment Entry hook — when rent invoices get paid (or payment is
    cancelled), refresh the linked Rent Schedule rows."""
    for ref in doc.references or []:
        if ref.reference_doctype != "Sales Invoice":
            continue

        rows = frappe.get_all(
            "Rent Schedule",
            filters={"sales_invoice": ref.reference_name},
            pluck="name",
        )
        if not rows:
            continue

        outstanding = flt(frappe.db.get_value(
            "Sales Invoice", ref.reference_name, "outstanding_amount"
        ))
        status = "Paid" if outstanding <= 0 else "Invoiced"
        for row_name in rows:
            frappe.db.set_value("Rent Schedule", row_name, "status", status)
