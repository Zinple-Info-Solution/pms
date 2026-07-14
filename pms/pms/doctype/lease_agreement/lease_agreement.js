// Copyright (c) 2026, admin and contributors
// For license information, please see license.txt

frappe.ui.form.on('Lease Agreement', {

    refresh(frm) {
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
            const paid = (frm.doc.rent_schedule || [])
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
                frappe.msgprint(__("Select a Building first."));
                frm.set_value("lease_based_on", "Selected Units");
                return;
            }
            frm.set_value("based_on_by_unit", 0);
            frappe.call({
                method: "frappe.client.get_list",
                args: {
                    doctype: "Asset",
                    filters: {
                        custom_building: frm.doc.building,
                        custom_created_by_pms: 1,
                        docstatus: 1
                    },
                    fields: [
                        "name", "custom_unit_type", "custom_unit_category",
                        "custom_floor_no", "custom_area_sqft",
                        "custom_monthly_rent", "custom_occupancy_status"
                    ],
                    limit: 500
                },
                callback(r) {
                    const units = r.message || [];
                    const occupied = units.filter(
                        u => u.custom_occupancy_status === "Occupied");
                    if (occupied.length) {
                        frappe.msgprint({
                            title: __("Units Occupied"),
                            message: __("Cannot lease whole building — occupied: {0}",
                                [occupied.map(u => u.name).join(", ")]),
                            indicator: "red"
                        });
                        frm.set_value("lease_based_on", "Selected Units");
                        return;
                    }
                    frm.clear_table("units");
                    units.forEach(u => {
                        frm.add_child("units", {
                            unit_id: u.name,
                            unit_type: u.custom_unit_type,
                            unit_category: u.custom_unit_category,
                            floor_no: u.custom_floor_no,
                            area_sqft: u.custom_area_sqft,
                            monthly_rent: u.custom_monthly_rent
                        });
                    });
                    frm.refresh_field("units");
                    frappe.show_alert({
                        message: __("{0} units added — whole building", [units.length]),
                        indicator: "green"
                    }, 5);
                }
            });
        }
    },

    billing_frequency(frm) { frm.trigger("recalc_schedule"); },
    discount_type(frm)     { frm.trigger("recalc_schedule"); },
    discount_value(frm)    { frm.trigger("recalc_schedule"); },
    start_date(frm)        { frm.trigger("recalc_schedule"); },
    end_date(frm)          { frm.trigger("recalc_schedule"); },

    recalc_schedule(frm) {
        if (frm.doc.docstatus === 0 && !frm.is_new()) {
            frappe.show_alert({
                message: __("Schedule will refresh on Save"),
                indicator: "blue"
            }, 3);
        }
    },

    based_on_by_unit: function(frm) {
        if (frm.doc.based_on_by_unit) {

            // If no building selected, silently uncheck and do nothing
            if (!frm.doc.building) {
                frm.set_value('based_on_by_unit', 0);
                return;
            }

            // Fetch Vacant Assets filtered by building
            frappe.call({
                method: 'frappe.client.get_list',
                args: {
                    doctype: 'Asset',
                    filters: {
                        custom_occupancy_status : 'Vacent',
                        custom_building         : frm.doc.building,
                        custom_created_by_pms   : 1,
                        docstatus               : 1
                    },
                    fields: [
                        'name',
                        'asset_name',
                        'asset_category',
                        'custom_property_name',
                        'custom_building',
                        'custom_building_unit_row',
                        'custom_unit_type',
                        'custom_unit_category',
                        'custom_area_sqft',
                        'custom_bedrooms',
                        'custom_bathrooms',
                        'custom_monthly_rent',
                        'custom_floor_no',
                        'custom_occupancy_status',
                        'gross_purchase_amount'
                    ],
                    limit: 100
                },
                callback: function(r) {
                    let units = r.message || [];

                    if (units.length === 0) {
                        frappe.msgprint({
                            title: 'No Vacant Units',
                            message: `There are no vacant units available in building <b>${frm.doc.building}</b>.`,
                            indicator: 'orange'
                        });
                        frm.set_value('based_on_by_unit', 0);
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
                            <td style="padding:8px; border:1px solid #ddd;">${unit.custom_property_name || ''}</td>
                            <td style="padding:8px; border:1px solid #ddd;">${unit.custom_building || ''}</td>
                            <td style="padding:8px; border:1px solid #ddd;">${unit.custom_floor_no || ''}</td>
                            <td style="padding:8px; border:1px solid #ddd;">${unit.custom_unit_type || ''}</td>
                            <td style="padding:8px; border:1px solid #ddd;">${unit.custom_unit_category || ''}</td>
                            <td style="padding:8px; border:1px solid #ddd;">${unit.custom_area_sqft || ''} sq.ft</td>
                            <td style="padding:8px; border:1px solid #ddd;">${unit.custom_bedrooms || 0} Bed / ${unit.custom_bathrooms || 0} Bath</td>
                            <td style="padding:8px; border:1px solid #ddd; color:green; font-weight:bold;">
                                ${frappe.format(unit.custom_monthly_rent, {fieldtype: 'Currency'})}
                            </td>
                            <td style="padding:8px; border:1px solid #ddd;">
                                <span style="background:#28a745; color:white; padding:2px 8px;
                                             border-radius:10px; font-size:11px;">Vacant</span>
                            </td>
                        </tr>
                    `).join('');

                    let units_html = `
                        <p style="margin-bottom:8px; color:#555; font-size:12px;">
                            🔍 Showing vacant units in Building: <b>${frm.doc.building}</b>
                            — Total: <b>${units.length}</b> unit(s)
                        </p>
                        <div style="overflow-x:auto; max-height:300px; overflow-y:auto;">
                            <table style="width:100%; border-collapse:collapse; font-size:13px;">
                                <thead>
                                    <tr style="background:#f2f2f2; position:sticky; top:0;">
                                        <th style="padding:8px; border:1px solid #ddd;">Select</th>
                                        <th style="padding:8px; border:1px solid #ddd;">Asset ID</th>
                                        <th style="padding:8px; border:1px solid #ddd;">Property</th>
                                        <th style="padding:8px; border:1px solid #ddd;">Building</th>
                                        <th style="padding:8px; border:1px solid #ddd;">Floor</th>
                                        <th style="padding:8px; border:1px solid #ddd;">Type</th>
                                        <th style="padding:8px; border:1px solid #ddd;">Category</th>
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
                        size: 'extra-large',
                        fields: [
                            {
                                fieldname: 'units_table',
                                fieldtype: 'HTML',
                                options: units_html
                            },
                            {
                                fieldname: 'section_dates',
                                fieldtype: 'Section Break',
                                label: 'Lease Period'
                            },
                            {
                                fieldname: 'start_date',
                                fieldtype: 'Date',
                                label: 'Start Date',
                                reqd: 1,
                                default: frm.doc.start_date || ''
                            },
                            {
                                fieldname: 'col_break',
                                fieldtype: 'Column Break'
                            },
                            {
                                fieldname: 'end_date',
                                fieldtype: 'Date',
                                label: 'End Date',
                                reqd: 1,
                                default: frm.doc.end_date || ''
                            }
                        ],
                        primary_action_label: 'Confirm',
                        primary_action: function(values) {

                            if (!selected_unit) {
                                frappe.msgprint({
                                    title: 'No Unit Selected',
                                    message: 'Please select a vacant unit from the table.',
                                    indicator: 'red'
                                });
                                return;
                            }

                            if (!values.start_date || !values.end_date) {
                                frappe.msgprint({
                                    title: 'Dates Required',
                                    message: 'Please fill both Start Date and End Date.',
                                    indicator: 'red'
                                });
                                return;
                            }

                            if (values.start_date >= values.end_date) {
                                frappe.msgprint({
                                    title: 'Invalid Dates',
                                    message: 'End Date must be after Start Date.',
                                    indicator: 'red'
                                });
                                return;
                            }

                            // Update main form fields
                            frm.set_value('start_date', values.start_date);
                            frm.set_value('end_date', values.end_date);
                            frm.set_value('building', selected_unit.custom_building);
                            frm.set_value('rent_amount', selected_unit.custom_monthly_rent);
                            frm.set_value('floor', selected_unit.custom_floor_no || '');

                            // Clear existing units child table
                            frm.clear_table('units');

                            // Add selected asset to child table
                            let child = frm.add_child('units');
                            frappe.model.set_value(child.doctype, child.name, {
                                'unit_type'    : selected_unit.custom_unit_type || '',
                                'unit_category': selected_unit.custom_unit_category || '',
                                'floor_no'     : selected_unit.custom_floor_no || '',
                                'unit_id'      : selected_unit.name || '',
                                'area_sqft'    : selected_unit.custom_area_sqft || 0,
                                'monthly_rent' : selected_unit.custom_monthly_rent || 0
                            });

                            frm.refresh_field('units');

                            frappe.show_alert({
                                message: `✅ Unit ${selected_unit.name} added successfully!`,
                                indicator: 'green'
                            }, 5);

                            dialog.hide();
                        },
                        onhide: function() {
                            if (!selected_unit) {
                                frm.set_value('based_on_by_unit', 0);
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
                            ${selected_unit.custom_property_name || ''} |
                            ${selected_unit.custom_building || ''} |
                            Floor: ${selected_unit.custom_floor_no || ''} |
                            ${selected_unit.custom_unit_type || ''} |
                            ${frappe.format(selected_unit.custom_monthly_rent, {fieldtype: 'Currency'})}
                        `).css('color', '#28a745');
                    };
                }
            });
        }
    }
});

function create_sales_invoice(frm, schedule_row) {
    frappe.dom.freeze(__("Creating Sales Invoice..."));
    frappe.call({
        method: "pms.pms.billing.make_rent_invoice",
        args: {
            lease_name: frm.doc.name,
            schedule_row: schedule_row || null
        },
        callback(r) {
            frappe.dom.unfreeze();
            if (r.message) {
                frappe.show_alert({
                    message: __("Sales Invoice {0} created!", [r.message]),
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
