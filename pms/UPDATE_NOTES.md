# PMS — Phase 3: Billing, Discounts, Service Apartments & Unit Inventory

## New in this release

### 1. Rent collection setup (Monthly / Quarterly / Half-Yearly / Yearly)
- New **Billing Frequency** field on Lease Agreement.
- While the lease is a draft, saving it auto-generates a **Rent Collection
  Schedule** — one row per billing cycle with due date, period, rent, charges,
  discount and total. Review it before you submit.
- After submit, the **Create > Rent Invoice** button invoices the next pending
  cycle, and the daily scheduler (`pms.pms.billing.generate_due_invoices`)
  auto-creates invoices for rows due within 3 days.
- When an invoice is paid (Payment Entry) the schedule row flips to **Paid**
  automatically; cancelling the invoice returns the row to **Pending**.
- New **Rent Collection** report: every cycle across all leases with
  color-coded status and overdue days.

### 2. Discounts on Lease Agreement
- Discount Type: **Percentage** (of monthly rent) or fixed **Amount** per month.
- Auto-computed *Discount / Month* and *Net Monthly Amount*.
- Carried into every rent invoice via ERPNext's `discount_amount`
  (applied on Net Total).

### 3. Additional charges
- New child table on the lease: charge name, **Recurring** (added every month)
  or **One Time** (first invoice only), amount, remarks.
- Recurring charges roll into the schedule and appear on each invoice as a
  "PMS Additional Charges" line item (Item auto-created).

### 4. Service Apartment Booking (short stays)
- New doctype: guest (Tenant), unit, check-in/out, nights auto-computed,
  rate per night (auto-suggested from unit monthly rent / 30), extra charges,
  discount, total.
- Buttons: **Check In** (unit → Occupied), **Check Out** (unit → Vacant),
  **Cancel Booking**, **Create > Sales Invoice**.
- Validations: no overlapping bookings on the same unit, and a unit under an
  active long-term lease cannot be booked.

### 5. Unit inventory (assets inside apartments/shops)
- New Asset custom fields: **Parent Unit** + **Condition**.
- Any normal ERPNext Asset (AC, fridge, sofa, water heater...) can be linked
  to the apartment/shop Asset it lives in.
- On a unit's Asset form: **View > Unit Inventory (n)** lists everything
  inside it, **Create > Inventory Asset** opens a new Asset pre-linked to
  this unit.

### 6. Tenant link fixes (your change, completed)
- You changed Lease.tenant to link **Tenant** instead of Customer — good call.
  This release completes it: a read-only **Customer** field is fetched from
  the Tenant and used for invoicing; tenant delete-protection and all Tenant
  form buttons now filter correctly. Service bookings use the same pattern.

## Install
```bash
cd ~/v-15
cp -r <extracted>/pms/* apps/pms/          # or replace apps/pms entirely
bench --site test.com migrate
bench build --app pms
bench --site test.com clear-cache
bench --site test.com enable-scheduler
```

Manual test of the auto-invoicing:
```bash
bench --site test.com execute pms.pms.billing.generate_due_invoices
```

## Data notes
- Existing submitted leases (created before this release) have no rent
  schedule. Either amend them, or keep invoicing them manually — new leases
  get the schedule automatically.
- If a lease shows an empty Customer, open its Tenant and click Save once
  (the Customer is auto-created), then reload the lease.

## Phase 4 ideas
- PMS Workspace/dashboard with number cards (occupancy %, overdue rent,
  open maintenance, upcoming check-ins)
- Lease renewal button (duplicate with shifted dates)
- Tenant web portal (view lease, pay rent, raise maintenance requests)
- Security deposit tracking with refund on termination
