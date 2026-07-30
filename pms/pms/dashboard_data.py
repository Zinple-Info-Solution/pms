# Copyright (c) 2026, admin and contributors
# ---------------------------------------------------------------------------
# Shared data helpers for the PMS Financial dashboard.
#
# Everything here is derived only from PMS's own data flow:
#   Rent Schedule -> Sales Invoice -> Payment Entry   (rent + collections)
#   Asset (custom_created_by_pms) custom fields        (units + occupancy)
#
# These helpers are consumed by:
#   * Number Cards  (Custom type -> methods below)
#   * Dashboard Chart Sources (pms_monthly_collected_rent, pms_rent_year_comparison)
# ---------------------------------------------------------------------------

import frappe
from frappe.utils import (
    flt, getdate, nowdate, add_months, get_first_day, get_last_day, formatdate,
)

# Sub-query: every Sales Invoice that was raised from a rent schedule row.
# This is what makes "rent" distinct from any other invoice on the site.
RENT_INVOICES = """
    SELECT sales_invoice FROM `tabRent Schedule`
    WHERE sales_invoice IS NOT NULL AND sales_invoice != ''
"""


# --------------------------------------------------------------------------
# Collections (real cash received, by Payment Entry posting date)
# --------------------------------------------------------------------------
def collected_between(start, end):
    """Total rent actually collected (allocated) between two dates."""
    val = frappe.db.sql(
        f"""
        SELECT COALESCE(SUM(per.allocated_amount), 0)
        FROM `tabPayment Entry Reference` per
        INNER JOIN `tabPayment Entry` pe
                ON pe.name = per.parent AND pe.docstatus = 1
        WHERE per.reference_doctype = 'Sales Invoice'
          AND per.reference_name IN ({RENT_INVOICES})
          AND pe.posting_date BETWEEN %(start)s AND %(end)s
        """,
        {"start": start, "end": end},
    )
    return flt(val[0][0]) if val else 0.0


def collected_by_month(start, end):
    """{'YYYY-MM': amount} of rent collected per month in the range."""
    rows = frappe.db.sql(
        f"""
        SELECT DATE_FORMAT(pe.posting_date, '%%Y-%%m') AS ym,
               COALESCE(SUM(per.allocated_amount), 0)  AS amt
        FROM `tabPayment Entry Reference` per
        INNER JOIN `tabPayment Entry` pe
                ON pe.name = per.parent AND pe.docstatus = 1
        WHERE per.reference_doctype = 'Sales Invoice'
          AND per.reference_name IN ({RENT_INVOICES})
          AND pe.posting_date BETWEEN %(start)s AND %(end)s
        GROUP BY ym
        """,
        {"start": start, "end": end},
        as_dict=True,
    )
    return {r.ym: flt(r.amt) for r in rows}


# --------------------------------------------------------------------------
# Receivables (invoiced but not yet paid)
# --------------------------------------------------------------------------
def outstanding_total():
    val = frappe.db.sql(
        f"""
        SELECT COALESCE(SUM(si.outstanding_amount), 0)
        FROM `tabSales Invoice` si
        WHERE si.docstatus = 1
          AND si.name IN ({RENT_INVOICES})
        """
    )
    return flt(val[0][0]) if val else 0.0


# --------------------------------------------------------------------------
# Occupancy (from PMS-created Asset units)
# --------------------------------------------------------------------------
def occupancy():
    """Return (occupied, total, rate_percent)."""
    total = frappe.db.count("Asset", {"custom_created_by_pms": 1})
    occupied = frappe.db.count(
        "Asset", {"custom_created_by_pms": 1, "custom_occupancy_status": "Occupied"}
    )
    rate = (occupied / total * 100) if total else 0.0
    return occupied, total, rate


# --------------------------------------------------------------------------
# Number Card methods  (Custom type -> return {"value": .., "fieldtype": ..})
# --------------------------------------------------------------------------
@frappe.whitelist()
def rent_collected_mtd(filters=None):
    today = getdate(nowdate())
    start = get_first_day(today)
    end = get_last_day(today)
    return {"value": collected_between(start, end), "fieldtype": "Currency"}


@frappe.whitelist()
def rent_outstanding(filters=None):
    return {"value": outstanding_total(), "fieldtype": "Currency"}


@frappe.whitelist()
def occupancy_rate(filters=None):
    occupied, total, rate = occupancy()
    return {"value": flt(rate, 1), "fieldtype": "Percent"}



# ===========================================================================
# Desk dashboard  ·  /app/pms-dashboard
# ---------------------------------------------------------------------------
# One endpoint that feeds the whole "Financial" page in a single round trip.
# Every block is guarded so a missing doctype or an empty site returns zeros
# instead of a traceback.
# ===========================================================================

MONTH_LABELS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

EXPENSE_DT = "Purchase Invoice"


def _has_dt(doctype):
    try:
        return bool(frappe.db.exists("DocType", doctype))
    except Exception:
        return False


# --------------------------------------------------------------------------
# Expenses (Purchase Invoices — what the portfolio actually spends)
# --------------------------------------------------------------------------
def expense_between(start, end):
    if not _has_dt(EXPENSE_DT):
        return 0.0
    val = frappe.db.sql(
        """
        SELECT COALESCE(SUM(pi.base_grand_total), 0)
        FROM `tabPurchase Invoice` pi
        WHERE pi.docstatus = 1
          AND pi.posting_date BETWEEN %(start)s AND %(end)s
        """,
        {"start": start, "end": end},
    )
    return flt(val[0][0]) if val else 0.0


def expense_by_month(start, end):
    if not _has_dt(EXPENSE_DT):
        return {}
    rows = frappe.db.sql(
        """
        SELECT DATE_FORMAT(pi.posting_date, '%%Y-%%m') AS ym,
               COALESCE(SUM(pi.base_grand_total), 0)   AS amt
        FROM `tabPurchase Invoice` pi
        WHERE pi.docstatus = 1
          AND pi.posting_date BETWEEN %(start)s AND %(end)s
        GROUP BY ym
        """,
        {"start": start, "end": end},
        as_dict=True,
    )
    return {r.ym: flt(r.amt) for r in rows}


def expense_breakdown(start, end, limit=5):
    """Top spend categories (by Item Group) for the donut."""
    if not _has_dt(EXPENSE_DT):
        return []
    rows = frappe.db.sql(
        """
        SELECT COALESCE(NULLIF(pii.item_group, ''), 'Uncategorised') AS label,
               COALESCE(SUM(pii.base_net_amount), 0)                 AS amount
        FROM `tabPurchase Invoice Item` pii
        INNER JOIN `tabPurchase Invoice` pi
                ON pi.name = pii.parent AND pi.docstatus = 1
        WHERE pi.posting_date BETWEEN %(start)s AND %(end)s
        GROUP BY label
        HAVING amount > 0
        ORDER BY amount DESC
        """,
        {"start": start, "end": end},
        as_dict=True,
    )
    top = [{"label": r.label, "amount": flt(r.amount)} for r in rows[:limit]]
    rest = sum(flt(r.amount) for r in rows[limit:])
    if rest > 0:
        top.append({"label": "Others", "amount": rest})
    return top


# --------------------------------------------------------------------------
# Unit mix (how the portfolio splits across Unit Types)
# --------------------------------------------------------------------------
def units_by_type(limit=6):
    """Unit count per Unit Type, split into occupied / vacant.

    Reads the same PMS-created Assets the occupancy KPI uses, so the totals
    here always add up to `portfolio.total_units`. Anything past `limit` is
    folded into a single 'Others' row so the panel never scrolls forever.
    """
    try:
        rows = frappe.db.sql(
            """
            SELECT COALESCE(NULLIF(a.custom_unit_type, ''), 'Unassigned') AS label,
                   COUNT(a.name)                                          AS total,
                   COALESCE(SUM(CASE WHEN a.custom_occupancy_status = 'Occupied'
                                     THEN 1 ELSE 0 END), 0)               AS occupied
            FROM `tabAsset` a
            WHERE a.custom_created_by_pms = 1
            GROUP BY label
            ORDER BY total DESC, label ASC
            """,
            as_dict=True,
        )
    except Exception:
        # missing custom fields on a fresh bench shouldn't break the page
        return []

    def _row(label, total, occupied, linkable=True):
        total = int(total or 0)
        occupied = int(occupied or 0)
        return {
            "label": label,
            "total": total,
            "occupied": occupied,
            "vacant": max(0, total - occupied),
            "linkable": 1 if linkable else 0,
        }

    top = [_row(r.label, r.total, r.occupied, r.label != "Unassigned") for r in rows[:limit]]

    rest = rows[limit:]
    if rest:
        top.append(
            _row(
                "Others",
                sum(int(r.total or 0) for r in rest),
                sum(int(r.occupied or 0) for r in rest),
                linkable=False,
            )
        )
    return top


# --------------------------------------------------------------------------
# Receivables detail
# --------------------------------------------------------------------------
def overdue_summary():
    """(overdue_amount, overdue_invoice_count) on rent invoices past due date."""
    row = frappe.db.sql(
        f"""
        SELECT COALESCE(SUM(si.outstanding_amount), 0), COUNT(si.name)
        FROM `tabSales Invoice` si
        WHERE si.docstatus = 1
          AND si.outstanding_amount > 0
          AND si.due_date < %(today)s
          AND si.name IN ({RENT_INVOICES})
        """,
        {"today": nowdate()},
    )
    if not row:
        return 0.0, 0
    return flt(row[0][0]), int(row[0][1] or 0)


# --------------------------------------------------------------------------
# Month buckets for the selected period
# --------------------------------------------------------------------------
def _buckets(period):
    """Return a list of (first_day_date, short_label) for the period."""
    today = getdate(nowdate())
    if period == "last_6":
        months = [add_months(get_first_day(today), -i) for i in range(5, -1, -1)]
    elif period == "last_12":
        months = [add_months(get_first_day(today), -i) for i in range(11, -1, -1)]
    else:  # this_year — Jan..Dec of the current calendar year
        months = [getdate(f"{today.year}-{m:02d}-01") for m in range(1, 13)]
    return [(m, formatdate(m, "MMM")) for m in months]


def _series(bucket_map, months):
    return [flt(bucket_map.get(m.strftime("%Y-%m"), 0)) for m in months]


def _pct_change(current, previous):
    if not previous:
        return None
    return flt(((current - previous) / previous) * 100, 1)


# --------------------------------------------------------------------------
# The endpoint
# --------------------------------------------------------------------------
@frappe.whitelist()
def financial_overview(period="this_year"):
    # whitelisted, so don't rely on the Page's role check alone
    if not (
        frappe.has_permission("Lease Agreement", "read")
        or frappe.has_permission("Sales Invoice", "read")
    ):
        frappe.throw(frappe._("Not permitted"), frappe.PermissionError)

    today = getdate(nowdate())

    # ---- month buckets / series -----------------------------------------
    buckets = _buckets(period)
    months = [b[0] for b in buckets]
    labels = [b[1] for b in buckets]
    range_start = months[0]
    range_end = get_last_day(months[-1])

    income_map = collected_by_month(range_start, range_end)
    expense_map = expense_by_month(range_start, range_end)

    income_series = _series(income_map, months)
    expense_series = _series(expense_map, months)
    net_series = [flt(i - e) for i, e in zip(income_series, expense_series)]

    # ---- this month vs last month ---------------------------------------
    m_start, m_end = get_first_day(today), get_last_day(today)
    p_start = get_first_day(add_months(today, -1))
    p_end = get_last_day(add_months(today, -1))

    income_mtd = collected_between(m_start, m_end)
    income_prev = collected_between(p_start, p_end)
    expense_mtd = expense_between(m_start, m_end)
    expense_prev = expense_between(p_start, p_end)
    net_mtd = income_mtd - expense_mtd
    net_prev = income_prev - expense_prev

    # ---- receivables -----------------------------------------------------
    outstanding = outstanding_total()
    overdue_amount, overdue_count = overdue_summary()

    # ---- portfolio -------------------------------------------------------
    occupied, total_units, occ_rate = occupancy()
    active_leases = frappe.db.count(
        "Lease Agreement", {"status": "Active", "docstatus": 1}
    ) if _has_dt("Lease Agreement") else 0
    open_maintenance = frappe.db.count(
        "Maintenance Request", {"status": ["in", ["Open", "In Progress"]]}
    ) if _has_dt("Maintenance Request") else 0

    # ---- year comparison -------------------------------------------------
    this_year, last_year = today.year, today.year - 1
    ty_map = collected_by_month(f"{this_year}-01-01", f"{this_year}-12-31")
    ly_map = collected_by_month(f"{last_year}-01-01", f"{last_year}-12-31")
    ty_values = [flt(ty_map.get(f"{this_year}-{m:02d}", 0)) for m in range(1, 13)]
    ly_values = [flt(ly_map.get(f"{last_year}-{m:02d}", 0)) for m in range(1, 13)]

    return {
        "currency": frappe.defaults.get_global_default("currency") or "INR",
        "period": period,
        "as_on": formatdate(today, "d MMM yyyy"),
        "cards": {
            "income": {"value": income_mtd, "change": _pct_change(income_mtd, income_prev)},
            "expense": {"value": expense_mtd, "change": _pct_change(expense_mtd, expense_prev)},
            "net": {"value": net_mtd, "change": _pct_change(net_mtd, net_prev)},
            "pending": {
                "value": outstanding,
                "overdue_amount": overdue_amount,
                "overdue_count": overdue_count,
            },
        },
        "cash_flow": {
            "labels": labels,
            "income": income_series,
            "expenses": expense_series,
            "net": net_series,
        },
        "expense_breakdown": {
            "total": sum(expense_series),
            "rows": expense_breakdown(range_start, range_end),
        },
        "collection_split": [
            {"label": "Collected", "amount": sum(income_series)},
            {"label": "Outstanding", "amount": outstanding},
        ],
        "revenue_comparison": {
            "labels": MONTH_LABELS,
            "this_year": {"name": str(this_year), "values": ty_values},
            "last_year": {"name": str(last_year), "values": ly_values},
        },
        "unit_mix": units_by_type(),
        "portfolio": {
            "occupied_units": occupied,
            "total_units": total_units,
            "vacant_units": max(0, total_units - occupied),
            "occupancy_rate": flt(occ_rate, 1),
            "active_leases": active_leases,
            "open_maintenance": open_maintenance,
        },
    }