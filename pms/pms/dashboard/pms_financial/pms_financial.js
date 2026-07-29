// apps/<your_app>/<your_app>/page/pms_dashboard/pms_dashboard.js
// Frappe desk page — no build step, no React, no Tailwind.
// Charts use frappe-charts (frappe.Chart), already bundled with the desk.

frappe.pages["pms-dashboard"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Financial"),
		single_column: true,
	});
	new PmsDashboard(page);
};

/* ------------------------------------------------------------------ */
/* Sample data — replace with frappe.call() results later              */
/* ------------------------------------------------------------------ */

const NX = {
	months: ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
	income: [96, 104, 112, 108, 121, 128, 133, 126, 130, 138, 142, 149],
	expenses: [41, 44, 39, 47, 43, 42, 48, 45, 40, 46, 44, 50],
	net: [55, 60, 73, 61, 78, 86, 85, 81, 90, 92, 98, 99],
	prev_year: [79, 88, 100, 100, 99, 108, 119, 116, 107, 117, 127, 138],

	expense_break: [
		{ name: "Maintenance", value: 16800, color: "#16a34a" },
		{ name: "Utilities", value: 11200, color: "#4ade80" },
		{ name: "Operations", value: 8600, color: "#a78bfa" },
		{ name: "Services", value: 5700, color: "#f59e0b" },
	],

	kpis: [
		{ label: "Rent Collected (This Month)", value: 128400, delta: "+14.2%", up: true, sub: "vs last month" },
		{ label: "Expenses (This Month)", value: 42300, delta: "-6.1%", up: false, sub: "vs last month" },
		{ label: "Net Income (This Month)", value: 86100, delta: "+18.7%", up: true, sub: "vs last month" },
		{ label: "Pending Rent", value: 23750, delta: "5 overdue", up: false, sub: "across 3 tenants" },
	],

	properties: [
		{ name: "Marina Heights", city: "Kochi", units: 48, leased: 46, collected: 41200 },
		{ name: "Palm Court", city: "Kannur", units: 32, leased: 30, collected: 28400 },
		{ name: "Cedar Residency", city: "Kozhikode", units: 36, leased: 31, collected: 31800 },
		{ name: "Lakeview Towers", city: "Kochi", units: 32, leased: 29, collected: 27000 },
	],

	transactions: [
		{ id: "TRX-2041", date: "12-07-2026", tenant: "Rahul Menon", unit: "Marina Heights · 12B", type: "Rent", method: "Bank transfer", amount: 4200, status: "Paid" },
		{ id: "TRX-2040", date: "11-07-2026", tenant: "Aisha Rahman", unit: "Palm Court · 04A", type: "Rent", method: "Card", amount: 3850, status: "Paid" },
		{ id: "TRX-2039", date: "10-07-2026", tenant: "Greenfield Facilities", unit: "Marina Heights", type: "Maintenance", method: "Bank transfer", amount: -2400, status: "Paid" },
		{ id: "TRX-2038", date: "09-07-2026", tenant: "Daniel Okoro", unit: "Cedar Residency · 09C", type: "Rent", method: "Cheque", amount: 5100, status: "Pending" },
		{ id: "TRX-2037", date: "08-07-2026", tenant: "State Water Board", unit: "Portfolio", type: "Utilities", method: "Auto debit", amount: -1860, status: "Paid" },
		{ id: "TRX-2036", date: "06-07-2026", tenant: "Sofia Alvarez", unit: "Palm Court · 07B", type: "Security deposit", method: "Bank transfer", amount: 7600, status: "Paid" },
		{ id: "TRX-2035", date: "05-07-2026", tenant: "Nikhil Varma", unit: "Cedar Residency · 02A", type: "Rent", method: "UPI", amount: 3400, status: "Overdue" },
		{ id: "TRX-2034", date: "04-07-2026", tenant: "BrightClean Services", unit: "Lakeview Towers", type: "Services", method: "Bank transfer", amount: -980, status: "Paid" },
		{ id: "TRX-2033", date: "03-07-2026", tenant: "Meera Iqbal", unit: "Lakeview Towers · 15D", type: "Rent", method: "Card", amount: 4650, status: "Paid" },
		{ id: "TRX-2032", date: "01-07-2026", tenant: "Tomás Ferreira", unit: "Marina Heights · 06A", type: "Rent", method: "Bank transfer", amount: 4200, status: "Pending" },
	],

	invoices: [
		{ id: "INV-1187", tenant: "Rahul Menon", unit: "Marina Heights · 12B", issued: "01-07-2026", due: "07-07-2026", amount: 4200, status: "Paid" },
		{ id: "INV-1188", tenant: "Aisha Rahman", unit: "Palm Court · 04A", issued: "01-07-2026", due: "07-07-2026", amount: 3850, status: "Paid" },
		{ id: "INV-1189", tenant: "Daniel Okoro", unit: "Cedar Residency · 09C", issued: "01-07-2026", due: "10-07-2026", amount: 5100, status: "Pending" },
		{ id: "INV-1190", tenant: "Nikhil Varma", unit: "Cedar Residency · 02A", issued: "01-07-2026", due: "05-07-2026", amount: 3400, status: "Overdue" },
		{ id: "INV-1191", tenant: "Meera Iqbal", unit: "Lakeview Towers · 15D", issued: "01-07-2026", due: "07-07-2026", amount: 4650, status: "Paid" },
		{ id: "INV-1192", tenant: "Tomás Ferreira", unit: "Marina Heights · 06A", issued: "01-07-2026", due: "12-07-2026", amount: 4200, status: "Pending" },
		{ id: "INV-1193", tenant: "Hannah Weiss", unit: "Palm Court · 11C", issued: "01-07-2026", due: "04-07-2026", amount: 3900, status: "Overdue" },
	],

	overdue: [
		{ name: "Nikhil Varma", unit: "Cedar Residency · 02A", days: 24, amount: 3400 },
		{ name: "Hannah Weiss", unit: "Palm Court · 11C", days: 25, amount: 3900 },
		{ name: "Daniel Okoro", unit: "Cedar Residency · 09C", days: 6, amount: 5100 },
	],

	maintenance: [
		{ ref: "MR-318", title: "Lift stopping between floors", property: "Marina Heights", priority: "High", age: "2h ago" },
		{ ref: "MR-317", title: "Water seepage in ceiling", property: "Cedar Residency", priority: "High", age: "6h ago" },
		{ ref: "MR-315", title: "AC not cooling, unit 07B", property: "Palm Court", priority: "Medium", age: "1d ago" },
		{ ref: "MR-312", title: "Corridor lights flickering", property: "Lakeview Towers", priority: "Low", age: "3d ago" },
	],
};

/* ------------------------------------------------------------------ */

class PmsDashboard {
	constructor(page) {
		this.page = page;
		this.tab = "overview";
		this.query = "";
		this.inject_styles();
		this.setup_page_actions();
		this.render();
	}

	/* ---------- page-level chrome ---------- */

	setup_page_actions() {
		this.page.set_primary_action(__("Add Transaction"), () => {
			frappe.msgprint(__("Wire this to your Payment Entry / Rent Receipt doctype."));
		}, "add");

		this.page.add_menu_item(__("Export"), () => {
			frappe.msgprint(__("Hook up your export report here."));
		});

		this.search = this.page.add_field({
			fieldtype: "Data",
			fieldname: "nx_search",
			placeholder: __("Search tenant, unit or reference"),
			change: () => {
				this.query = (this.search.get_value() || "").trim().toLowerCase();
				this.render_tab_body();
			},
		});
	}

	/* ---------- helpers ---------- */

	money(n) {
		const abs = Math.abs(n).toLocaleString("en-IN");
		return (n < 0 ? "- $" : "$") + abs;
	}

	pill(value) {
		const map = {
			Paid: "nx-pill-green",
			Pending: "nx-pill-amber",
			Overdue: "nx-pill-red",
			High: "nx-pill-red",
			Medium: "nx-pill-amber",
			Low: "nx-pill-grey",
		};
		return `<span class="nx-pill ${map[value] || "nx-pill-grey"}">${frappe.utils.escape_html(value)}</span>`;
	}

	initials(name) {
		return name.split(" ").map((w) => w[0]).join("").slice(0, 2).toUpperCase();
	}

	/* ---------- layout ---------- */

	render() {
		const occ_units = NX.properties.reduce((s, p) => s + p.units, 0);
		const occ_leased = NX.properties.reduce((s, p) => s + p.leased, 0);
		const occ = Math.round((occ_leased / occ_units) * 100);

		const kpi_html = NX.kpis.map((k) => `
			<div class="nx-card nx-kpi">
				<div class="nx-kpi-label">${__(k.label)}</div>
				<div class="nx-kpi-value">${this.money(k.value)}</div>
				<div class="nx-kpi-delta ${k.up ? "nx-up" : "nx-down"}">
					${k.up ? "▲" : "▼"} ${k.delta}
					<span class="nx-muted">${__(k.sub)}</span>
				</div>
			</div>`).join("");

		$(this.page.main).html(`
			<div class="nx-root">
				<div class="nx-topline">
					<div class="nx-tabs">
						<button class="nx-tab is-active" data-tab="overview">${__("Overview")}</button>
						<button class="nx-tab" data-tab="transactions">${__("Transactions")}</button>
						<button class="nx-tab" data-tab="invoices">${__("Invoices")}</button>
					</div>
					<div class="nx-occ">
						<div>
							<div class="nx-occ-label">${__("Occupancy")}</div>
							<div class="nx-occ-sub">${occ_leased} ${__("of")} ${occ_units} ${__("units leased")}</div>
						</div>
						<div class="nx-occ-bar"><span style="width:${occ}%"></span></div>
						<div class="nx-occ-pct">${occ}%</div>
					</div>
				</div>

				<div class="nx-grid-4">${kpi_html}</div>

				<div class="nx-tab-body"></div>
			</div>
		`);

		$(this.page.main).on("click", ".nx-tab", (e) => {
			const $btn = $(e.currentTarget);
			$(this.page.main).find(".nx-tab").removeClass("is-active");
			$btn.addClass("is-active");
			this.tab = $btn.data("tab");
			this.render_tab_body();
		});

		this.render_tab_body();
	}

	render_tab_body() {
		const $body = $(this.page.main).find(".nx-tab-body");
		if (this.tab === "overview") this.render_overview($body);
		if (this.tab === "transactions") this.render_transactions($body);
		if (this.tab === "invoices") this.render_invoices($body);
	}

	/* ---------- overview ---------- */

	render_overview($body) {
		const total_exp = NX.expense_break.reduce((s, e) => s + e.value, 0);

		const legend = NX.expense_break.map((e) => `
			<div class="nx-legend-row">
				<span class="nx-dot" style="background:${e.color}"></span>
				<span>${__(e.name)}</span>
				<span class="nx-legend-val">${this.money(e.value)}</span>
				<span class="nx-muted nx-legend-pct">${Math.round((e.value / total_exp) * 100)}%</span>
			</div>`).join("");

		const prop_rows = NX.properties.map((p) => {
			const pct = Math.round((p.leased / p.units) * 100);
			return `
				<tr>
					<td>
						<div class="nx-strong">${p.name}</div>
						<div class="nx-sub">${p.leased}/${p.units} ${__("units leased")}</div>
					</td>
					<td class="nx-muted">${p.city}</td>
					<td>
						<div class="nx-inline">
							<div class="nx-progress"><span style="width:${pct}%"></span></div>
							<span class="nx-strong nx-small">${pct}%</span>
						</div>
					</td>
					<td class="text-right nx-strong">${this.money(p.collected)}</td>
				</tr>`;
		}).join("");

		const overdue_rows = NX.overdue.map((t) => `
			<div class="nx-list-row">
				<div class="nx-avatar">${this.initials(t.name)}</div>
				<div class="nx-list-main">
					<div class="nx-strong">${t.name}</div>
					<div class="nx-sub">${t.unit}</div>
				</div>
				<div class="text-right">
					<div class="nx-strong">${this.money(t.amount)}</div>
					<div class="nx-sub nx-danger">${t.days} ${__("days late")}</div>
				</div>
			</div>`).join("");

		const maint_rows = NX.maintenance.map((m) => `
			<div class="nx-list-row">
				<div class="nx-list-main">
					<div class="nx-strong">${m.title}</div>
					<div class="nx-sub">${m.ref} · ${m.property} · ${m.age}</div>
				</div>
				${this.pill(m.priority)}
			</div>`).join("");

		$body.html(`
			<div class="nx-grid-3">
				<div class="nx-card nx-span-2">
					<div class="nx-card-title">${__("Cash Flow Analysis")}</div>
					<div id="nx-chart-cashflow"></div>
				</div>
				<div class="nx-card">
					<div class="nx-card-title">${__("Expense Breakdown")}</div>
					<div class="nx-donut-wrap">
						<div id="nx-chart-expense"></div>
						<div class="nx-donut-center">
							<div class="nx-sub">${__("Total Expenses")}</div>
							<div class="nx-donut-total">${this.money(total_exp)}</div>
						</div>
					</div>
					<div class="nx-legend">${legend}</div>
				</div>
			</div>

			<div class="nx-card">
				<div class="nx-card-title">${__("Revenue Comparison")}</div>
				<div id="nx-chart-revenue"></div>
			</div>

			<div class="nx-grid-3">
				<div class="nx-card nx-span-2">
					<div class="nx-card-title">${__("Collection by Property")}</div>
					<table class="nx-table">
						<thead>
							<tr>
								<th>${__("Property")}</th>
								<th>${__("City")}</th>
								<th>${__("Occupancy")}</th>
								<th class="text-right">${__("Collected")}</th>
							</tr>
						</thead>
						<tbody>${prop_rows}</tbody>
					</table>
				</div>
				<div class="nx-stack">
					<div class="nx-card">
						<div class="nx-card-title">${__("Overdue Rent")}</div>
						${overdue_rows}
					</div>
					<div class="nx-card">
						<div class="nx-card-title">${__("Open Maintenance")}</div>
						${maint_rows}
					</div>
				</div>
			</div>
		`);

		this.render_charts();
	}

	render_charts() {
		const money_fmt = (v) => "$" + Number(v).toLocaleString("en-IN") + "k";

		new frappe.Chart("#nx-chart-cashflow", {
			type: "line",
			height: 260,
			colors: ["#16a34a", "#ef4444", "#f59e0b"],
			data: {
				labels: NX.months,
				datasets: [
					{ name: __("Income"), values: NX.income },
					{ name: __("Expenses"), values: NX.expenses },
					{ name: __("Net"), values: NX.net },
				],
			},
			lineOptions: { hideDots: 1, regionFill: 0, spline: 1 },
			axisOptions: { xAxisMode: "tick", yAxisMode: "span" },
			tooltipOptions: { formatTooltipY: money_fmt },
		});

		new frappe.Chart("#nx-chart-expense", {
			// If your frappe-charts build has no "donut", change this to "pie".
			type: "donut",
			height: 200,
			colors: NX.expense_break.map((e) => e.color),
			data: {
				labels: NX.expense_break.map((e) => e.name),
				datasets: [{ values: NX.expense_break.map((e) => e.value) }],
			},
			tooltipOptions: { formatTooltipY: (v) => this.money(v) },
		});

		new frappe.Chart("#nx-chart-revenue", {
			type: "bar",
			height: 230,
			colors: ["#d5e8dd", "#16a34a"],
			data: {
				labels: NX.months,
				datasets: [
					{ name: "2025", values: NX.prev_year },
					{ name: "2026", values: NX.income },
				],
			},
			barOptions: { spaceRatio: 0.4 },
			axisOptions: { xAxisMode: "tick" },
			tooltipOptions: { formatTooltipY: money_fmt },
		});
	}

	/* ---------- tables ---------- */

	match(row, fields) {
		if (!this.query) return true;
		return fields.some((f) => String(row[f] || "").toLowerCase().includes(this.query));
	}

	render_transactions($body) {
		const rows = NX.transactions.filter((t) => this.match(t, ["id", "tenant", "unit", "type"]));

		const body = rows.map((t) => `
			<tr>
				<td class="nx-strong">${t.id}</td>
				<td class="nx-muted">${t.date}</td>
				<td>
					<div class="nx-strong">${frappe.utils.escape_html(t.tenant)}</div>
					<div class="nx-sub">${t.unit}</div>
				</td>
				<td class="nx-muted">${__(t.type)}</td>
				<td class="nx-muted">${__(t.method)}</td>
				<td class="text-right nx-strong ${t.amount < 0 ? "nx-danger" : ""}">${this.money(t.amount)}</td>
				<td class="text-right">${this.pill(t.status)}</td>
			</tr>`).join("");

		$body.html(`
			<div class="nx-card">
				<div class="nx-card-title">${__("Recent Transactions")}</div>
				<table class="nx-table">
					<thead>
						<tr>
							<th>${__("Reference")}</th>
							<th>${__("Date")}</th>
							<th>${__("Tenant / Payee")}</th>
							<th>${__("Category")}</th>
							<th>${__("Method")}</th>
							<th class="text-right">${__("Amount")}</th>
							<th class="text-right">${__("Status")}</th>
						</tr>
					</thead>
					<tbody>${body}</tbody>
				</table>
				${rows.length ? "" : `<p class="nx-empty">${__("No transactions match that search. Clear the search box to see all records.")}</p>`}
			</div>
		`);
	}

	render_invoices($body) {
		const rows = NX.invoices.filter((i) => this.match(i, ["id", "tenant", "unit"]));

		const body = rows.map((i) => `
			<tr>
				<td class="nx-strong">${i.id}</td>
				<td>
					<div class="nx-strong">${frappe.utils.escape_html(i.tenant)}</div>
					<div class="nx-sub">${i.unit}</div>
				</td>
				<td class="nx-muted">${i.issued}</td>
				<td class="nx-muted">${i.due}</td>
				<td class="text-right nx-strong">${this.money(i.amount)}</td>
				<td class="text-right">${this.pill(i.status)}</td>
			</tr>`).join("");

		$body.html(`
			<div class="nx-card">
				<div class="nx-card-title">${__("Rent Invoices — July 2026")}</div>
				<table class="nx-table">
					<thead>
						<tr>
							<th>${__("Invoice")}</th>
							<th>${__("Tenant")}</th>
							<th>${__("Issued")}</th>
							<th>${__("Due")}</th>
							<th class="text-right">${__("Amount")}</th>
							<th class="text-right">${__("Status")}</th>
						</tr>
					</thead>
					<tbody>${body}</tbody>
				</table>
				${rows.length ? "" : `<p class="nx-empty">${__("No invoices match that search. Clear the search box to see all records.")}</p>`}
			</div>
		`);
	}

	/* ---------- styles ---------- */

	inject_styles() {
		if (document.getElementById("nx-pms-styles")) return;
		const css = `
		.nx-root { --nx-ink:#0f2f22; --nx-mute:#6b7f75; --nx-line:#eef2f0; --nx-green:#16a34a;
			display:flex; flex-direction:column; gap:16px; padding-bottom:24px; }
		.nx-root * { box-sizing:border-box; }
		.nx-card { background:#fff; border:1px solid var(--nx-line); border-radius:16px; padding:18px; }
		.nx-card-title { font-weight:600; color:var(--nx-ink); margin-bottom:12px; }
		.nx-grid-4 { display:grid; gap:14px; grid-template-columns:repeat(4,1fr); }
		.nx-grid-3 { display:grid; gap:14px; grid-template-columns:repeat(3,1fr); }
		.nx-span-2 { grid-column:span 2; }
		.nx-stack { display:flex; flex-direction:column; gap:14px; }
		@media (max-width:1100px){
			.nx-grid-4 { grid-template-columns:repeat(2,1fr); }
			.nx-grid-3 { grid-template-columns:1fr; }
			.nx-span-2 { grid-column:span 1; }
		}
		@media (max-width:640px){ .nx-grid-4 { grid-template-columns:1fr; } }

		.nx-topline { display:flex; align-items:center; gap:16px; flex-wrap:wrap; }
		.nx-tabs { display:flex; gap:6px; }
		.nx-tab { border:none; background:transparent; color:var(--nx-mute); font-weight:500;
			font-size:13px; padding:6px 14px; border-radius:8px; cursor:pointer; }
		.nx-tab.is-active { background:#dcfce7; color:#166534; }
		.nx-occ { margin-left:auto; display:flex; align-items:center; gap:12px;
			background:linear-gradient(160deg,#166534,#16a34a); color:#fff;
			padding:10px 16px; border-radius:14px; }
		.nx-occ-label { font-size:13px; font-weight:600; }
		.nx-occ-sub { font-size:11px; opacity:.8; }
		.nx-occ-bar { width:120px; height:6px; border-radius:99px; background:rgba(255,255,255,.25); }
		.nx-occ-bar span { display:block; height:100%; border-radius:99px; background:#fff; }
		.nx-occ-pct { font-size:18px; font-weight:700; }

		.nx-kpi-label { font-size:13px; color:var(--nx-mute); }
		.nx-kpi-value { margin-top:8px; font-size:24px; font-weight:600; color:var(--nx-ink); letter-spacing:-.02em; }
		.nx-kpi-delta { margin-top:6px; font-size:12px; font-weight:600; }
		.nx-kpi-delta.nx-up { color:#16a34a; }
		.nx-kpi-delta.nx-down { color:#ef4444; }
		.nx-kpi-delta .nx-muted { font-weight:400; margin-left:4px; }

		.nx-muted { color:var(--nx-mute); }
		.nx-strong { color:var(--nx-ink); font-weight:600; }
		.nx-small { font-size:12px; }
		.nx-sub { font-size:11.5px; color:var(--nx-mute); }
		.nx-danger { color:#ef4444; }
		.nx-inline { display:flex; align-items:center; gap:8px; }

		.nx-donut-wrap { position:relative; }
		.nx-donut-center { position:absolute; inset:0; display:flex; flex-direction:column;
			align-items:center; justify-content:center; pointer-events:none; }
		.nx-donut-total { font-size:18px; font-weight:600; color:var(--nx-ink); }
		.nx-legend { margin-top:10px; display:flex; flex-direction:column; gap:8px; }
		.nx-legend-row { display:flex; align-items:center; gap:8px; font-size:13px; color:#42544c; }
		.nx-legend-val { margin-left:auto; font-weight:600; color:var(--nx-ink); }
		.nx-legend-pct { width:38px; text-align:right; font-size:12px; }
		.nx-dot { width:10px; height:10px; border-radius:3px; display:inline-block; }

		.nx-table { width:100%; border-collapse:collapse; }
		.nx-table th { text-align:left; font-size:11px; text-transform:uppercase; letter-spacing:.06em;
			font-weight:600; color:#9fb3a9; padding-bottom:10px; }
		.nx-table td { padding:11px 0; font-size:13.5px; border-top:1px solid var(--nx-line); vertical-align:middle; }
		.nx-table .text-right, .nx-table th.text-right { text-align:right; }
		.nx-empty { padding:28px 0; text-align:center; font-size:13px; color:var(--nx-mute); }

		.nx-progress { width:96px; height:6px; border-radius:99px; background:#eaf2ee; }
		.nx-progress span { display:block; height:100%; border-radius:99px; background:var(--nx-green); }

		.nx-list-row { display:flex; align-items:center; gap:12px; padding:9px 0; }
		.nx-list-row + .nx-list-row { border-top:1px solid var(--nx-line); }
		.nx-list-main { min-width:0; }
		.nx-list-row .text-right { margin-left:auto; text-align:right; }
		.nx-list-row .nx-pill { margin-left:auto; }
		.nx-avatar { width:34px; height:34px; border-radius:99px; background:#f2f7f4; color:#166534;
			display:flex; align-items:center; justify-content:center; font-size:12px; font-weight:600; flex:0 0 auto; }

		.nx-pill { display:inline-block; padding:3px 10px; border-radius:99px; font-size:11px; font-weight:600; white-space:nowrap; }
		.nx-pill-green { background:#dcfce7; color:#166534; }
		.nx-pill-amber { background:#fef3c7; color:#92400e; }
		.nx-pill-red   { background:#fee2e2; color:#991b1b; }
		.nx-pill-grey  { background:#e5eeea; color:#42544c; }
		`;
		const style = document.createElement("style");
		style.id = "nx-pms-styles";
		style.textContent = css;
		document.head.appendChild(style);
	}
}