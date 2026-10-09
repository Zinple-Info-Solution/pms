// Copyright (c) 2026, admin and contributors
frappe.ui.form.on('Meter Reading', {

    setup(frm) {
        frm.set_query('meter', () => {
            return { filters: { status: 'Active' } };
        });
    },

    refresh(frm) {
        if (frm.is_new() || frm.doc.status !== 'Pending') return;

        frm.add_custom_button(__('Create Invoice'), () => {
            frm.call('create_invoice').then(r => {
                if (r.message) {
                    frm.reload_doc();
                    frappe.set_route('Form', 'Sales Invoice', r.message);
                }
            });
        });
    }
});
