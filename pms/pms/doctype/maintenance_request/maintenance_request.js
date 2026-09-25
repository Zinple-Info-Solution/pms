// Copyright (c) 2026, admin and contributors
frappe.ui.form.on('Maintenance Request', {

    setup(frm) {
        // Only show units of the selected property
        frm.set_query('unit', () => {
            let filters = {};
            if (frm.doc.building) {
                filters.property = frm.doc.building;
            }
            return { filters };
        });
    },

    building(frm) {
        // Reset unit if it doesn't match the new property
        if (frm.doc.unit && frm.doc.building) {
            frappe.db.get_value('Unit', frm.doc.unit, 'property')
                .then(r => {
                    if (r.message && r.message.property !== frm.doc.building) {
                        frm.set_value('unit', null);
                    }
                });
        }
    },

    refresh(frm) {
        if (frm.is_new()) return;

        if (!frm.doc.work_order) {
            frm.add_custom_button(__('Work Order'), () => {
                frm.call('create_work_order').then(r => {
                    if (r.message) {
                        frm.reload_doc();
                        frappe.set_route('Form', 'Work Order', r.message);
                    }
                });
            }, __('Create'));
        } else {
            frm.add_custom_button(__('Work Order'), () => {
                frappe.set_route('Form', 'Work Order', frm.doc.work_order);
            }, __('View'));
        }

        // Quick status actions
        if (frm.doc.status === 'Open') {
            frm.add_custom_button(__('Start Work'), () => {
                frm.set_value('status', 'In Progress');
                frm.save();
            }).addClass('btn-primary');
        }

        if (['Open', 'In Progress', 'On Hold'].includes(frm.doc.status)) {
            frm.add_custom_button(__('Mark Resolved'), () => {
                if (!frm.doc.resolution_details) {
                    frappe.prompt(
                        {
                            fieldname: 'resolution_details',
                            fieldtype: 'Text',
                            label: __('Resolution Details'),
                            reqd: 1
                        },
                        (values) => {
                            frm.set_value('resolution_details', values.resolution_details);
                            frm.set_value('status', 'Resolved');
                            frm.save();
                        },
                        __('Resolve Request')
                    );
                } else {
                    frm.set_value('status', 'Resolved');
                    frm.save();
                }
            });
        }

        if (frm.doc.status === 'Resolved') {
            frm.add_custom_button(__('Close Request'), () => {
                frm.set_value('status', 'Closed');
                frm.save();
            });
        }
    }
});
