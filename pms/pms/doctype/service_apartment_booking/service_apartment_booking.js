// Copyright (c) 2026, admin and contributors
frappe.ui.form.on('Service Apartment Booking', {

    setup(frm) {
        frm.set_query('unit', () => {
            let filters = { custom_created_by_pms: 1, docstatus: 1 };
            if (frm.doc.building) filters.custom_building = frm.doc.building;
            return { filters };
        });
    },

    refresh(frm) {
        if (frm.is_new()) return;

        const call = (method, then) => frappe.call({
            method: method,
            doc: frm.doc,
            callback(r) {
                frm.reload_doc();
                if (then) then(r);
            }
        });

        if (frm.doc.status === 'Booked') {
            frm.add_custom_button(__('Check In'), () =>
                call('check_in_guest')).addClass('btn-primary');
            frm.add_custom_button(__('Cancel Booking'), () =>
                frappe.confirm(__('Cancel this booking?'), () => call('cancel_booking')));
        }

        if (frm.doc.status === 'Checked In') {
            frm.add_custom_button(__('Check Out'), () =>
                call('check_out_guest')).addClass('btn-primary');
        }

        if (['Checked In', 'Checked Out'].includes(frm.doc.status) && !frm.doc.sales_invoice) {
            frm.add_custom_button(__('Sales Invoice'), () =>
                call('make_invoice', (r) => {
                    if (r.message) frappe.set_route('Form', 'Sales Invoice', r.message);
                }), __('Create'));
        }
    },

    check_in(frm)  { recalc(frm); },
    check_out(frm) { recalc(frm); },
    rate_per_night(frm)  { recalc(frm); },
    extra_charges(frm)   { recalc(frm); },
    discount_amount(frm) { recalc(frm); },

    unit(frm) {
        if (frm.doc.unit && !flt(frm.doc.rate_per_night)) {
            frappe.db.get_value('Asset', frm.doc.unit, 'custom_monthly_rent')
                .then(r => {
                    if (r.message && r.message.custom_monthly_rent) {
                        frm.set_value('rate_per_night',
                            flt(r.message.custom_monthly_rent) / 30);
                    }
                });
        }
    }
});

function recalc(frm) {
    if (frm.doc.check_in && frm.doc.check_out) {
        const nights = frappe.datetime.get_day_diff(
            frm.doc.check_out, frm.doc.check_in);
        frm.set_value('no_of_nights', Math.max(nights, 0));
        frm.set_value('total_amount',
            flt(frm.doc.rate_per_night) * Math.max(nights, 0)
            + flt(frm.doc.extra_charges)
            - flt(frm.doc.discount_amount));
    }
}
