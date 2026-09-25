// Copyright (c) 2026, admin and contributors
// For license information, please see license.txt

frappe.ui.form.on('Rental Application', {
    refresh(frm) {
        if (frm.doc.status === 'Approved' && !frm.doc.lease) {
            frm.add_custom_button(__('Lease'), () => {
                frm.call('create_lease').then(r => {
                    if (r.message) {
                        frm.reload_doc();
                        frappe.set_route('Form', 'Lease Agreement', r.message);
                    }
                });
            }, __('Create'));
        } else if (frm.doc.lease) {
            frm.add_custom_button(__('Lease'), () => {
                frappe.set_route('Form', 'Lease Agreement', frm.doc.lease);
            }, __('View'));
        }
    }
});
