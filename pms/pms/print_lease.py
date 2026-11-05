# Copyright (c) 2026, admin and contributors
"""Data for the Lease Agreement Contract print format: the details that live
on other doctypes (owner, tenant, unit, late fee rule), read in one place so
the template only has to lay them out."""

import frappe
from dateutil.relativedelta import relativedelta
from frappe.contacts.doctype.address.address import get_address_display
from frappe.utils import add_days, flt, getdate


def get_lease_print_data(doc):
    from pms.pms.billing import get_lease_company

    company = get_lease_company(doc)
    address = doc.address or frappe.db.get_value("Property", doc.building, "address")
    return frappe._dict(
        company=company,
        currency=frappe.get_cached_value("Company", company, "default_currency")
        or frappe.db.get_default("currency"),
        owners=_get_owners(doc.building),
        tenant=frappe.get_doc("Tenant", doc.tenant),
        property_address=get_address_display(address) if address else "",
        units=_get_units(doc),
        recurring_charges=_get_charges(doc, "Recurring"),
        one_time_charges=_get_charges(doc, "One Time"),
        late_fee=_get_late_fee(doc),
        term=_get_term(doc.start_date, doc.end_date),
    )


def _get_owners(building):
    """The property's owners, primary owner first."""
    rows = frappe.get_all(
        "Property Owner",
        filters={"parent": building, "parenttype": "Property"},
        fields=["owner_id"],
        order_by="is_primary desc, idx",
    )
    return [
        frappe.db.get_value("Owner", row.owner_id, ["owner_name", "email", "mobile_no"], as_dict=True)
        for row in rows
    ]


def _get_units(doc):
    """The lease's unit rows, with anything blank filled in from the Unit."""
    units = []
    for row in doc.get("units") or []:
        unit = frappe.db.get_value(
            "Unit", row.unit_id, ["unit_type", "floor_no", "area_sqft"], as_dict=True
        ) or frappe._dict()
        units.append(
            frappe._dict(
                unit_id=row.unit_id,
                unit_type=row.unit_type or unit.unit_type,
                floor_no=row.floor_no or unit.floor_no,
                area_sqft=row.area_sqft or unit.area_sqft,
                monthly_rent=row.monthly_rent,
            )
        )
    return units


def _get_charges(doc, charge_type):
    """Additional charges and applied facility charges of one type."""
    charges = [
        frappe._dict(name=row.charge_name, amount=row.amount)
        for row in doc.get("additional_charges") or []
        if row.charge_type == charge_type
    ]
    charges += [
        frappe._dict(name=row.facility, amount=row.amount)
        for row in doc.get("facilities") or []
        if row.apply and row.charge_type == charge_type
    ]
    return charges


def _get_late_fee(doc):
    from pms.pms.billing import get_late_fee_rule

    rule = get_late_fee_rule(doc.building)
    if not rule or not (flt(rule.fee_amount) or flt(rule.fee_percent)):
        return None
    return frappe._dict(
        grace_days=rule.grace_period_days,
        is_percent=rule.fee_type == "Percent of Rent",
        amount=rule.fee_amount,
        percent=rule.fee_percent,
    )


def _get_term(start_date, end_date):
    """The lease length in words, counting the end date as a full day:
    1 Jan to 31 Dec is "12 months"."""
    if not (start_date and end_date):
        return ""
    gap = relativedelta(add_days(getdate(end_date), 1), getdate(start_date))
    parts = [
        (gap.years * 12 + gap.months, "month"),
        (gap.days, "day"),
    ]
    return " and ".join(f"{count} {name}{'s' if count != 1 else ''}" for count, name in parts if count)
