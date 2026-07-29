# Copyright (c) 2026, admin and contributors
# Rent collected this year vs last year, by month, for a grouped bar chart.

import frappe
from frappe.utils import getdate, nowdate
from frappe.utils.dashboard import cache_source

from pms.pms.dashboard_data import collected_by_month

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _year_values(year):
    data = collected_by_month(f"{year}-01-01", f"{year}-12-31")
    return [data.get(f"{year}-{m:02d}", 0) for m in range(1, 13)]


@frappe.whitelist()
@cache_source
def get(
	chart_name=None,
	chart=None,
	no_cache=None,
	filters=None,
	from_date=None,
	to_date=None,
	timespan=None,
	time_interval=None,
	heatmap_year=None,
):
	this_year = getdate(nowdate()).year
	last_year = this_year - 1
	return {
		"labels": MONTHS,
		"datasets": [
			{"name": str(last_year), "values": _year_values(last_year)},
			{"name": str(this_year), "values": _year_values(this_year)},
		],
	}
