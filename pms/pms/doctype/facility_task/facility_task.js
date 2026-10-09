// Copyright (c) 2026, admin and contributors
frappe.ui.form.on('Facility Task', {

    refresh(frm) {
        if (frm.is_new()) return;

        frm.add_custom_button(__('Mark Completed'), () => {
            frappe.prompt(
                { fieldname: 'notes', fieldtype: 'Small Text', label: __('Notes') },
                (values) => {
                    frm.call('mark_completed', { notes: values.notes }).then(() => frm.reload_doc());
                },
                __('Mark Completed')
            );
        });
    }
});
