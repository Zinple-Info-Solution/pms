app_name = "pms"
app_title = "pms"
app_publisher = "admin"
app_description = "pms"
app_email = "admin@test.com"
app_license = "mit"

# NOTE:
# lease_agreement.js / building.js / tenant.js live inside their own doctype
# folders, so Frappe loads them automatically. doctype_js is ONLY needed for
# JS that customizes doctypes from OTHER apps (like the core Asset doctype).
doctype_js = {
    "Asset": "public/js/asset.js",
}

app_include_css = "/assets/pms/css/pms_dashboard.css"

# ------------------------------------------------------------------
# Document Events — keep Rent Schedule in sync with invoice payments
# ------------------------------------------------------------------
doc_events = {
    "Sales Invoice": {
        "on_submit": "pms.pms.billing.on_invoice_change",
        "on_update_after_submit": "pms.pms.billing.on_invoice_change",
        "on_cancel": "pms.pms.billing.on_invoice_change",
    },
    "Payment Entry": {
        "on_submit": "pms.pms.billing.on_payment_entry",
        "on_cancel": "pms.pms.billing.on_payment_entry",
    },
}

# ------------------------------------------------------------------
# Scheduled Tasks
# ------------------------------------------------------------------
scheduler_events = {
    "daily": [
        "pms.pms.tasks.check_lease_expiry",
        "pms.pms.tasks.send_lease_expiry_reminders",
        "pms.pms.billing.generate_due_invoices",
        "pms.pms.tasks.send_overdue_rent_reminders",
    ],
}

# ------------------------------------------------------------------
# Fixtures  (export custom fields on Asset / Sales Invoice Item etc.)
# Run:  bench --site test.com export-fixtures
# ------------------------------------------------------------------
fixtures = [
    {
        "dt": "Custom Field",
        "filters": [
            [
                "dt",
                "in",
                ["Asset", "Sales Invoice Item", "Maintenance Schedule Item"],
            ]
        ],
    },
]
