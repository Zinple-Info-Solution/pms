frappe.ui.form.on('Asset', {

    setup: function(frm) {
        // Parent unit can only be a PMS-created unit (not another inventory asset)
        frm.set_query('custom_parent_unit', () => {
            return { filters: { custom_created_by_pms: 1 } };
        });
    },

    refresh: function(frm) {
        // ---- Unit inventory management ----
        if (frm.doc.custom_created_by_pms && !frm.is_new()) {
            frappe.db.count('Asset', {
                filters: { custom_parent_unit: frm.doc.name }
            }).then(count => {
                frm.add_custom_button(
                    __('Unit Inventory ({0})', [count || 0]),
                    () => frappe.set_route('List', 'Asset', {
                        custom_parent_unit: frm.doc.name
                    }),
                    __('View')
                );
            });

            frm.add_custom_button(__('Inventory Asset'), () => {
                frappe.new_doc('Asset', {
                    custom_parent_unit: frm.doc.name,
                    location: frm.doc.location
                });
            }, __('Create'));
        }

        if (frm.doc.custom_parent_unit) {
            frm.dashboard.add_indicator(
                __('Inside unit: {0}', [frm.doc.custom_parent_unit]), 'blue');
        }

        if (frm.doc.custom_created_by_pms) {
            // Load facilities only if table is empty
            let table_fieldname = get_facilities_fieldname(frm);
            if (table_fieldname) {
                let existing_rows = frm.doc[table_fieldname] || [];
                if (existing_rows.length === 0) {
                    load_facilities(frm);
                }
            }
        }
    },

    custom_created_by_pms: function(frm) {
        if (frm.doc.custom_created_by_pms) {
            load_facilities(frm);
        } else {
            let table_fieldname = get_facilities_fieldname(frm);
            if (table_fieldname) {
                frm.clear_table(table_fieldname);
                frm.refresh_field(table_fieldname);
            }
        }
    }
});

function get_facilities_fieldname(frm) {
    for (let key in frm.fields_dict) {
        if (
            frm.fields_dict[key].df.fieldtype === 'Table' &&
            key.toLowerCase().includes('facilit')
        ) {
            return key;
        }
    }
    return null;
}

function load_facilities(frm) {
    frappe.call({
        method: 'frappe.client.get_list',
        args: {
            doctype: 'Property Facility',
            fields: ['name'],
            limit: 100
        },
        callback: function(r) {
            let facilities = r.message || [];

            if (facilities.length === 0) {
                frappe.msgprint({
                    title: 'No Facilities',
                    message: 'No Property Facility records found.',
                    indicator: 'orange'
                });
                return;
            }

            let table_fieldname = get_facilities_fieldname(frm);

            if (!table_fieldname) {
                frappe.msgprint({
                    title: 'Error',
                    message: 'Could not find facilities table field. Check fieldname.',
                    indicator: 'red'
                });
                return;
            }

            // Check if already populated — don't overwrite
            let existing_rows = frm.doc[table_fieldname] || [];
            if (existing_rows.length > 0) {
                return; // already has data, skip
            }

            // Clear and populate
            frm.clear_table(table_fieldname);

            facilities.forEach(function(facility) {
                let child = frm.add_child(table_fieldname);
                frappe.model.set_value(child.doctype, child.name, {
                    'facilities': facility.name,
                    'value'     : 0
                });
            });

            frm.refresh_field(table_fieldname);

            // Auto save so facilities persist
            frm.save().then(() => {
                frappe.show_alert({
                    message: `✅ ${facilities.length} facilities loaded and saved.`,
                    indicator: 'green'
                }, 3);
            });
        }
    });
}