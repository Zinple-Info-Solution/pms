// Copyright (c) 2026, admin and contributors
// For license information, please see license.txt

frappe.ui.form.on('Lease Agreement', {

    refresh(frm) {
        // ---- Facility charges ----
        if (frm.doc.docstatus === 0) {
            frm.add_custom_button(__("Facilities From Units"), () => {
                fetch_facilities(frm, true);
            }, __("Get"));
        }
        render_facility_summary(frm);

        // ---- Send for e-signature (Zoho Sign), if configured ----
        if (frm.doc.docstatus === 0 && !frm.is_new() && frm.doc.esign_status !== "Sent") {
            frappe.db.get_single_value("PMS Integration Settings", "esign_enabled").then(enabled => {
                if (!enabled) return;
                frm.add_custom_button(__("Send for Signature"), () => {
                    frm.call("send_for_signature").then(() => frm.reload_doc());
                });
            });
        }

        // Renew for active or expired leases
        if (frm.doc.docstatus === 1 && ["Active", "Expired"].includes(frm.doc.status)) {
            frm.add_custom_button(__("Renew Lease"), () => {
                frappe.confirm(
                    __("Create a renewal draft continuing after {0}?", [frm.doc.end_date]),
                    () => {
                        frappe.call({
                            method: "pms.pms.doctype.lease_agreement.lease_agreement.make_renewal",
                            args: { lease_name: frm.doc.name },
                            callback(r) {
                                if (r.message) {
                                    frappe.set_route("Form", "Lease Agreement", r.message);
                                }
                            }
                        });
                    }
                );
            }).addClass("btn-primary");
        }

        // Move In / Move Out for active leases
        if (frm.doc.docstatus === 1 && frm.doc.status === "Active") {
            frm.add_custom_button(__("Move In"), () => {
                frappe.call({
                    method: "pms.pms.doctype.lease_agreement.lease_agreement.make_move_in",
                    args: { lease_name: frm.doc.name },
                    callback(r) {
                        if (r.message) frappe.set_route("Form", "Move In", r.message);
                    }
                });
            }, __("Create"));

            frm.add_custom_button(__("Move Out"), () => {
                frappe.call({
                    method: "pms.pms.doctype.lease_agreement.lease_agreement.make_move_out",
                    args: { lease_name: frm.doc.name },
                    callback(r) {
                        if (r.message) frappe.set_route("Form", "Move Out", r.message);
                    }
                });
            }, __("Create"));
        }

        if (frm.doc.docstatus === 1) {
            const pending = (frm.doc.rent_schedule || [])
                .filter(r => r.status === "Pending");

            if (pending.length) {
                frm.add_custom_button(
                    __("Rent Invoice ({0})", [pending[0].billing_period]),
                    () => create_sales_invoice(frm, pending[0].name),
                    __("Create")
                );
            } else {
                frm.add_custom_button(__("Sales Invoice"), function () {
                    create_sales_invoice(frm);
                }, __("Create"));
            }

            // Schedule progress in the dashboard
            const total = (frm.doc.rent_schedule || []).length;
            const paid  = (frm.doc.rent_schedule || [])
                .filter(r => r.status === "Paid").length;
            if (total) {
                frm.dashboard.add_indicator(
                    __("Rent collected: {0} / {1} cycles", [paid, total]),
                    paid === total ? "green" : "orange"
                );
            }
        }
    },

    lease_based_on(frm) {
        if (frm.doc.lease_based_on === "Whole Building") {
            if (!frm.doc.building) {
                frappe.msgprint(__("Select a Property first."));
                frm.set_value("lease_based_on", "Selected Units");
                frm.set_value("billing_based_on", "Asset Wise");
                return;
            }
            frm.set_value("based_on_by_unit", 0);
            frappe.call({
                method: "frappe.client.get_list",
                args: {
                    doctype: "Unit",
                    filters: {
                        property: frm.doc.building
                    },
                    fields: [
                        "name", "unit_type", "unit_template",
                        "floor_no", "area_sqft",
                        "monthly_rent", "status"
                    ],
                    limit: 500
                },
                callback(r) {
                    const units    = r.message || [];
                    const occupied = units.filter(
                        u => u.status === "Occupied");
                    if (occupied.length) {
                        frappe.msgprint({
                            title    : __("Units Occupied"),
                            message  : __("Cannot lease whole building — occupied: {0}",
                                [occupied.map(u => u.name).join(", ")]),
                            indicator: "red"
                        });
                        frm.set_value("lease_based_on", "Selected Units");
                        frm.set_value("billing_based_on", "Asset Wise");
                        return;
                    }
                    frm.clear_table("units");
                    units.forEach(u => {
                        frm.add_child("units", {
                            unit_id      : u.name,
                            unit_type    : u.unit_type,
                            unit_category: u.unit_template,
                            floor_no     : u.floor_no,
                            area_sqft    : u.area_sqft,
                            monthly_rent : u.monthly_rent
                        });
                    });
                    frm.refresh_field("units");
                    fetch_facilities(frm, false);
                    frappe.show_alert({
                        message  : __("{0} units added — whole building", [units.length]),
                        indicator: "green"
                    }, 5);
                }
            });
        }
    },

    auto_fetch_facilities(frm) {
        if (frm.doc.auto_fetch_facilities) {
            fetch_facilities(frm, false);
        }
    },

    validate(frm) {
        calculate_facility_totals(frm);
    },

    billing_frequency(frm) { frm.trigger("recalc_schedule"); },
    discount_type(frm)     { frm.trigger("recalc_schedule"); },
    discount_value(frm)    { frm.trigger("recalc_schedule"); },
    start_date(frm)        { frm.trigger("recalc_schedule"); },
    end_date(frm)          { frm.trigger("recalc_schedule"); },

    recalc_schedule(frm) {
        if (frm.doc.docstatus === 0 && !frm.is_new()) {
            frappe.show_alert({
                message  : __("Schedule will refresh on Save"),
                indicator: "blue"
            }, 3);
        }
    },

    based_on_by_unit: function(frm) {
        if (frm.doc.based_on_by_unit) {

            // ✅ Auto set lease_based_on to Selected Units
            frm.set_value('lease_based_on', 'Selected Units');
            frm.set_value('billing_based_on', 'Asset Wise');


            // If no building selected, silently uncheck and reset
            if (!frm.doc.building) {
                frm.set_value('based_on_by_unit', 0);
                frm.set_value('lease_based_on', 'Whole Building');
                frm.set_value('billing_based_on', 'Building Wise');  // ✅
                return;
            }

            // Fetch Vacant Units filtered by property
            frappe.call({
                method: 'frappe.client.get_list',
                args: {
                    doctype: 'Unit',
                    filters: {
                        status  : 'Vacant',
                        property: frm.doc.building
                    },
                    fields: [
                        'name',
                        'property',
                        'unit_type',
                        'unit_template',
                        'area_sqft',
                        'bedrooms',
                        'bathrooms',
                        'monthly_rent',
                        'floor_no',
                        'status'
                    ],
                    limit: 100
                },
                callback: function(r) {
                    let units = r.message || [];

                    if (units.length === 0) {
                        frappe.msgprint({
                            title    : 'No Vacant Units',
                            message  : `There are no vacant units available in building <b>${frm.doc.building}</b>.`,
                            indicator: 'orange'
                        });
                        frm.set_value('based_on_by_unit', 0);
                        frm.set_value('lease_based_on', 'Whole Building');  // ✅
                        frm.set_value('billing_based_on', 'Building Wise');
                        return;
                    }

                    let selected_unit = null;

                    let unit_rows_html = units.map((unit, index) => `
                        <tr id="unit-row-${index}"
                            onclick="select_unit(${index})"
                            style="cursor:pointer; transition: background 0.2s;"
                            onmouseover="this.style.background='#e8f5e9'"
                            onmouseout="this.style.background=window.selected_unit_index===${index}?'#d4edda':'white'">
                            <td style="padding:8px; border:1px solid #ddd; text-align:center;">
                                <input type="radio" name="unit_select" value="${index}">
                            </td>
                            <td style="padding:8px; border:1px solid #ddd;">${unit.name || ''}</td>
                            <td style="padding:8px; border:1px solid #ddd;">${unit.property || ''}</td>
                            <td style="padding:8px; border:1px solid #ddd;">${unit.floor_no || ''}</td>
                            <td style="padding:8px; border:1px solid #ddd;">${unit.unit_type || ''}</td>
                            <td style="padding:8px; border:1px solid #ddd;">${unit.unit_template || ''}</td>
                            <td style="padding:8px; border:1px solid #ddd;">${unit.area_sqft || ''} sq.ft</td>
                            <td style="padding:8px; border:1px solid #ddd;">${unit.bedrooms || 0} Bed / ${unit.bathrooms || 0} Bath</td>
                            <td style="padding:8px; border:1px solid #ddd; color:green; font-weight:bold;">
                                ${frappe.format(unit.monthly_rent, {fieldtype: 'Currency'})}
                            </td>
                            <td style="padding:8px; border:1px solid #ddd;">
                                <span style="background:#28a745; color:white; padding:2px 8px;
                                             border-radius:10px; font-size:11px;">Vacant</span>
                            </td>
                        </tr>
                    `).join('');

                    let units_html = `
                        <p style="margin-bottom:8px; color:#555; font-size:12px;">
                            🔍 Showing vacant units in Property: <b>${frm.doc.building}</b>
                            — Total: <b>${units.length}</b> unit(s)
                        </p>
                        <div style="overflow-x:auto; max-height:300px; overflow-y:auto;">
                            <table style="width:100%; border-collapse:collapse; font-size:13px;">
                                <thead>
                                    <tr style="background:#f2f2f2; position:sticky; top:0;">
                                        <th style="padding:8px; border:1px solid #ddd;">Select</th>
                                        <th style="padding:8px; border:1px solid #ddd;">Unit ID</th>
                                        <th style="padding:8px; border:1px solid #ddd;">Property</th>
                                        <th style="padding:8px; border:1px solid #ddd;">Floor</th>
                                        <th style="padding:8px; border:1px solid #ddd;">Type</th>
                                        <th style="padding:8px; border:1px solid #ddd;">Template</th>
                                        <th style="padding:8px; border:1px solid #ddd;">Area</th>
                                        <th style="padding:8px; border:1px solid #ddd;">Rooms</th>
                                        <th style="padding:8px; border:1px solid #ddd;">Monthly Rent</th>
                                        <th style="padding:8px; border:1px solid #ddd;">Status</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    ${unit_rows_html}
                                </tbody>
                            </table>
                        </div>
                        <p id="selected-unit-info" style="margin-top:8px; color:#888; font-size:12px;">
                            👆 Click a row to select a unit
                        </p>
                    `;

                    let dialog = new frappe.ui.Dialog({
                        title: '🏢 Select Vacant Unit',
                        size : 'extra-large',
                        fields: [
                            {
                                fieldname: 'units_table',
                                fieldtype: 'HTML',
                                options  : units_html
                            },
                            {
                                fieldname: 'section_dates',
                                fieldtype: 'Section Break',
                                label    : 'Lease Period'
                            },
                            {
                                fieldname: 'start_date',
                                fieldtype: 'Date',
                                label    : 'Start Date',
                                reqd     : 1,
                                default  : frm.doc.start_date || ''
                            },
                            {
                                fieldname: 'col_break',
                                fieldtype: 'Column Break'
                            },
                            {
                                fieldname: 'end_date',
                                fieldtype: 'Date',
                                label    : 'End Date',
                                reqd     : 1,
                                default  : frm.doc.end_date || ''
                            }
                        ],
                        primary_action_label: 'Confirm',
                        primary_action: function(values) {

                            if (!selected_unit) {
                                frappe.msgprint({
                                    title    : 'No Unit Selected',
                                    message  : 'Please select a vacant unit from the table.',
                                    indicator: 'red'
                                });
                                return;
                            }

                            if (!values.start_date || !values.end_date) {
                                frappe.msgprint({
                                    title    : 'Dates Required',
                                    message  : 'Please fill both Start Date and End Date.',
                                    indicator: 'red'
                                });
                                return;
                            }

                            if (values.start_date >= values.end_date) {
                                frappe.msgprint({
                                    title    : 'Invalid Dates',
                                    message  : 'End Date must be after Start Date.',
                                    indicator: 'red'
                                });
                                return;
                            }

                            // Update main form fields
                            frm.set_value('start_date', values.start_date);
                            frm.set_value('end_date', values.end_date);
                            frm.set_value('building', selected_unit.property);
                            frm.set_value('rent_amount', selected_unit.monthly_rent);
                            frm.set_value('floor', selected_unit.floor_no || '');

                            // Clear existing units child table
                            frm.clear_table('units');

                            // Add selected unit to child table
                            let child = frm.add_child('units');
                            frappe.model.set_value(child.doctype, child.name, {
                                'unit_type'    : selected_unit.unit_type     || '',
                                'unit_category': selected_unit.unit_template || '',
                                'floor_no'     : selected_unit.floor_no      || '',
                                'unit_id'      : selected_unit.name          || '',
                                'area_sqft'    : selected_unit.area_sqft     || 0,
                                'monthly_rent' : selected_unit.monthly_rent  || 0
                            });

                            frm.refresh_field('units');

                            // Pull the facilities ticked on that unit
                            fetch_facilities(frm, false);

                            frappe.show_alert({
                                message  : `✅ Unit ${selected_unit.name} added successfully!`,
                                indicator: 'green'
                            }, 5);

                            dialog.hide();
                        },
                        onhide: function() {
                            if (!selected_unit) {
                                // ✅ Dialog cancelled without selection
                                frm.set_value('based_on_by_unit', 0);
                                frm.set_value('lease_based_on', 'Whole Building');
                                frm.set_value('billing_based_on', 'Building Wise');
                            }
                        }
                    });

                    dialog.show();

                    window.selected_unit_index = -1;
                    window.select_unit = function(index) {
                        if (window.selected_unit_index >= 0) {
                            $(`#unit-row-${window.selected_unit_index}`).css('background', 'white');
                            $(`#unit-row-${window.selected_unit_index} input[type=radio]`).prop('checked', false);
                        }

                        window.selected_unit_index = index;
                        selected_unit = units[index];

                        $(`#unit-row-${index}`).css('background', '#d4edda');
                        $(`#unit-row-${index} input[type=radio]`).prop('checked', true);

                        $('#selected-unit-info').html(`
                            ✅ <b>Selected:</b> ${selected_unit.name} —
                            ${selected_unit.property || ''} |
                            Floor: ${selected_unit.floor_no || ''} |
                            ${selected_unit.unit_type || ''} |
                            ${frappe.format(selected_unit.monthly_rent, {fieldtype: 'Currency'})}
                        `).css('color', '#28a745');
                    };
                }
            });

        } else {
            // ✅ Checkbox unchecked — set back to Whole Building
            frm.set_value('lease_based_on', 'Whole Building');
            frm.set_value('billing_based_on', 'Building Wise');
        }
    }
});

function create_sales_invoice(frm, schedule_row) {
    frappe.dom.freeze(__("Creating Sales Invoice..."));
    frappe.call({
        method: "pms.pms.billing.make_rent_invoice",
        args: {
            lease_name  : frm.doc.name,
            schedule_row: schedule_row || null
        },
        callback(r) {
            frappe.dom.unfreeze();
            if (r.message) {
                frappe.show_alert({
                    message  : __("Sales Invoice {0} created!", [r.message]),
                    indicator: "green"
                }, 5);
                frm.reload_doc();
                frappe.set_route("Form", "Sales Invoice", r.message);
            }
        },
        error() {
            frappe.dom.unfreeze();
        }
    });
}


// ---------------------------------------------------------------------------
// Facility charges
// ---------------------------------------------------------------------------
frappe.ui.form.on('Lease Facility Charge', {
    amount(frm)        { calculate_facility_totals(frm); },
    charge_type(frm)   { calculate_facility_totals(frm); },
    apply(frm)         { calculate_facility_totals(frm); },
    facilities_remove(frm) { calculate_facility_totals(frm); },

    facility(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        if (!row.facility) return;

        frappe.db.get_value('Property Facility', row.facility,
            ['default_amount', 'charge_type'], (r) => {
                if (!r) return;
                if (!row.amount)      frappe.model.set_value(cdt, cdn, 'amount', r.default_amount);
                if (!row.charge_type) frappe.model.set_value(cdt, cdn, 'charge_type', r.charge_type || 'Recurring');
                calculate_facility_totals(frm);
            });
    }
});

frappe.ui.form.on('Lease Agreement Unit', {
    units_remove(frm) { fetch_facilities(frm, false); }
});

function fetch_facilities(frm, show_message) {
    const unit_ids = (frm.doc.units || []).map(u => u.unit_id).filter(Boolean);

    if (!unit_ids.length) {
        if (show_message) {
            frappe.msgprint({
                title    : __('No Units'),
                message  : __('Add at least one unit before fetching facilities.'),
                indicator: 'orange'
            });
        }
        return;
    }

    frappe.call({
        method: 'pms.pms.doctype.lease_agreement.lease_agreement.get_facilities_for_units',
        args  : { units: JSON.stringify(unit_ids) },
        callback(r) {
            const fetched = r.message || [];

            // keep manual rows + remember what the user already edited
            const manual = (frm.doc.facilities || []).filter(f => !f.auto_fetched);
            const old    = {};
            (frm.doc.facilities || []).forEach(f => {
                if (f.auto_fetched && f.unit) old[f.unit + '::' + f.facility] = f;
            });

            frm.clear_table('facilities');

            manual.forEach(m => {
                const c = frm.add_child('facilities');
                Object.assign(c, {
                    apply       : m.apply,
                    unit        : m.unit,
                    facility    : m.facility,
                    charge_type : m.charge_type,
                    amount      : m.amount,
                    unit_type   : m.unit_type,
                    floor_no    : m.floor_no,
                    remarks     : m.remarks,
                    auto_fetched: 0
                });
            });

            fetched.forEach(f => {
                const prev = old[f.unit + '::' + f.facility];
                const c = frm.add_child('facilities');
                Object.assign(c, {
                    apply       : prev ? prev.apply : 1,
                    unit        : f.unit,
                    facility    : f.facility,
                    charge_type : prev ? prev.charge_type : (f.charge_type || 'Recurring'),
                    amount      : prev ? prev.amount : (f.amount || 0),
                    unit_type   : f.unit_type,
                    floor_no    : f.floor_no,
                    remarks     : prev ? prev.remarks : f.remarks,
                    auto_fetched: 1
                });
            });

            frm.refresh_field('facilities');
            calculate_facility_totals(frm);

            if (show_message) {
                if (fetched.length) {
                    frappe.show_alert({
                        message  : __('{0} facility charge(s) loaded from {1} unit(s).',
                                      [fetched.length, unit_ids.length]),
                        indicator: 'green'
                    }, 5);
                } else {
                    frappe.msgprint({
                        title    : __('No Facilities'),
                        message  : __('None of the selected units have a ticked facility. Open the Unit, tick the facilities under <b>Facilities</b> and set an amount.'),
                        indicator: 'orange'
                    });
                }
            }
        }
    });
}

function calculate_facility_totals(frm) {
    let monthly = 0, one_time = 0;

    (frm.doc.facilities || []).forEach(row => {
        if (!row.apply) return;
        if (row.charge_type === 'One Time') one_time += flt(row.amount);
        else                                monthly  += flt(row.amount);
    });

    frm.set_value('facility_charges_monthly', monthly);
    frm.set_value('facility_charges_one_time', one_time);

    // mirror the server calculation so the user sees live totals
    const add_monthly = (frm.doc.additional_charges || [])
        .filter(c => c.charge_type === 'Recurring')
        .reduce((a, c) => a + flt(c.amount), 0);
    const add_one = (frm.doc.additional_charges || [])
        .filter(c => c.charge_type === 'One Time')
        .reduce((a, c) => a + flt(c.amount), 0);

    frm.set_value('monthly_charges', add_monthly + monthly);
    frm.set_value('one_time_charges', add_one + one_time);

    const rent = flt(frm.doc.rent_amount) || flt(frm.doc.total_rent);
    frm.set_value('net_monthly_amount',
        rent + add_monthly + monthly - flt(frm.doc.discount_per_month));

    render_facility_summary(frm);
}

function render_facility_summary(frm) {
    const rows = (frm.doc.facilities || []).filter(f => f.apply);
    if (!rows.length) return;

    const monthly = rows.filter(f => f.charge_type !== 'One Time')
                        .reduce((a, f) => a + flt(f.amount), 0);
    const one_time = rows.filter(f => f.charge_type === 'One Time')
                         .reduce((a, f) => a + flt(f.amount), 0);

    frm.dashboard.add_indicator(
        __('Facilities: {0} / month + {1} one time',
           [format_currency(monthly), format_currency(one_time)]),
        monthly || one_time ? 'blue' : 'gray'
    );
}
