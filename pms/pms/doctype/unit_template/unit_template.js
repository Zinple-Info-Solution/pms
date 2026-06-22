// Copyright (c) 2026, admin and contributors
// For license information, please see license.txt

frappe.ui.form.on('Unit Template', {
    unit_type: function(frm) {
        if (frm.doc.unit_type === "Apartment") {
            frm.set_value('naming_series', 'APT-.MM.-.DD.-.####');
        }
        else if (frm.doc.unit_type === "Shop") {
            frm.set_value('naming_series', 'SH-.MM.-.DD.-.####');
        }
        else if (frm.doc.unit_type === "Gym") {
            frm.set_value('naming_series', 'GYM-.MM.-.DD.-.####');
        }
    }
});