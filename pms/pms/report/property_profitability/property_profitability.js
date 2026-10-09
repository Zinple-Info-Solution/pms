// Copyright (c) 2026, admin and contributors
frappe.query_reports["Property Profitability"] = {
    filters: [
        {
            fieldname: "property", label: __("Property"), fieldtype: "Link", options: "Property"
        },
        {
            fieldname: "from_date", label: __("From Date"), fieldtype: "Date",
            default: frappe.datetime.year_start(), reqd: 1
        },
        {
            fieldname: "to_date", label: __("To Date"), fieldtype: "Date",
            default: frappe.datetime.get_today(), reqd: 1
        }
    ]
};
