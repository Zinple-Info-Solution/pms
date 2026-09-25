# Copyright (c) 2026, admin and contributors
# Central rent-invoicing engine:
#  - make_rent_invoice()  -> called by the Lease form button AND the daily scheduler
#  - on_invoice_change()  -> Sales Invoice doc_events keep the Rent Schedule in sync

import frappe
from frappe.utils import flt, today, add_days, getdate


CHARGE_ITEM = "PMS Additional Charges"
FACILITY_ITEM_PREFIX = "Facility-"


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
            "custom_unit": unit.unit_id or "",
            "custom_area_sqft": unit.area_sqft or 0,
        })

    # --- Facility charges: one line per facility -------------------------
    # One-time facilities are billed only on the very first cycle, exactly the
    # way generate_rent_schedule() built the numbers.
    is_first_cycle = (row.idx == 1)
    facility_total = 0

    for fac in (getattr(lease, "facilities", None) or []):
        if not fac.apply or not flt(fac.amount):
            continue

        if fac.charge_type == "One Time":
            if not is_first_cycle:
                continue
            qty, rate, kind = 1, flt(fac.amount), "one time"
        else:
            qty, rate, kind = (months or 1), flt(fac.amount), "per month"

        line_total = flt(rate) * flt(qty)
        facility_total += line_total

        items.append({
            "item_code": ensure_item(f"{FACILITY_ITEM_PREFIX}{fac.facility}"),
            "qty": qty,
            "uom": "Nos",
            "rate": rate,
            "custom_unit": fac.unit or "",
            "description": " | ".join(filter(None, [
                f"Facility: {fac.facility} ({kind})",
                f"Unit: {fac.unit}" if fac.unit else "",
                f"Period: {row.billing_period}",
                fac.remarks or "",
            ])),
            "custom_lease_agreement": lease.name,
        })

    # --- Remaining additional charges as one line ------------------------
    other_charges = flt(row.charges_amount) - flt(facility_total)

    if other_charges > 0.005:
        charge_names = ", ".join(
            c.charge_name for c in (lease.additional_charges or []) if c.charge_name
        ) or "Additional charges"
        items.append({
            "item_code": ensure_item(CHARGE_ITEM),
            "qty": 1,
            "uom": "Nos",
            "rate": other_charges,
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


def apply_late_fees():
    """Runs daily: scan Pending Rent Schedule rows on Active leases past
    their rule's grace period and add the fee onto that row's
    charges_amount/total_amount — which then flows automatically into the
    "Additional charges" invoice line the next time make_rent_invoice()
    runs for it. Applied once per row (late_fee_applied guards against
    re-applying on every daily run)."""
    rows = frappe.db.sql("""
        SELECT rs.name, rs.parent AS lease, rs.due_date, rs.charges_amount,
               rs.total_amount, la.building AS property, la.rent_amount
        FROM `tabRent Schedule` rs
        INNER JOIN `tabLease Agreement` la ON la.name = rs.parent
        WHERE rs.status = 'Pending'
          AND rs.late_fee_applied = 0
          AND la.docstatus = 1
          AND la.status = 'Active'
    """, as_dict=True)

    for r in rows:
        try:
            rule = get_late_fee_rule(r.property)
            if not rule:
                continue

            overdue_days = (getdate(today()) - getdate(r.due_date)).days
            if overdue_days < rule.grace_period_days:
                continue

            if rule.fee_type == "Flat":
                fee = flt(rule.fee_amount)
            else:
                fee = flt(r.rent_amount) * flt(rule.fee_percent) / 100

            if fee <= 0:
                continue

            frappe.db.set_value("Rent Schedule", r.name, {
                "charges_amount": flt(r.charges_amount) + fee,
                "total_amount": flt(r.total_amount) + fee,
                "late_fee_amount": fee,
                "late_fee_applied": 1,
            })
        except Exception:
            frappe.log_error(
                frappe.get_traceback(),
                f"Late fee application failed: {r.lease} / {r.name}",
            )


def get_late_fee_rule(property_name):
    """Property-specific rule takes priority over a blank (applies-to-all) one."""
    rule_name = frappe.db.get_value(
        "Late Fee Rule", {"property": property_name, "is_active": 1}, "name"
    ) or frappe.db.sql(
        """
        SELECT name FROM `tabLate Fee Rule`
        WHERE (property IS NULL OR property = '') AND is_active = 1
        LIMIT 1
        """
    )
    if isinstance(rule_name, list):
        rule_name = rule_name[0][0] if rule_name else None
    return frappe.get_doc("Late Fee Rule", rule_name) if rule_name else None


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


DEPOSIT_LIABILITY_ACCOUNT_NAME = "Tenant Security Deposits"


def on_move_out(doc, method=None):
    """Move Out doc_event (on_submit): put the unit into make-ready and
    draft a Security Deposit Settlement so the deposit refund/deduction
    flow can proceed."""
    frappe.db.set_value("Unit", doc.unit, "status", "Under Maintenance")

    if doc.settlement:
        return

    settlement = frappe.get_doc({
        "doctype": "Security Deposit Settlement",
        "lease": doc.lease,
        "move_out": doc.name,
    })
    settlement.insert(ignore_permissions=True)
    doc.db_set("settlement", settlement.name)

    frappe.msgprint(
        f"Security Deposit Settlement <b>{settlement.name}</b> drafted.",
        indicator="blue", alert=True,
    )


def get_deposit_liability_account(company=None):
    company = company or frappe.db.get_single_value("Global Defaults", "default_company")
    account_name = f"{DEPOSIT_LIABILITY_ACCOUNT_NAME} - {frappe.get_cached_value('Company', company, 'abbr')}"
    if not frappe.db.exists("Account", account_name):
        frappe.throw(
            f"Account <b>{account_name}</b> not found. Run the "
            f"create_deposit_liability_account patch first."
        )
    return account_name


def settle_security_deposit(settlement):
    """Called from Security Deposit Settlement.on_submit(). Books the
    deduction portion (if any) via a Journal Entry against the deposit
    liability account, and pays out the refund portion (if positive) via
    a Payment Entry to the tenant's Customer. If deductions exceed the
    deposit, no auto-payment is made — the shortfall is left for manual
    follow-up (billing/collections), which is out of scope here."""
    lease = frappe.get_doc("Lease Agreement", settlement.lease)
    deposit_account = get_deposit_liability_account(
        frappe.db.get_value("Sales Invoice", {"customer": lease.customer}, "company")
        or frappe.db.get_single_value("Global Defaults", "default_company")
    )

    if flt(settlement.total_deductions) > 0:
        default_income_account = frappe.get_cached_value(
            "Company", frappe.db.get_single_value("Global Defaults", "default_company"), "default_income_account"
        )
        je = frappe.get_doc({
            "doctype": "Journal Entry",
            "voucher_type": "Journal Entry",
            "posting_date": frappe.utils.today(),
            "user_remark": f"Security deposit deductions for lease {lease.name} ({settlement.name})",
            "accounts": [
                {
                    "account": deposit_account,
                    "debit_in_account_currency": flt(settlement.total_deductions),
                    "party_type": "Customer",
                    "party": lease.customer,
                },
                {
                    "account": default_income_account,
                    "credit_in_account_currency": flt(settlement.total_deductions),
                },
            ],
        })
        je.insert(ignore_permissions=True)
        je.submit()
        settlement.db_set("journal_entry", je.name)

    if flt(settlement.refund_amount) > 0:
        company = frappe.db.get_single_value("Global Defaults", "default_company")
        bank_or_cash = (
            frappe.get_cached_value("Company", company, "default_bank_account")
            or frappe.get_cached_value("Company", company, "default_cash_account")
        )
        # payment_type "Pay": paid_from = the source of funds (bank/cash),
        # paid_to = the party's account (here, the deposit liability being
        # drawn down) — matches erpnext.accounts.doctype.payment_entry
        # .payment_entry.get_payment_entry()'s own from/to convention.
        pe = frappe.get_doc({
            "doctype": "Payment Entry",
            "payment_type": "Pay",
            "party_type": "Customer",
            "party": lease.customer,
            "paid_from": bank_or_cash,
            "paid_to": deposit_account,
            "paid_amount": flt(settlement.refund_amount),
            "received_amount": flt(settlement.refund_amount),
            "reference_no": settlement.name,
            "reference_date": frappe.utils.today(),
            "remarks": f"Security deposit refund for lease {lease.name} ({settlement.name})",
        })
        pe.insert(ignore_permissions=True)
        pe.submit()
        settlement.db_set("payment_entry", pe.name)
    elif flt(settlement.refund_amount) < 0:
        frappe.msgprint(
            f"Deductions exceed the deposit by "
            f"{frappe.format_value(-flt(settlement.refund_amount), {'fieldtype': 'Currency'})}. "
            f"No automatic payment created — follow up manually for collection.",
            indicator="orange", alert=True,
        )


def create_vendor_bill(work_order):
    """Create a Purchase Invoice against a Work Order's vendor once it's
    Completed with an actual cost recorded. Cost-centered to the Property
    so Phase 6's Owner Statements can pick it up correctly."""
    item_code = ensure_item("Maintenance Service", item_group="Services")
    cost_center = frappe.db.get_value("Property", work_order.property, "cost_center")

    pi = frappe.get_doc({
        "doctype": "Purchase Invoice",
        "supplier": work_order.vendor,
        "posting_date": frappe.utils.today(),
        "due_date": frappe.utils.today(),
        "items": [{
            "item_code": item_code,
            "qty": 1,
            "uom": "Nos",
            "rate": flt(work_order.actual_cost),
            "cost_center": cost_center,
            "description": (
                f"Maintenance work order {work_order.name} — "
                f"{work_order.description or work_order.priority + ' priority'}"
            ),
        }],
        "remarks": f"Work Order: {work_order.name}\nProperty: {work_order.property}",
    })
    pi.insert(ignore_permissions=True)
    work_order.db_set("purchase_invoice", pi.name)

    frappe.msgprint(
        f"Vendor bill <b>{pi.name}</b> created for Work Order <b>{work_order.name}</b>.",
        indicator="green", alert=True,
    )
    return pi.name


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
