// Copyright (c) 2026, admin and contributors
frappe.ui.form.on('Maintenance Request', {

    setup(frm) {
        // Only show PMS-created units of the selected building
        frm.set_query('unit', () => {
            let filters = { custom_created_by_pms: 1 };
            if (frm.doc.building) {
                filters.custom_building = frm.doc.building;
            }
            return { filters };
        });
    },

    building(frm) {
        // Reset unit if it doesn't match the new building
        if (frm.doc.unit && frm.doc.building) {
            frappe.db.get_value('Asset', frm.doc.unit, 'custom_building')
                .then(r => {
                    if (r.message && r.message.custom_building !== frm.doc.building) {
                        frm.set_value('unit', null);
                    }
                });
        }
    },

    refresh(frm) {
        if (frm.is_new()) return;

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
