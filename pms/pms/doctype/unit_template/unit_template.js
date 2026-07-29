// Copyright (c) 2026, admin and contributors
// For license information, please see license.txt
frappe.ui.form.on('Unit Template', {
    unit_type: function(frm) {
        if (frm.doc.unit_type) {
            let series = 'UT-' + frm.doc.unit_type.toUpperCase() + '-.####';
            frm.set_value('naming_series', series);
        }
    }
});