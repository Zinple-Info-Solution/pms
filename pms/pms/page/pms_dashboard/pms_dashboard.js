// Copyright (c) 2026, admin and contributors
// ---------------------------------------------------------------------------
// PMS · Financial dashboard  —  a native desk page at /app/pms-dashboard
//
// Lives inside the desk, so it inherits the sidebar, navbar, awesomebar,
// theming and role checks for free. All data comes from one call to
//     pms.pms.dashboard_data.financial_overview
// Charts are hand-drawn SVG — no chart library, no CDN, works offline.
// ---------------------------------------------------------------------------

frappe.provide("pms.dashboard");

frappe.pages["pms-dashboard"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Financial"),
		single_column: true,
	});

	wrapper.pms_financial = new pms.dashboard.Financial(page);
};

frappe.pages["pms-dashboard"].on_page_show = function (wrapper) {
	if (wrapper.pms_financial) {
		wrapper.pms_financial.load();
	}
};

pms.dashboard.Financial = class Financial {
	constructor(page) {
		this.page = page;
		this.period = "this_year";
		this.currency = frappe.boot.sysdefaults.currency || "INR";

		this.COLOURS = {
			green: "#16a34a",
			red: "#ef4444",
			amber: "#f59e0b",
			ghost: "#d5e8dd",
			donut: ["#16a34a", "#8b5cf6", "#f59e0b", "#3182ce", "#ef4444", "#94a3b8"],
		};

		this.setup_page_actions();
		this.make_layout();
		this.bind_events();
		this.load();
	}

	// ---------------------------------------------------------------- shell
	setup_page_actions() {
		this.page.set_primary_action(
			__("Record Payment"),
			() => frappe.new_doc("Payment Entry"),
			"add"
		);

		this.page.add_menu_item(__("Refresh"), () => this.load(true));
		this.page.add_menu_item(__("Rent Collection Report"), () =>
			frappe.set_route("query-report", "Rent Collection")
		);
		this.page.add_menu_item(__("Occupancy Summary"), () =>
			frappe.set_route("query-report", "Occupancy Summary")
		);
		this.page.add_menu_item(__("Print"), () => window.print());
	}

	make_layout() {
		this.$root = $(`
			<div class="pms-fin">
				<div class="fin-toolbar">
					<button class="fin-tab is-active" data-route="">${__("Overview")}</button>
					<button class="fin-tab" data-route="payment-entry">${__("Transactions")}</button>
					<button class="fin-tab" data-route="sales-invoice">${__("Invoices")}</button>
					<div class="fin-spacer"></div>
					<span class="fin-asof"></span>
					<select class="form-control input-xs fin-period" style="width:auto">
						<option value="this_year">${__("This Year")}</option>
						<option value="last_12">${__("Last 12 Months")}</option>
						<option value="last_6">${__("Last 6 Months")}</option>
					</select>
				</div>

				<div class="fin-kpis"></div>

				<div class="fin-row fin-split">
					<div class="fin-panel fin-panel-cashflow">
						<div class="fin-panel-head">
							<div>
								<h3 class="fin-panel-title">${__("Cash Flow Analysis")}</h3>
								<div class="fin-legend">
									<span><i class="fin-dot" style="background:${this.COLOURS.green}"></i>${__("Income")}</span>
									<span><i class="fin-dot" style="background:${this.COLOURS.red}"></i>${__("Expenses")}</span>
									<span><i class="fin-dot" style="background:${this.COLOURS.amber}"></i>${__("Net")}</span>
								</div>
							</div>
						</div>
						<svg class="fin-chart fin-cashflow" height="270"></svg>
					</div>

					<div class="fin-panel fin-panel-breakdown">
						<div class="fin-panel-head">
							<h3 class="fin-panel-title fin-breakdown-title">${__("Expense Breakdown")}</h3>
						</div>
						<div class="fin-donut-wrap">
							<svg class="fin-chart fin-donut" height="200"></svg>
							<div class="fin-donut-centre">
								<div>
									<div class="fin-c-label"></div>
									<div class="fin-c-value">&ndash;</div>
								</div>
							</div>
						</div>
						<div class="fin-breakdown"></div>
					</div>
				</div>

				<div class="fin-row">
					<div class="fin-panel fin-panel-revenue">
						<div class="fin-panel-head">
							<h3 class="fin-panel-title">${__("Revenue Comparison")}</h3>
							<div class="fin-legend fin-revenue-legend"></div>
						</div>
						<svg class="fin-chart fin-revenue" height="250"></svg>
					</div>
				</div>

				<div class="fin-row fin-quad fin-portfolio"></div>
			</div>
		`).appendTo(this.page.main);

		this.$tip = $('<div class="pms-fin-tip"></div>').appendTo(document.body);
	}

	bind_events() {
		this.$root.on("click", ".fin-tab", (e) => {
			const route = $(e.currentTarget).data("route");
			if (route) {
				frappe.set_route("List", route);
			}
		});

		this.$root.on("change", ".fin-period", (e) => {
			this.period = e.target.value;
			this.load(true);
		});

		// redraw on resize so the SVG text never stretches
		$(window).on(
			"resize.pms_financial",
			frappe.utils.debounce(() => {
				if (this.data && this.$root.is(":visible")) {
					this.draw_charts();
				}
			}, 200)
		);
	}

	// ----------------------------------------------------------------- data
	load(force) {
		if (this.loading) return;
		this.loading = true;
		this.$root.addClass("is-loading");

		frappe
			.call({
				method: "pms.pms.dashboard_data.financial_overview",
				args: { period: this.period },
				type: "GET",
			})
			.then((r) => {
				this.loading = false;
				this.$root.removeClass("is-loading");
				if (!r || !r.message) {
					this.render_error();
					return;
				}
				this.data = r.message;
				this.currency = this.data.currency || this.currency;
				this.render();
			})
			.catch(() => {
				this.loading = false;
				this.$root.removeClass("is-loading");
				this.render_error();
			});
	}

	render_error() {
		this.$root
			.find(".fin-kpis")
			.html(
				`<div class="fin-panel fin-empty" style="grid-column:1/-1">
					${__("Could not load dashboard data. Check the error log and try refreshing.")}
				</div>`
			);
	}

	render() {
		this.$root.find(".fin-asof").text(__("As on {0}", [this.data.as_on]));
		this.$root.find(".fin-period").val(this.data.period);
		this.render_kpis();
		this.render_breakdown_legend();
		this.render_portfolio();
		this.draw_charts();
	}

	draw_charts() {
		this.draw_cash_flow();
		this.draw_donut();
		this.draw_revenue();
	}

	// ---------------------------------------------------------- formatting
	money(value) {
		return format_currency(flt(value), this.currency, 0);
	}

	compact(value) {
		const n = flt(value);
		const abs = Math.abs(n);
		const prefix = n < 0 ? "-" : "";
		if (this.currency === "INR") {
			if (abs >= 1e7) return prefix + (abs / 1e7).toFixed(1) + "Cr";
			if (abs >= 1e5) return prefix + (abs / 1e5).toFixed(1) + "L";
		} else if (abs >= 1e9) {
			return prefix + (abs / 1e9).toFixed(1) + "B";
		} else if (abs >= 1e6) {
			return prefix + (abs / 1e6).toFixed(1) + "M";
		}
		if (abs >= 1e3) return prefix + Math.round(abs / 1e3) + "k";
		return prefix + Math.round(abs);
	}

	pct_text(change) {
		if (change === null || change === undefined) return null;
		return (change >= 0 ? "+" : "") + flt(change, 1) + "%";
	}

	// ----------------------------------------------------------------- KPIs
	render_kpis() {
		const c = this.data.cards;
		const icons = {
			income: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 3v18M17 7H9.5a2.5 2.5 0 0 0 0 5h5a2.5 2.5 0 0 1 0 5H6"/></svg>',
			expense: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 7h16M4 12h16M4 17h10"/></svg>',
			net: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 17l6-6 4 4 8-8"/><path d="M21 7h-5v5"/></svg>',
			pending: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>',
		};

		const cards = [
			{
				key: "income",
				label: __("Rent Collected (This Month)"),
				value: this.money(c.income.value),
				change: c.income.change,
				good_is_up: true,
				note: __("vs last month"),
				route: "/app/payment-entry",
			},
			{
				key: "expense",
				label: __("Total Expenses (This Month)"),
				value: this.money(c.expense.value),
				change: c.expense.change,
				good_is_up: false,
				note: __("vs last month"),
				route: "/app/purchase-invoice",
			},
			{
				key: "net",
				label: __("Net Position (This Month)"),
				value: this.money(c.net.value),
				change: c.net.change,
				good_is_up: true,
				note: __("vs last month"),
				route: "",
			},
			{
				key: "pending",
				label: __("Pending Payments"),
				value: this.money(c.pending.value),
				change: null,
				note: c.pending.overdue_count
					? __("{0} overdue · {1}", [
							c.pending.overdue_count,
							this.money(c.pending.overdue_amount),
					  ])
					: __("nothing overdue"),
				note_tone: c.pending.overdue_count ? "fin-down" : "",
				route: "/app/sales-invoice?status=Overdue",
			},
		];

		const html = cards
			.map((card) => {
				const tag = card.route ? "a" : "div";
				const href = card.route ? ` href="${card.route}"` : "";
				let foot;
				const pct = this.pct_text(card.change);
				if (pct !== null) {
					const rising = card.change >= 0;
					const tone = (rising === card.good_is_up) ? "fin-up" : "fin-down";
					foot = `<span class="${tone}">${rising ? "&#9650;" : "&#9660;"} ${pct}</span>
							<span class="fin-note">${card.note}</span>`;
				} else {
					foot = `<span class="${card.note_tone || "fin-note"}">${card.note}</span>`;
				}
				return `
					<${tag} class="fin-kpi"${href}>
						<div class="fin-kpi-head">
							<span class="fin-kpi-label">${card.label}</span>
							<span class="fin-kpi-icon">${icons[card.key]}</span>
						</div>
						<div class="fin-kpi-value">${card.value}</div>
						<div class="fin-kpi-foot">${foot}</div>
					</${tag}>`;
			})
			.join("");

		this.$root.find(".fin-kpis").html(html);
	}

	// ------------------------------------------------------------ portfolio
	render_portfolio() {
		const p = this.data.portfolio;
		const rate = Math.max(0, Math.min(100, flt(p.occupancy_rate)));

		const html = `
			<div class="fin-tile fin-tile-occ">
				<div class="fin-tile-label">${__("Occupancy")}</div>
				<div class="fin-tile-value">${flt(rate, 1)}%</div>
				<div class="fin-track"><div class="fin-track-fill" style="width:${rate}%"></div></div>
				<div class="fin-tile-note">${__("{0} of {1} units leased", [
					p.occupied_units,
					p.total_units,
				])}</div>
			</div>
			<a class="fin-tile" href="/app/lease-agreement?status=Active">
				<div class="fin-tile-label">${__("Active Leases")}</div>
				<div class="fin-tile-value">${p.active_leases}</div>
				<div class="fin-tile-note">${__("submitted and running")}</div>
			</a>
			<a class="fin-tile" href="/app/asset?custom_created_by_pms=1&custom_occupancy_status=Vacent">
				<div class="fin-tile-label">${__("Vacant Units")}</div>
				<div class="fin-tile-value">${p.vacant_units}</div>
				<div class="fin-tile-note">${__("available to lease")}</div>
			</a>
			<a class="fin-tile" href="/app/maintenance-request?status=%5B%22in%22%2C%5B%22Open%22%2C%22In%20Progress%22%5D%5D">
				<div class="fin-tile-label">${__("Open Maintenance")}</div>
				<div class="fin-tile-value">${p.open_maintenance}</div>
				<div class="fin-tile-note">${__("open or in progress")}</div>
			</a>`;

		this.$root.find(".fin-portfolio").html(html);
	}

	// -------------------------------------------------------- svg utilities
	svg(tag, attrs) {
		const node = document.createElementNS("http://www.w3.org/2000/svg", tag);
		for (const key in attrs) {
			node.setAttribute(key, attrs[key]);
		}
		return node;
	}

	nice_max(value) {
		if (value <= 0) return 100;
		const power = Math.pow(10, Math.floor(Math.log10(value)));
		const scaled = value / power;
		const step = scaled <= 1 ? 1 : scaled <= 2 ? 2 : scaled <= 5 ? 5 : 10;
		return step * power;
	}

	domain(values) {
		const max = Math.max(0, ...values);
		const min = Math.min(0, ...values);
		return [min < 0 ? -this.nice_max(Math.abs(min)) : 0, this.nice_max(max || 1)];
	}

	smooth_path(points) {
		if (!points.length) return "";
		if (points.length === 1) return `M${points[0][0]},${points[0][1]}`;
		let d = `M${points[0][0]},${points[0][1]}`;
		for (let i = 0; i < points.length - 1; i++) {
			const p0 = points[i > 0 ? i - 1 : i];
			const p1 = points[i];
			const p2 = points[i + 1];
			const p3 = points[i + 2] || p2;
			const c1x = p1[0] + (p2[0] - p0[0]) / 6;
			const c1y = p1[1] + (p2[1] - p0[1]) / 6;
			const c2x = p2[0] - (p3[0] - p1[0]) / 6;
			const c2y = p2[1] - (p3[1] - p1[1]) / 6;
			d += ` C${c1x},${c1y} ${c2x},${c2y} ${p2[0]},${p2[1]}`;
		}
		return d;
	}

	show_tip(event, title, rows) {
		const body = rows
			.map(
				(row) => `<div class="fin-tip-row">
					<span class="fin-dot" style="background:${row.colour}"></span>
					${frappe.utils.escape_html(row.name)}
					<span class="fin-tip-amount">${row.value}</span>
				</div>`
			)
			.join("");

		this.$tip.html(`<b>${frappe.utils.escape_html(title)}</b>${body}`).css({
			opacity: 1,
			left: Math.min(event.clientX + 14, window.innerWidth - 250) + "px",
			top: Math.max(event.clientY - 12, 8) + "px",
		});
	}

	hide_tip() {
		this.$tip.css("opacity", 0);
	}

	chart_width($svg, fallback) {
		const width = Math.floor($svg.parent().width() || 0);
		return width > 120 ? width : fallback;
	}

	// ------------------------------------------------------------ cash flow
	draw_cash_flow() {
		const $svg = this.$root.find(".fin-cashflow");
		const svg = $svg.get(0);
		if (!svg) return;

		const cf = this.data.cash_flow;
		const labels = cf.labels || [];
		svg.innerHTML = "";

		if (!labels.length) return;

		const W = this.chart_width($svg, 720);
		const H = 270;
		svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
		svg.setAttribute("width", W);

		const padding = { left: 58, right: 16, top: 12, bottom: 28 };
		const iw = W - padding.left - padding.right;
		const ih = H - padding.top - padding.bottom;

		const all = [].concat(cf.income, cf.expenses, cf.net);
		const [dmin, dmax] = this.domain(all);
		const n = labels.length;

		const xs = (i) => padding.left + (n <= 1 ? iw / 2 : (iw * i) / (n - 1));
		const ys = (v) =>
			padding.top + ih - (ih * (flt(v) - dmin)) / (dmax - dmin || 1);

		// gridlines + y axis
		const grid = this.svg("g", { class: "fin-grid" });
		for (let t = 0; t <= 4; t++) {
			const value = dmin + ((dmax - dmin) * t) / 4;
			const y = ys(value);
			grid.appendChild(
				this.svg("line", { x1: padding.left, y1: y, x2: W - padding.right, y2: y })
			);
			const text = this.svg("text", {
				x: padding.left - 10,
				y: y + 3.5,
				"text-anchor": "end",
			});
			text.textContent = this.compact(value);
			grid.appendChild(text);
		}
		svg.appendChild(grid);

		if (dmin < 0) {
			svg.appendChild(
				this.svg("line", {
					class: "fin-zero",
					x1: padding.left,
					y1: ys(0),
					x2: W - padding.right,
					y2: ys(0),
				})
			);
		}

		// income area gradient
		const defs = this.svg("defs", {});
		const gradient = this.svg("linearGradient", {
			id: "pmsFinIncome",
			x1: 0,
			y1: 0,
			x2: 0,
			y2: 1,
		});
		gradient.appendChild(
			this.svg("stop", {
				offset: "0%",
				"stop-color": this.COLOURS.green,
				"stop-opacity": 0.22,
			})
		);
		gradient.appendChild(
			this.svg("stop", {
				offset: "100%",
				"stop-color": this.COLOURS.green,
				"stop-opacity": 0,
			})
		);
		defs.appendChild(gradient);
		svg.appendChild(defs);

		const income_points = cf.income.map((v, i) => [xs(i), ys(v)]);
		const income_line = this.smooth_path(income_points);
		const baseline = ys(Math.max(dmin, 0));

		svg.appendChild(
			this.svg("path", {
				d: `${income_line} L${xs(n - 1)},${baseline} L${xs(0)},${baseline} Z`,
				fill: "url(#pmsFinIncome)",
			})
		);

		const series = [
			{ key: "income", name: __("Income"), colour: this.COLOURS.green, dash: "" },
			{ key: "expenses", name: __("Expenses"), colour: this.COLOURS.red, dash: "6 4" },
			{ key: "net", name: __("Net"), colour: this.COLOURS.amber, dash: "2 4" },
		];

		series.forEach((s) => {
			const points = cf[s.key].map((v, i) => [xs(i), ys(v)]);
			const path = this.svg("path", {
				d: this.smooth_path(points),
				fill: "none",
				stroke: s.colour,
				"stroke-width": s.key === "income" ? 2.5 : 2,
				"stroke-linecap": "round",
			});
			if (s.dash) path.setAttribute("stroke-dasharray", s.dash);
			svg.appendChild(path);
		});

		// x labels
		const skip = n > 12 ? Math.ceil(n / 12) : 1;
		labels.forEach((label, i) => {
			if (i % skip) return;
			const text = this.svg("text", {
				x: xs(i),
				y: H - 8,
				"text-anchor": "middle",
			});
			text.textContent = label;
			svg.appendChild(text);
		});

		// hover guide — one hit column per month, tooltip shows all three series
		const guide = this.svg("line", {
			class: "fin-zero",
			x1: 0,
			y1: padding.top,
			x2: 0,
			y2: padding.top + ih,
			opacity: 0,
		});
		svg.appendChild(guide);

		const markers = series.map((s) => {
			const marker = this.svg("circle", {
				r: 3.5,
				stroke: s.colour,
				"stroke-width": 2,
				opacity: 0,
			});
			marker.style.fill = "var(--card-bg, #fff)";
			return marker;
		});
		markers.forEach((m) => svg.appendChild(m));

		const half = n <= 1 ? iw / 2 : iw / (n - 1) / 2;
		labels.forEach((label, i) => {
			const hit = this.svg("rect", {
				x: xs(i) - half,
				y: padding.top,
				width: Math.max(1, half * 2),
				height: ih,
				fill: "transparent",
			});
			hit.style.cursor = "crosshair";
			hit.addEventListener("mousemove", (event) => {
				guide.setAttribute("x1", xs(i));
				guide.setAttribute("x2", xs(i));
				guide.setAttribute("opacity", 1);
				series.forEach((s, si) => {
					markers[si].setAttribute("cx", xs(i));
					markers[si].setAttribute("cy", ys(cf[s.key][i]));
					markers[si].setAttribute("opacity", 1);
				});
				this.show_tip(
					event,
					label,
					series.map((s) => ({
						name: s.name,
						colour: s.colour,
						value: this.money(cf[s.key][i]),
					}))
				);
			});
			hit.addEventListener("mouseleave", () => {
				guide.setAttribute("opacity", 0);
				markers.forEach((m) => m.setAttribute("opacity", 0));
				this.hide_tip();
			});
			svg.appendChild(hit);
		});
	}

	// ---------------------------------------------------------------- donut
	breakdown_rows() {
		// Expenses if there are any, otherwise fall back to the collection split
		// so the panel is never an empty circle.
		const expenses = this.data.expense_breakdown.rows || [];
		if (expenses.length) {
			return {
				title: __("Expense Breakdown"),
				centre: __("Total Expenses"),
				rows: expenses,
			};
		}
		return {
			title: __("Collection Status"),
			centre: __("Total Billed"),
			rows: (this.data.collection_split || []).filter((r) => flt(r.amount) > 0),
		};
	}

	render_breakdown_legend() {
		const model = this.breakdown_rows();
		this.$root.find(".fin-breakdown-title").text(model.title);
		this.$root.find(".fin-donut-centre .fin-c-label").text(model.centre);

		const total = model.rows.reduce((sum, r) => sum + flt(r.amount), 0);
		this.$root
			.find(".fin-donut-centre .fin-c-value")
			.text(total ? this.compact(total) : this.money(0));

		if (!model.rows.length) {
			this.$root
				.find(".fin-breakdown")
				.html(`<div class="fin-empty">${__("No transactions in this period yet.")}</div>`);
			return;
		}

		const html = model.rows
			.map((row, i) => {
				const colour = this.COLOURS.donut[i % this.COLOURS.donut.length];
				const pct = total ? Math.round((flt(row.amount) / total) * 100) : 0;
				return `<div class="fin-breakdown-row">
						<span class="fin-dot" style="background:${colour}"></span>
						<span class="fin-b-name" title="${frappe.utils.escape_html(row.label)}">${frappe.utils.escape_html(
					row.label
				)}</span>
						<span class="fin-b-amount">${this.money(row.amount)}</span>
						<span class="fin-b-pct">${pct}%</span>
					</div>`;
			})
			.join("");

		this.$root.find(".fin-breakdown").html(html);
	}

	draw_donut() {
		const $svg = this.$root.find(".fin-donut");
		const svg = $svg.get(0);
		if (!svg) return;
		svg.innerHTML = "";

		const model = this.breakdown_rows();
		const W = this.chart_width($svg, 240);
		const H = 200;
		svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
		svg.setAttribute("width", W);

		const cx = W / 2;
		const cy = H / 2;
		const r = Math.min(72, H / 2 - 14);
		const circumference = 2 * Math.PI * r;
		const thickness = 18;

		svg.appendChild(
			this.svg("circle", {
				cx: cx,
				cy: cy,
				r: r,
				fill: "none",
				stroke: "var(--border-color, #e8ecea)",
				"stroke-width": thickness,
			})
		);

		const total = model.rows.reduce((sum, row) => sum + flt(row.amount), 0);
		if (!total) return;

		let offset = 0;
		model.rows.forEach((row, i) => {
			const fraction = flt(row.amount) / total;
			const colour = this.COLOURS.donut[i % this.COLOURS.donut.length];
			const arc = this.svg("circle", {
				cx: cx,
				cy: cy,
				r: r,
				fill: "none",
				stroke: colour,
				"stroke-width": thickness,
				"stroke-dasharray": `${fraction * circumference} ${circumference}`,
				"stroke-dashoffset": -offset * circumference,
				transform: `rotate(-90 ${cx} ${cy})`,
			});
			arc.style.cursor = "pointer";
			arc.addEventListener("mousemove", (event) =>
				this.show_tip(event, row.label, [
					{
						name: `${Math.round(fraction * 100)}%`,
						colour: colour,
						value: this.money(row.amount),
					},
				])
			);
			arc.addEventListener("mouseleave", () => this.hide_tip());
			svg.appendChild(arc);
			offset += fraction;
		});
	}

	// ----------------------------------------------------- revenue comparison
	draw_revenue() {
		const $svg = this.$root.find(".fin-revenue");
		const svg = $svg.get(0);
		if (!svg) return;
		svg.innerHTML = "";

		const rc = this.data.revenue_comparison;
		const labels = rc.labels || [];
		const current = rc.this_year.values || [];
		const previous = rc.last_year.values || [];

		this.$root.find(".fin-revenue-legend").html(
			`<span><i class="fin-dot" style="background:${this.COLOURS.green}"></i>${frappe.utils.escape_html(
				rc.this_year.name
			)}</span>
			 <span><i class="fin-dot" style="background:${this.COLOURS.ghost}"></i>${frappe.utils.escape_html(
				rc.last_year.name
			)}</span>`
		);

		const W = this.chart_width($svg, 720);
		const H = 250;
		svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
		svg.setAttribute("width", W);

		const padding = { left: 58, right: 16, top: 12, bottom: 26 };
		const iw = W - padding.left - padding.right;
		const ih = H - padding.top - padding.bottom;
		const [, dmax] = this.domain([].concat(current, previous));
		const ys = (v) => padding.top + ih - (ih * flt(v)) / (dmax || 1);

		const grid = this.svg("g", { class: "fin-grid" });
		for (let t = 0; t <= 4; t++) {
			const value = (dmax * t) / 4;
			const y = ys(value);
			grid.appendChild(
				this.svg("line", { x1: padding.left, y1: y, x2: W - padding.right, y2: y })
			);
			const text = this.svg("text", {
				x: padding.left - 10,
				y: y + 3.5,
				"text-anchor": "end",
			});
			text.textContent = this.compact(value);
			grid.appendChild(text);
		}
		svg.appendChild(grid);

		const n = labels.length || 1;
		const slot = iw / n;
		const bar_width = Math.max(4, Math.min(14, slot / 3.2));
		const gap = 3;

		labels.forEach((label, i) => {
			const centre = padding.left + slot * i + slot / 2;
			const bars = [
				{
					x: centre - bar_width - gap / 2,
					value: previous[i] || 0,
					colour: this.COLOURS.ghost,
					name: rc.last_year.name,
				},
				{
					x: centre + gap / 2,
					value: current[i] || 0,
					colour: this.COLOURS.green,
					name: rc.this_year.name,
				},
			];

			bars.forEach((bar) => {
				const y = ys(bar.value);
				const height = Math.max(0, padding.top + ih - y);
				const rect = this.svg("rect", {
					x: bar.x,
					y: y,
					width: bar_width,
					height: height,
					rx: 3,
					fill: bar.colour,
				});
				rect.style.cursor = "pointer";
				rect.addEventListener("mousemove", (event) =>
					this.show_tip(event, label, [
						{ name: bar.name, colour: bar.colour, value: this.money(bar.value) },
					])
				);
				rect.addEventListener("mouseleave", () => this.hide_tip());
				svg.appendChild(rect);
			});

			const text = this.svg("text", {
				x: centre,
				y: H - 7,
				"text-anchor": "middle",
			});
			text.textContent = label;
			svg.appendChild(text);
		});
	}
};
