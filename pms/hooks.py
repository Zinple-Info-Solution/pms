app_name = "pms"
app_title = "pms"
app_publisher = "admin"
app_description = "pms"
app_email = "admin@test.com"
app_license = "mit"

# NOTE:
# lease_agreement.js and building.js live inside their own doctype folders,
# so Frappe loads them automatically. doctype_js is ONLY needed for JS that
# customizes doctypes from OTHER apps (like the core Asset doctype).
doctype_js = {
    "Asset": "public/js/asset.js",
}

# ------------------------------------------------------------------
# Scheduled Tasks
# ------------------------------------------------------------------
scheduler_events = {
    "daily": [
        "pms.pms.tasks.check_lease_expiry",
        "pms.pms.tasks.send_lease_expiry_reminders",
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
            ["dt", "in", ["Asset", "Sales Invoice Item", "Maintenance Schedule Item"]]
        ],
    },
]
