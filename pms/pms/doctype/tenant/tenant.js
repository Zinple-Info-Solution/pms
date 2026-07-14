// Copyright (c) 2026, admin and contributors
frappe.ui.form.on('Tenant', {

    refresh(frm) {
        if (frm.is_new()) return;

        frm.add_custom_button(__('Lease Agreements'), () => {
            frappe.set_route('List', 'Lease Agreement', { tenant: frm.doc.name });
        }, __('View'));

        frm.add_custom_button(__('Bookings'), () => {
            frappe.set_route('List', 'Service Apartment Booking', { guest: frm.doc.name });
        }, __('View'));

        if (frm.doc.customer) {
            frm.add_custom_button(__('Sales Invoices'), () => {
                frappe.set_route('List', 'Sales Invoice', { customer: frm.doc.customer });
            }, __('View'));

            frm.add_custom_button(__('Maintenance Requests'), () => {
                frappe.set_route('List', 'Maintenance Request', { tenant: frm.doc.customer });
            }, __('View'));
        }

        frm.add_custom_button(__('New Lease Agreement'), () => {
            frappe.new_doc('Lease Agreement', { tenant: frm.doc.name });
        }, __('Create'));

        frm.add_custom_button(__('New Booking (Short Stay)'), () => {
            frappe.new_doc('Service Apartment Booking', { guest: frm.doc.name });
        }, __('Create'));

        if (frm.doc.customer) {
            frm.add_custom_button(__('New Maintenance Request'), () => {
                frappe.new_doc('Maintenance Request', { tenant: frm.doc.customer });
            }, __('Create'));
        }
    }
});
