# Copyright (c) 2026, admin and contributors
# ---------------------------------------------------------------------------
# Data for the Financial Management page (/app/pms-financial-management).
#
# For now this returns SAMPLE numbers only. The page reads nothing but the
# payload below, so moving to live data later means replacing
# _sample_data() with real queries that return the same shape — no page
# changes needed. `is_sample` drives the "Sample data" badge on the page.
#
# Payload shape:
#   currency, refreshed_at, is_sample
#   kpis:   {key: {"value": number, "format": "currency"|"percent", "note": str}}
#   occupancy_trend:      {labels: [6 months], values: [%]}
#   billed_vs_collected:  {labels, billed: [...], collected: [...]}
#   income_vs_expense:    {labels, income: [...], expense: [...]}
#   receivables_ageing:   {labels: ["Current", "1-30", ...], values: [...]}
# ---------------------------------------------------------------------------

import frappe
from frappe.utils import add_months, getdate, now_datetime, nowdate


@frappe.whitelist()
def get_dashboard_data():
    if not (
        frappe.has_permission("Lease Agreement", "read")
        or frappe.has_permission("Sales Invoice", "read")
    ):
        frappe.throw(frappe._("Not permitted"), frappe.PermissionError)

    return _sample_data()


def _last_six_month_labels():
    today = getdate(nowdate())
    return [add_months(today, -i).strftime("%b") for i in range(5, -1, -1)]


def _sample_data():
    labels = _last_six_month_labels()
    return {
        "currency": frappe.defaults.get_global_default("currency") or "INR",
        "refreshed_at": now_datetime().strftime("%b %d, %Y %I:%M %p"),
        "is_sample": True,
        "kpis": {
            "receivable": {"value": 1860000, "format": "currency", "note": "Rent due from tenants"},
            "revenue": {"value": 11240000, "format": "currency", "note": "Rent + utilities, last 6 months"},
            "occupancy": {"value": 87.2, "format": "percent", "note": "82 of 94 units leased"},
            "collection_rate": {"value": 92.4, "format": "percent", "note": "Collected vs billed"},
            "deposits": {"value": 4250000, "format": "currency", "note": "Security deposits held"},
            "payable": {"value": 640000, "format": "currency", "note": "Owed to vendors"},
            "overdue": {"value": 820000, "format": "currency", "note": "37 invoices past due"},
            "margin": {"value": 39.5, "format": "percent", "note": "Net operating margin"},
        },
        "occupancy_trend": {
            "labels": labels,
            "values": [81.9, 83.0, 84.0, 85.1, 86.2, 87.2],
        },
        "billed_vs_collected": {
            "labels": labels,
            "billed": [1810000, 1835000, 1850000, 1872000, 1890000, 1915000],
            "collected": [1640000, 1702000, 1695000, 1760000, 1748000, 1773000],
        },
        "income_vs_expense": {
            "labels": labels,
            "income": [1790000, 1850000, 1820000, 1910000, 1880000, 1990000],
            "expense": [1120000, 1080000, 1190000, 1140000, 1105000, 1170000],
        },
        "receivables_ageing": {
            "labels": ["Current", "1–30 days", "31–60 days", "61–90 days", "90+ days"],
            "values": [1040000, 498000, 172000, 96000, 54000],
        },
    }
