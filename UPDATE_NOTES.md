# PMS — Phase 4: Building/Asset-wise Billing, Renewal, Workspace & More Automation

## 1. Lease Based On — Selected Units vs Whole Building
New field on Lease Agreement:
- **Selected Units** (default): works exactly as before — pick units via the dialog.
- **Whole Building**: instantly pulls EVERY unit of the building into the
  Units table. If any unit is occupied, it blocks with the list of occupied
  units. Server-side validation re-checks on save/submit, so this is safe
  even if the client script is bypassed.

## 2. Billing Based On — Asset Wise vs Building Wise
Controls how rent invoices are built (works for both manual button and
auto-generated invoices):
- **Asset Wise** (default): one invoice line per unit with its own rent —
  itemized bills.
- **Building Wise**: one consolidated line "Building Rent-<building>" at the
  full monthly rent, with all unit numbers in the description — a single
  clean line for whole-building tenants.
Discount and additional charges apply identically in both modes.

## 3. Lease Renewal (one click)
"Renew Lease" button on Active/Expired leases: creates a draft copy with the
same units, charges, discount and frequency, starting the day after the old
end date with the same duration. The rent schedule regenerates for the new
dates. Review and submit.

## 4. New automation: overdue rent reminders
Daily task `pms.pms.tasks.send_overdue_rent_reminders` — for every Pending
rent cycle past its due date on an Active lease, notifies the lease owner at
1, 3, 7, 14 and 30 days overdue with tenant, period and amount.

Full daily automation stack now:
1. check_lease_expiry            — expire leases, release units
2. send_lease_expiry_reminders   — 30/15/7/3/1 days before end
3. generate_due_invoices         — auto-invoice due rent cycles
4. send_overdue_rent_reminders   — chase pending overdue rent

## 5. PMS Workspace
A dedicated "PMS" page in the sidebar: shortcuts to Lease Agreement,
Bookings, Tenants, Buildings, Maintenance, Units, Visitor Log and the Rent
Collection report, plus grouped master/report cards. Your whole app in one
screen.

## Install
```bash
cd ~/v-15
# replace apps/pms with this package (back up first), then:
bench --site test.com migrate
bench build --app pms
bench --site test.com clear-cache
```

## Quick test checklist
1. New lease → Lease Based On = Whole Building → all units auto-fill.
2. Set Billing Based On = Building Wise → submit → Create > Rent Invoice →
   invoice has ONE consolidated line.
3. Switch a second lease to Asset Wise → invoice has one line per unit.
4. Open an Active lease → Renew Lease → draft appears with shifted dates.
5. `bench --site test.com execute pms.pms.tasks.send_overdue_rent_reminders`
6. Click "PMS" in the sidebar → workspace loads.
