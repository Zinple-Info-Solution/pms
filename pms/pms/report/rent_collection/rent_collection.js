// Copyright (c) 2026, admin and contributors
frappe.query_reports["Rent Collection"] = {
    filters: [
        { fieldname: "building", label: __("Building"), fieldtype: "Link", options: "Building" },
        { fieldname: "tenant", label: __("Tenant"), fieldtype: "Link", options: "Tenant" },
        { fieldname: "status", label: __("Status"), fieldtype: "Select",
          options: "\nPending\nInvoiced\nPaid" }
    ],
    formatter(value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);
        if (column.fieldname === "status" && data) {
            const colors = { Paid: "green", Invoiced: "orange", Pending: "red" };
            value = `<span style="color:${colors[data.status] || 'inherit'};font-weight:bold">${value}</span>`;
        }
        if (column.fieldname === "overdue_days" && data && data.overdue_days > 0) {
            value = `<span style="color:red;font-weight:bold">${value}</span>`;
        }
        return value;
    }
};
