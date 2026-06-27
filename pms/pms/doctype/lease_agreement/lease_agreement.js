// Copyright (c) 2026, admin and contributors
// For license information, please see license.txt

// frappe.ui.form.on("Lease Agreement", {
// 	refresh(frm) {

// 	},
// });
frappe.ui.form.on("Lease Agreement", {
    refresh(frm) {
        if (frm.doc.docstatus === 1) {
            frm.add_custom_button(__("Sales Invoice"), function () {
                create_sales_invoice(frm);
            }, __("Create"));
        }
    }
});

function create_sales_invoice(frm) {
    if (!frm.doc.tenant) {
        frappe.msgprint({
            title: __("Missing Field"),
            message: __("Please set a Tenant before creating a Sales Invoice."),
            indicator: "orange"
        });
        return;
    }

    if (!frm.doc.units || frm.doc.units.length === 0) {
        frappe.msgprint({
            title: __("No Units"),
            message: __("Please add at least one Unit in the Units table."),
            indicator: "orange"
        });
        return;
    }

    frappe.confirm(
        __("Create a Sales Invoice for Lease Agreement <b>{0}</b>?", [frm.doc.name]),
        function () {
            frappe.dom.freeze(__("Creating Sales Invoice..."));

            // Build items from Units child table
            const si_items = frm.doc.units.map(unit => {
                const rate = flt(unit.monthly_rent) || flt(frm.doc.rent_amount) || 0;

                return {
                    item_code              : "Building Unit",
                    item_name              : "Building Unit",
                    description            : [
                        unit.unit_type     ? `Type: ${unit.unit_type}`         : "",
                        unit.unit_category ? `Category: ${unit.unit_category}` : "",
                        unit.floor_no      ? `Floor: ${unit.floor_no}`         : "",
                        unit.unit_no       ? `Unit No: ${unit.unit_no}`        : "",
                        unit.area_sqft     ? `Area: ${unit.area_sqft} sq.ft`   : "",
                    ].filter(Boolean).join(" | "),
                    qty                    : 1,
                    uom                    : "Month",
                    rate                   : rate,
                    price_list_rate        : rate,
                    // custom fields
                    custom_lease_agreement : frm.doc.name,
                    custom_unit_type       : unit.unit_type  || "",
                    custom_floor_no        : unit.floor_no   || 0,
                    custom_unit_no         : unit.unit_no    || 0,
                    custom_area_sqft       : unit.area_sqft  || 0,
                };
            });

            const remarks = [
                `Lease Agreement  : ${frm.doc.name}`,
                frm.doc.building         ? `Building         : ${frm.doc.building}`         : "",
                frm.doc.floor            ? `Floor            : ${frm.doc.floor}`            : "",
                frm.doc.start_date       ? `Lease Start      : ${frm.doc.start_date}`       : "",
                frm.doc.end_date         ? `Lease End        : ${frm.doc.end_date}`         : "",
                frm.doc.rent_amount      ? `Rent Amount      : ${frm.doc.rent_amount}`      : "",
                frm.doc.security_deposit ? `Security Deposit : ${frm.doc.security_deposit}` : "",
            ].filter(Boolean).join("\n");

            // Create Sales Invoice via server — this runs all server-side
            // hooks and calculations (taxes, totals, etc.) correctly
            frappe.call({
                method: "frappe.client.insert",
                args: {
                    doc: {
                        doctype          : "Sales Invoice",
                        customer         : frm.doc.tenant,
                        posting_date     : frappe.datetime.get_today(),
                        due_date         : frm.doc.end_date || frappe.datetime.get_today(),
                        remarks          : remarks,
                        ignore_pricing_rule: 1,
                        items            : si_items,
                    }
                },
                callback(response) {
                    frappe.dom.unfreeze();

                    if (response.exc) {
                        frappe.msgprint({
                            title: __("Error"),
                            message: response.exc,
                            indicator: "red"
                        });
                        return;
                    }

                    const si_name = response.message.name;

                    frappe.show_alert({
                        message: __("Sales Invoice {0} created successfully!", [si_name]),
                        indicator: "green"
                    }, 5);

                    // Now open the created doc — all values will be there
                    frappe.set_route("Form", "Sales Invoice", si_name);
                },
                error(err) {
                    frappe.dom.unfreeze();
                    frappe.msgprint({
                        title: __("Failed to create Sales Invoice"),
                        message: err.message || __("An unexpected error occurred."),
                        indicator: "red"
                    });
                }
            });
        }
    );
}