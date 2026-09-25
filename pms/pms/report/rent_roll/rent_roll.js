// Copyright (c) 2026, admin and contributors
frappe.query_reports["Rent Roll"] = {
    filters: [
        { fieldname: "property", label: __("Property"), fieldtype: "Link", options: "Property" },
        { fieldname: "status", label: __("Status"), fieldtype: "Select",
          options: "\nVacant\nOccupied\nUnder Maintenance\nBlocked" }
    ],
    formatter(value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);
        if (column.fieldname === "status" && data) {
            const colors = { Occupied: "green", Vacant: "orange", "Under Maintenance": "red", Blocked: "grey" };
            value = `<span style="color:${colors[data.status] || 'inherit'};font-weight:bold">${value}</span>`;
        }
        return value;
    }
};
