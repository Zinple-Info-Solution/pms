// Copyright (c) 2026, admin and contributors
// For license information, please see license.txt

frappe.ui.form.on("Move In", {
    refresh(frm) { set_attachment_item_options(frm); },
    condition_checklist_remove(frm) { set_attachment_item_options(frm); },

    checklist_template(frm) {
        if (!frm.doc.checklist_template) return;
        const fill = () => fill_checklist_from_template(frm);
        if ((frm.doc.condition_checklist || []).length) {
            frappe.confirm(
                __("Replace the current checklist with the items from {0}?", [frm.doc.checklist_template]),
                fill
            );
        } else {
            fill();
        }
    },
});

frappe.ui.form.on("Move In Checklist Item", {
    item(frm) { set_attachment_item_options(frm); },
    condition_checklist_add(frm) { set_attachment_item_options(frm); },
});

function fill_checklist_from_template(frm) {
    frappe.db.get_doc("Inspection Template", frm.doc.checklist_template).then(template => {
        frm.clear_table("condition_checklist");
        (template.items || []).forEach(row => {
            frm.add_child("condition_checklist", { item: row.item_name, condition: "Good" });
        });
        frm.refresh_field("condition_checklist");
        set_attachment_item_options(frm);
    });
}

// The Attachments table's "Checklist Item" dropdown lists this
// document's own checklist items.
function set_attachment_item_options(frm) {
    const items = [...new Set((frm.doc.condition_checklist || []).map(r => r.item).filter(Boolean))];
    frm.fields_dict.attachments.grid.update_docfield_property("item", "options", [""].concat(items));
    frm.set_df_property("attachments", "description", items.length
        ? __("Extra photos, videos or documents per checklist item. Can be added after submission.")
        : __("Add items to the Condition Checklist above (or pick a Checklist Template) to attach files to them."));
    frm.refresh_field("attachments");
}
