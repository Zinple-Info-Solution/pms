// Copyright (c) 2026, admin and contributors
frappe.listview_settings['Owner Statement'] = {
    onload(listview) {
        listview.page.add_action_item(__('Distribute Selected'), () => {
            const selected = listview.get_checked_items(true);
            if (!selected.length) {
                frappe.msgprint(__('Select one or more Finalized/Sent statements first.'));
                return;
            }
            frappe.confirm(
                __('Create an Owner Distribution for each of the {0} selected statement(s)?', [selected.length]),
                () => {
                    frappe.call({
                        method: 'pms.pms.owner_accounting.bulk_create_distributions',
                        args: { owner_statement_names: selected },
                        freeze: true,
                        freeze_message: __('Distributing...'),
                        callback(r) {
                            const result = r.message || { distributed: [], failed: [] };
                            let msg = __('{0} distributed.', [result.distributed.length]);
                            if (result.failed.length) {
                                msg += '<br>' + __('{0} failed:', [result.failed.length]);
                                msg += '<ul>' + result.failed.map(
                                    f => `<li>${f.owner_statement}: ${f.reason}</li>`
                                ).join('') + '</ul>';
                            }
                            frappe.msgprint({ message: msg, title: __('Batch Distribution') });
                            listview.refresh();
                        }
                    });
                }
            );
        });
    }
};
