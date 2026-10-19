// Copyright (c) 2026, admin and contributors
// For license information, please see license.txt

frappe.ui.form.on("Move In", {
    refresh(frm) { set_attachment_item_options(frm); },
    condition_checklist_remove(frm) { set_attachment_item_options(frm); },
});

frappe.ui.form.on("Move In Checklist Item", {
    item(frm) { set_attachment_item_options(frm); },
});

// The Attachments table's "Checklist Item" dropdown lists this
// document's own checklist items.
function set_attachment_item_options(frm) {
    const items = [...new Set((frm.doc.condition_checklist || []).map(r => r.item).filter(Boolean))];
    frm.fields_dict.attachments.grid.update_docfield_property("item", "options", [""].concat(items));
    frm.refresh_field("attachments");
}
