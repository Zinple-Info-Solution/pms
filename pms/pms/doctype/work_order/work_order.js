// Copyright (c) 2026, admin and contributors
// For license information, please see license.txt

frappe.ui.form.on('Work Order', {
    setup(frm) {
        frm.set_query('unit', () => {
            return frm.doc.property ? { filters: { property: frm.doc.property } } : {};
        });
    },
});
