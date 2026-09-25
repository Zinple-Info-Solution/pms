// Copyright (c) 2026, admin and contributors
// For license information, please see license.txt

frappe.ui.form.on('Unit', {
    setup(frm) {
        frm.set_query('unit_template', () => {
            return { filters: { unit_type: frm.doc.unit_type } };
        });
        frm.set_query('facilities', 'facilities', () => {
            return { filters: { is_active: 1 } };
        });
    },

    refresh(frm) {
        if (!frm.is_new()) {
            frappe.db.count('Asset', { filters: { custom_unit: frm.doc.name } }).then(count => {
                frm.add_custom_button(
                    __('Unit Inventory ({0})', [count || 0]),
                    () => frappe.set_route('List', 'Asset', { custom_unit: frm.doc.name }),
                    __('View')
                );
            });

            frm.add_custom_button(__('Inventory Asset'), () => {
                frappe.new_doc('Asset', { custom_unit: frm.doc.name });
            }, __('Create'));
        }

        show_facility_total(frm);
    }
});

frappe.ui.form.on('Property Facilities', {
    value(frm) { show_facility_total(frm); },
    amount(frm) { show_facility_total(frm); },
    charge_type(frm) { show_facility_total(frm); },
    facilities_remove(frm) { show_facility_total(frm); },
});

function show_facility_total(frm) {
    let monthly = 0, one_time = 0;
    (frm.doc.facilities || []).forEach(row => {
        if (!row.value) return;
        if (row.charge_type === 'One Time') one_time += flt(row.amount);
        else monthly += flt(row.amount);
    });

    frm.get_field('facilities').set_description(
        __('Ticked facilities are copied to the Lease Agreement. Current total: {0} / month + {1} one time.',
            [format_currency(monthly), format_currency(one_time)])
    );
}
