frappe.provide("frappe.dashboards.chart_sources");

frappe.dashboards.chart_sources["PMS Rent Year Comparison"] = {
	method: "pms.pms.dashboard_chart_source.pms_rent_year_comparison.pms_rent_year_comparison.get",
	filters: [],
};
