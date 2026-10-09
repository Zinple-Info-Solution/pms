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


DEPOSIT_ITEM = "Security Deposit"


@frappe.whitelist()
def make_deposit_invoice(lease_name):
    """Invoice the security deposit once, right after lease submission.
    Returns None (not an error) if there's nothing to invoice or it was
    already invoiced — safe to call more than once."""
    lease = frappe.get_doc("Lease Agreement", lease_name)
    if not flt(lease.security_deposit):
        return None
    if frappe.db.exists("Sales Invoice Item", {
        "custom_lease_agreement": lease.name, "item_code": ensure_item(DEPOSIT_ITEM),
    }):
        return None

    cost_center = frappe.db.get_value("Property", lease.building, "cost_center")
    si = frappe.get_doc({
        "doctype": "Sales Invoice",
        "customer": lease.customer,
        "posting_date": today(),
        "due_date": today(),
        "ignore_pricing_rule": 1,
        "items": [{
            "item_code": ensure_item(DEPOSIT_ITEM),
            "qty": 1,
            "uom": "Nos",
            "rate": flt(lease.security_deposit),
            "cost_center": cost_center,
            "custom_lease_agreement": lease.name,
            "description": f"Security deposit — Lease {lease.name}",
        }],
        "remarks": f"Security deposit for Lease Agreement {lease.name}",
    })
    si.insert(ignore_permissions=True)
    return si.name


def email_invoice_to_tenant(invoice_name):
    """Email the tenant a copy of the invoice with a link to pay it on the
    portal. Best-effort — a missing email address just skips silently
    rather than blocking lease/invoice creation."""
    if not invoice_name:
        return
    si = frappe.get_doc("Sales Invoice", invoice_name)
    email = frappe.db.get_value("Customer", si.customer, "email_id") or frappe.db.get_value(
        "Tenant", {"customer": si.customer}, "email"
    )
    if not email:
        return

    pay_url = frappe.utils.get_url(f"/my-lease")
    try:
        frappe.sendmail(
            recipients=[email],
            subject=f"Invoice {si.name} — {frappe.format_value(si.grand_total, {'fieldtype': 'Currency'})} due {si.due_date}",
            message=(
                f"<p>An invoice of <b>{frappe.format_value(si.grand_total, {'fieldtype': 'Currency'})}</b> "
                f"has been raised, due on <b>{si.due_date}</b>.</p>"
                f"<p><a href='{pay_url}'>View and pay on your tenant portal</a></p>"
            ),
            delayed=True,
        )
    except Exception:
        frappe.log_error(frappe.get_traceback(), f"email_invoice_to_tenant failed: {invoice_name}")


def send_payment_receipt(payment_entry_name):
    """Best-effort receipt email to the payer when a Payment Entry against
    a rent-linked Sales Invoice is submitted."""
    pe = frappe.get_doc("Payment Entry", payment_entry_name)
    if pe.party_type != "Customer" or not pe.party:
        return
    email = frappe.db.get_value("Customer", pe.party, "email_id") or frappe.db.get_value(
        "Tenant", {"customer": pe.party}, "email"
    )
    if not email:
        return
    try:
        frappe.sendmail(
            recipients=[email],
            subject=f"Payment received — {frappe.format_value(pe.paid_amount, {'fieldtype': 'Currency'})}",
            message=(
                f"<p>We've received your payment of "
                f"<b>{frappe.format_value(pe.paid_amount, {'fieldtype': 'Currency'})}</b>. Thank you.</p>"
            ),
            delayed=True,
        )
    except Exception:
        frappe.log_error(frappe.get_traceback(), f"send_payment_receipt failed: {payment_entry_name}")


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
    cost_center = frappe.db.get_value("Property", lease.building, "cost_center")

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
            "cost_center": cost_center,
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
            "cost_center": cost_center,
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
            "cost_center": cost_center,
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
            "cost_center": cost_center,
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
    Pending schedule row that is due within the next 5 days, and email
    each one to the tenant with a link to pay it on the portal."""
    rows = frappe.db.sql("""
        SELECT rs.name AS row_name, rs.parent AS lease
        FROM `tabRent Schedule` rs
        INNER JOIN `tabLease Agreement` la ON la.name = rs.parent
        WHERE rs.status = 'Pending'
          AND rs.due_date <= %s
          AND la.docstatus = 1
          AND la.status = 'Active'
        ORDER BY rs.due_date
    """, add_days(today(), 5), as_dict=True)

    for r in rows:
        try:
            invoice = make_rent_invoice(r.lease, r.row_name)
            email_invoice_to_tenant(invoice)
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
    """Move Out doc_event (on_submit): put the unit into make-ready, create
    the cleaning/repair work order, and draft a Security Deposit
    Settlement (pre-filled by comparing this checklist against the
    original Move In) so the deposit refund/deduction flow can proceed."""
    frappe.db.set_value("Unit", doc.unit, "status", "Under Maintenance")
    _create_make_ready_work_order(doc)

    if doc.settlement:
        return

    settlement = frappe.get_doc({
        "doctype": "Security Deposit Settlement",
        "lease": doc.lease,
        "move_out": doc.name,
        "deductions": _suggest_deductions_from_inspection_diff(doc),
    })
    settlement.insert(ignore_permissions=True)
    doc.db_set("settlement", settlement.name)

    frappe.msgprint(
        f"Security Deposit Settlement <b>{settlement.name}</b> drafted.",
        indicator="blue", alert=True,
    )


def _create_make_ready_work_order(move_out):
    property_name = frappe.db.get_value("Unit", move_out.unit, "property")
    frappe.get_doc({
        "doctype": "Work Order",
        "property": property_name,
        "unit": move_out.unit,
        "priority": "Medium",
        "description": f"Make-ready cleaning/repairs after move-out ({move_out.name})",
        "is_make_ready": 1,
    }).insert(ignore_permissions=True)


def _suggest_deductions_from_inspection_diff(move_out):
    """Compare this Move Out's condition checklist against the matching
    Move In (same lease + unit) and suggest a deduction row (amount left
    at 0, for staff to fill in) for every item whose condition got worse.
    Never auto-approved — the Settlement stays a draft the Property
    Manager reviews and edits before submitting."""
    move_ins = frappe.get_all(
        "Move In",
        filters={"lease": move_out.lease, "unit": move_out.unit, "docstatus": 1},
        order_by="creation desc",
        limit=1,
        pluck="name",
    )
    if not move_ins:
        return []
    move_in_name = move_ins[0]

    condition_rank = {"Good": 0, "Fair": 1, "Damaged": 2, "Missing": 3}
    move_in_items = {
        row.item: row
        for row in frappe.get_all(
            "Move In Checklist Item",
            filters={"parent": move_in_name, "parenttype": "Move In"},
            fields=["item", "condition"],
        )
    }

    suggestions = []
    for row in move_out.condition_checklist or []:
        before = move_in_items.get(row.item)
        if not before:
            continue
        if condition_rank.get(row.condition, 0) > condition_rank.get(before.condition, 0):
            suggestions.append({
                "reason": f"{row.item}: {before.condition} at move-in -> {row.condition} at move-out",
                "deduction_type": "Damage",
                "amount": 0,
            })
    return suggestions


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
        shortfall = -flt(settlement.refund_amount)
        cost_center = frappe.db.get_value("Property", lease.building, "cost_center")
        si = frappe.get_doc({
            "doctype": "Sales Invoice",
            "customer": lease.customer,
            "posting_date": frappe.utils.today(),
            "due_date": frappe.utils.today(),
            "ignore_pricing_rule": 1,
            "items": [{
                "item_code": ensure_item(DEPOSIT_ITEM),
                "qty": 1,
                "uom": "Nos",
                "rate": shortfall,
                "cost_center": cost_center,
                "description": f"Deposit shortfall — Lease {lease.name} ({settlement.name})",
            }],
            "remarks": f"Deposit deductions exceeded the deposit held for Lease {lease.name}.",
        })
        si.insert(ignore_permissions=True)
        settlement.db_set("shortfall_invoice", si.name)
        email_invoice_to_tenant(si.name)
        frappe.msgprint(
            f"Deductions exceed the deposit by {frappe.format_value(shortfall, {'fieldtype': 'Currency'})}. "
            f"Shortfall invoice <b>{si.name}</b> raised against the tenant.",
            indicator="orange", alert=True,
        )

    frappe.db.set_value("Lease Agreement", lease.name, "status", "Terminated")


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


def get_active_customer_for_unit(unit):
    """Return the Customer on the currently Active (or Notice Given)
    submitted Lease Agreement covering this unit, or None."""
    row = frappe.db.sql("""
        SELECT la.customer
        FROM `tabLease Agreement` la
        INNER JOIN `tabLease Agreement Unit` lau ON lau.parent = la.name
        WHERE lau.unit_id = %s AND la.docstatus = 1 AND la.status IN ('Active', 'Notice Given')
        LIMIT 1
    """, unit)
    return row[0][0] if row and row[0][0] else None


def create_tenant_recharge_invoice(work_order):
    """Bill the current tenant of a Work Order's unit directly (e.g.
    tenant-caused damage) instead of charging the owner."""
    customer = get_active_customer_for_unit(work_order.unit)
    if not customer:
        frappe.throw(
            f"No active tenant found for unit <b>{work_order.unit}</b> to recharge."
        )

    cost_center = frappe.db.get_value("Property", work_order.property, "cost_center")
    si = frappe.get_doc({
        "doctype": "Sales Invoice",
        "customer": customer,
        "posting_date": frappe.utils.today(),
        "due_date": frappe.utils.today(),
        "ignore_pricing_rule": 1,
        "items": [{
            "item_code": ensure_item("Maintenance Recharge", item_group="Services"),
            "qty": 1,
            "uom": "Nos",
            "rate": flt(work_order.actual_cost),
            "cost_center": cost_center,
            "description": f"Maintenance recharge — Work Order {work_order.name}: {work_order.description or ''}",
        }],
        "remarks": f"Tenant recharge for Work Order: {work_order.name}",
    })
    si.insert(ignore_permissions=True)
    work_order.db_set("sales_invoice", si.name)
    email_invoice_to_tenant(si.name)

    frappe.msgprint(
        f"Tenant recharge invoice <b>{si.name}</b> created for Work Order <b>{work_order.name}</b>.",
        indicator="orange", alert=True,
    )
    return si.name


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

        if doc.docstatus == 1 and status == "Paid":
            send_payment_receipt(doc.name)
