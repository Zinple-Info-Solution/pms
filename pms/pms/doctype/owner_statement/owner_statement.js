// Copyright (c) 2026, admin and contributors
// For license information, please see license.txt

frappe.ui.form.on('Owner Statement', {
    refresh(frm) {
        if (frm.is_new()) return;

        if (frm.doc.status === 'Draft') {
            frm.add_custom_button(__('Generate'), () => {
                frm.call('generate').then(() => frm.reload_doc());
            });
        }

        if (['Finalized', 'Sent'].includes(frm.doc.status) && flt(frm.doc.net_distributable) > 0) {
            frm.add_custom_button(__('Distribute'), () => {
                frappe.confirm(
                    __('Create an Owner Distribution and pay out {0}?',
                        [format_currency(frm.doc.net_distributable)]),
                    () => {
                        frappe.call({
                            method: 'pms.pms.owner_accounting.create_distribution',
                            args: { owner_statement_name: frm.doc.name },
                            callback(r) {
                                if (r.message) {
                                    frappe.set_route('Form', 'Owner Distribution', r.message);
                                }
                            }
                        });
                    }
                );
            }).addClass('btn-primary');
        }
    }
});
