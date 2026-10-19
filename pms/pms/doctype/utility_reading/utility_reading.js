// Copyright (c) 2026, admin and contributors
// For license information, please see license.txt

frappe.ui.form.on("Utility Reading", {
    setup(frm) {
        frm.set_query("lease", () => ({ filters: { docstatus: 1 } }));
        frm.set_query("unit", () => ({
            query: "pms.pms.doctype.utility_reading.utility_reading.lease_units_query",
            filters: { lease: frm.doc.lease },
        }));
    },

    refresh(frm) {
        if (!frm.is_new() && frm.doc.status === "Pending") {
            frm.add_custom_button(__("Create Invoice"), () => {
                frm.call("create_invoice").then(r => {
                    if (r.message) frappe.set_route("Form", "Sales Invoice", r.message);
                });
            });
        }
    },

    lease(frm) { frm.set_value("unit", ""); },
    unit(frm) { fill_defaults(frm); },
    utility_type(frm) { fill_defaults(frm); },
    reading_date(frm) { fill_defaults(frm); },
    current_reading(frm) { calculate(frm); },
    previous_reading(frm) { calculate(frm); },
    rate_per_unit(frm) { calculate(frm); },
    fixed_charge(frm) { calculate(frm); },
});

function fill_defaults(frm) {
    const d = frm.doc;
    if (!(d.unit && d.utility_type)) return;
    const module = "pms.pms.doctype.utility_reading.utility_reading";
    frappe.xcall(`${module}.get_previous_reading`, {
        unit: d.unit, utility_type: d.utility_type, lease: d.lease,
        reading_date: d.reading_date, name: frm.is_new() ? null : d.name,
    }).then(value => frm.set_value("previous_reading", value));
    if (!flt(d.rate_per_unit)) {
        frappe.xcall(`${module}.get_last_rate`, {
            unit: d.unit, utility_type: d.utility_type,
        }).then(value => value && frm.set_value("rate_per_unit", value));
    }
}

function calculate(frm) {
    const d = frm.doc;
    const consumption = Math.max(flt(d.current_reading) - flt(d.previous_reading), 0);
    frm.set_value("consumption", consumption);
    frm.set_value("amount", consumption * flt(d.rate_per_unit) + flt(d.fixed_charge));
}
