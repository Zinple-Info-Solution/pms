frappe.ui.form.on('Asset', {

    setup: function(frm) {
        // Parent unit can only be a PMS-created unit (not another inventory asset)
        frm.set_query('custom_parent_unit', () => {
            return { filters: { custom_created_by_pms: 1 } };
        });

        // Only active facilities can be picked
        frm.set_query('facilities', 'custom_property_facility', () => {
            return { filters: { is_active: 1 } };
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
            // Reload the facility list (adds any newly created Property Facility)
            frm.add_custom_button(__('Reload Facilities'), () => {
                load_facilities(frm, true);
            }, __('Tools'));

            let table_fieldname = get_facilities_fieldname(frm);
            if (table_fieldname) {
                let existing_rows = frm.doc[table_fieldname] || [];
                if (existing_rows.length === 0) {
                    load_facilities(frm);
                }
            }
            show_facility_total(frm);
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

// ---------------------------------------------------------------------------
// Facility rows: tick "Available" -> pull the default amount + charge type
// ---------------------------------------------------------------------------
frappe.ui.form.on('Property Facilities', {

    value: function(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        if (row.value && row.facilities) {
            apply_facility_defaults(frm, cdt, cdn, row.facilities);
        } else if (!row.value) {
            // not available -> no charge
            frappe.model.set_value(cdt, cdn, 'amount', 0);
        }
        show_facility_total(frm);
    },

    facilities: function(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        if (row.facilities) {
            apply_facility_defaults(frm, cdt, cdn, row.facilities);
        }
    },

    amount:      function(frm) { show_facility_total(frm); },
    charge_type: function(frm) { show_facility_total(frm); },

    custom_property_facility_remove: function(frm) { show_facility_total(frm); }
});

function apply_facility_defaults(frm, cdt, cdn, facility) {
    frappe.db.get_value('Property Facility', facility,
        ['default_amount', 'charge_type'], (r) => {
            if (!r) return;
            const row = locals[cdt][cdn];
            if (!flt(row.amount)) {
                frappe.model.set_value(cdt, cdn, 'amount', r.default_amount || 0);
            }
            if (!row.charge_type) {
                frappe.model.set_value(cdt, cdn, 'charge_type', r.charge_type || 'Recurring');
            }
            show_facility_total(frm);
        });
}

function show_facility_total(frm) {
    const fieldname = get_facilities_fieldname(frm);
    if (!fieldname) return;

    let monthly = 0, one_time = 0;
    (frm.doc[fieldname] || []).forEach(row => {
        if (!row.value) return;
        if (row.charge_type === 'One Time') one_time += flt(row.amount);
        else                                monthly  += flt(row.amount);
    });

    if (frm.fields_dict.custom_facility_monthly_total) {
        frm.set_value('custom_facility_monthly_total', monthly);
    }

    frm.get_field(fieldname).set_description(
        __('Ticked facilities are copied to the Lease Agreement. Current total: {0} / month + {1} one time.',
           [format_currency(monthly), format_currency(one_time)])
    );
}

function get_facilities_fieldname(frm) {
    // The PMS custom field is `custom_property_facility`; fall back to a
    // lookup so a renamed field still works.
    if (frm.fields_dict.custom_property_facility) {
        return 'custom_property_facility';
    }
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

function load_facilities(frm, force) {
    frappe.call({
        method: 'frappe.client.get_list',
        args: {
            doctype: 'Property Facility',
            filters: { is_active: 1 },
            fields : ['name', 'default_amount', 'charge_type'],
            limit  : 200
        },
        callback: function(r) {
            let facilities = r.message || [];

            if (facilities.length === 0) {
                frappe.msgprint({
                    title: 'No Facilities',
                    message: 'No active Property Facility records found. Create them first (Facility name, Charge Type and Default Amount).',
                    indicator: 'orange'
                });
                return;
            }

            let table_fieldname = get_facilities_fieldname(frm);

            if (!table_fieldname) {
                frappe.msgprint({
                    title: 'Error',
                    message: 'Could not find the facilities table field on Asset.',
                    indicator: 'red'
                });
                return;
            }

            let existing = frm.doc[table_fieldname] || [];

            if (existing.length && !force) {
                return;   // already populated, don't overwrite
            }

            // Keep what the user already ticked, only append missing facilities
            let have = {};
            existing.forEach(row => { if (row.facilities) have[row.facilities] = true; });

            let added = 0;
            facilities.forEach(function(facility) {
                if (have[facility.name]) return;
                let child = frm.add_child(table_fieldname);
                frappe.model.set_value(child.doctype, child.name, {
                    'facilities' : facility.name,
                    'value'      : 0,
                    'charge_type': facility.charge_type || 'Recurring',
                    'amount'     : 0
                });
                added++;
            });

            frm.refresh_field(table_fieldname);
            show_facility_total(frm);

            if (!added) {
                frappe.show_alert({
                    message: __('All facilities are already listed.'),
                    indicator: 'blue'
                }, 3);
                return;
            }

            // Auto save so facilities persist
            frm.save().then(() => {
                frappe.show_alert({
                    message: `✅ ${added} facility row(s) loaded and saved.`,
                    indicator: 'green'
                }, 3);
            });
        }
    });
}
