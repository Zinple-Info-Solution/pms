// Copyright (c) 2026, admin and contributors
// For license information, please see license.txt

frappe.ui.form.on("Property Lead", {
    setup(frm) {
        frm.set_query("interested_units", () => ({
            filters: { property: frm.doc.property },
        }));
    },

    property(frm) {
        // Units belong to one property — drop any picked under the old one.
        frm.set_value("interested_units", []);
    },
});
