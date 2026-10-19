app_name = "pms"
app_title = "pms"
app_publisher = "admin"
app_description = "pms"
app_email = "admin@test.com"
app_license = "mit"

# ------------------------------------------------------------------
# The financial dashboard now lives inside the desk as a standard Page
# (pms/pms/page/pms_dashboard  ->  /app/pms-dashboard).
# The old portal page at /pms_dashboard is gone; keep old bookmarks working.
# ------------------------------------------------------------------
website_redirects = [
    {"source": "/pms_dashboard", "target": "/app/pms-dashboard"},
    {"source": "/pms-dashboard", "target": "/app/pms-dashboard"},
]

standard_portal_menu_items = [
    {"title": "My Lease", "route": "/my-lease", "reference_doctype": "Lease Agreement", "role": "Tenant"},
    {"title": "My Properties", "route": "/my-property", "reference_doctype": "Owner Statement", "role": "Owner"},
    {"title": "My Work Orders", "route": "/my-work-orders", "reference_doctype": "Work Order", "role": "Vendor"},
]

# ------------------------------------------------------------------
# Document Events — keep Rent Schedule in sync with invoice payments
# ------------------------------------------------------------------
doc_events = {
    "Sales Invoice": {
        "on_submit": "pms.pms.billing.on_invoice_change",
        "on_update_after_submit": "pms.pms.billing.on_invoice_change",
        "on_cancel": "pms.pms.billing.on_invoice_change",
        "on_trash": "pms.pms.billing.on_invoice_trash",
    },
    "Payment Entry": {
        "on_submit": "pms.pms.billing.on_payment_entry",
        "on_cancel": "pms.pms.billing.on_payment_entry",
    },
    "Move Out": {
        "on_submit": "pms.pms.billing.on_move_out",
    },
}

# ------------------------------------------------------------------
# Scheduled Tasks
# ------------------------------------------------------------------
scheduler_events = {
    "hourly": [
        "pms.pms.maintenance.escalate_overdue_work_orders",
    ],
    "daily": [
        "pms.pms.tasks.check_lease_expiry",
        "pms.pms.tasks.send_lease_expiry_reminders",
        "pms.pms.tasks.send_signature_reminders",
        "pms.pms.tasks.send_renewal_offers",
        "pms.pms.tasks.apply_rent_escalations",
        "pms.pms.billing.generate_due_invoices",
        "pms.pms.billing.apply_late_fees",
        "pms.pms.tasks.send_overdue_rent_reminders",
        "pms.pms.maintenance.generate_preventive_work_orders",
    ],
    "monthly": [
        "pms.pms.owner_accounting.generate_monthly_owner_statements",
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

# ------------------------------------------------------------------
# Ship the PMS Financial dashboard with the app.
#
# Frappe already imports "Dashboard Chart Source" records from module
# folders on migrate. Declaring the three below tells `bench migrate`
# to also import our standard Dashboard, Dashboard Chart and Number Card
# records from  pms/pms/{dashboard,dashboard_chart,number_card}/<name>/.
# ------------------------------------------------------------------
importable_doctypes = [
    "Dashboard Chart",
    "Number Card",
    "Dashboard",
]
