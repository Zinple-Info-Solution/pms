// Copyright (c) 2026, admin and contributors
// For license information, please see license.txt

// frappe.ui.form.on("Building", {
// 	refresh(frm) {

// 	},
// });


frappe.ui.form.on('Units', {
    unit_type(frm, cdt, cdn) {
        let row = locals[cdt][cdn];

        row.unit_category = "";
        frm.refresh_field('units');
    }
});

frappe.ui.form.on('Building', {
    setup(frm) {
        frm.fields_dict.units.grid.get_field('unit_category').get_query = function(doc, cdt, cdn) {
            let row = locals[cdt][cdn];

            return {
                filters: {
                    unit_type: row.unit_type
                }
            };
        };
    }
});