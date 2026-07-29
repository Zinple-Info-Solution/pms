# Copyright (c) 2026, admin and contributors
# Rent actually collected per month (trailing 12 months) for a line chart.

import frappe
from frappe.utils import getdate, nowdate, add_months, get_first_day, get_last_day, formatdate
from frappe.utils.dashboard import cache_source

from pms.pms.dashboard_data import collected_by_month


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
	today = getdate(nowdate())
	# 12 monthly buckets ending with the current month
	months = [add_months(get_first_day(today), -i) for i in range(11, -1, -1)]
	start = months[0]
	end = get_last_day(months[-1])

	by_month = collected_by_month(start, end)

	labels = [formatdate(m, "MMM yyyy") for m in months]
	values = [by_month.get(m.strftime("%Y-%m"), 0) for m in months]

	return {
		"labels": labels,
		"datasets": [{"name": "Rent Collected", "values": values}],
	}
