// Copyright (c) 2026, admin and contributors
frappe.query_reports["Expiring Leases"] = {
    filters: [
        {
            fieldname: "days_ahead",
            label: __("Expiring Within (Days)"),
            fieldtype: "Int",
            default: 60
        },
        {
            fieldname: "building",
            label: __("Building"),
            fieldtype: "Link",
            options: "Building"
        }
    ],
    formatter: function (value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);
        if (column.fieldname === "days_remaining" && data) {
            if (data.days_remaining <= 7) {
                value = `<span style="color:red; font-weight:bold;">${value}</span>`;
            } else if (data.days_remaining <= 30) {
                value = `<span style="color:orange; font-weight:bold;">${value}</span>`;
            }
        }
        return value;
    }
};
