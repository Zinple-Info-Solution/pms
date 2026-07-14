// Copyright (c) 2026, admin and contributors
frappe.query_reports["Occupancy Summary"] = {
    filters: [
        {
            fieldname: "building",
            label: __("Building"),
            fieldtype: "Link",
            options: "Building"
        }
    ]
};
