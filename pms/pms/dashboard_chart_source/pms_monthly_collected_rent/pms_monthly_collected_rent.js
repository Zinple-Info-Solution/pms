frappe.provide("frappe.dashboards.chart_sources");

frappe.dashboards.chart_sources["PMS Monthly Collected Rent"] = {
	method: "pms.pms.dashboard_chart_source.pms_monthly_collected_rent.pms_monthly_collected_rent.get",
	filters: [],
};
