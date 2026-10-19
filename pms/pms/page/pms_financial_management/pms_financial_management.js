// Copyright (c) 2026, admin and contributors
// ---------------------------------------------------------------------------
// PMS · Financial Management dashboard — /app/pms-financial-management
//
// All numbers come from one call to
//     pms.pms.financial_dashboard.get_dashboard_data
// which returns sample data for now (see that file to switch to live data).
// Charts use frappe.Chart, which ships with the desk.
// ---------------------------------------------------------------------------

frappe.pages["pms-financial-management"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Financial Management"),
		single_column: true,
	});
	wrapper.fm_dashboard = new pms.FinancialManagement(page);
};

frappe.pages["pms-financial-management"].on_page_show = function (wrapper) {
	wrapper.fm_dashboard && wrapper.fm_dashboard.refresh();
};

frappe.provide("pms");

// Lucide-style line icons (24×24, stroke = currentColor)
const FM_ICONS = {
	receivable: '<path d="M4 2v20l2-1 2 1 2-1 2 1 2-1 2 1 2-1 2 1V2l-2 1-2-1-2 1-2-1-2 1-2-1-2 1Z"/><path d="M16 8h-6a2 2 0 1 0 0 4h4a2 2 0 1 1 0 4H8"/><path d="M12 17.5v-11"/>',
	revenue: '<path d="M3 3v18h18"/><path d="m19 9-5 5-4-4-3 3"/>',
	occupancy: '<path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><path d="M9 22V12h6v10"/>',
	collection_rate: '<circle cx="12" cy="12" r="10"/><path d="m9 12 2 2 4-4"/>',
	deposits: '<path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/><path d="m9 12 2 2 4-4"/>',
	payable: '<path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5z"/><path d="M14 2v6h6"/><path d="M9 15h6"/>',
	overdue: '<circle cx="12" cy="13" r="8"/><path d="M12 9v4l2 2"/><path d="M5 3 2 6"/><path d="m22 6-3-3"/>',
	margin: '<path d="M21.21 15.89A10 10 0 1 1 8 2.83"/><path d="M22 12A10 10 0 0 0 12 2v10z"/>',
};

const FM_TILES = [
	{ key: "receivable", label: __("Rent Receivable"), tone: "blue" },
	{ key: "revenue", label: __("Revenue"), tone: "green" },
	{ key: "occupancy", label: __("Occupancy Rate"), tone: "violet" },
	{ key: "collection_rate", label: __("Collection Rate"), tone: "teal" },
	{ key: "deposits", label: __("Deposits Held"), tone: "amber" },
	{ key: "payable", label: __("Accounts Payable"), tone: "rose" },
	{ key: "overdue", label: __("Overdue Rent"), tone: "orange" },
	{ key: "margin", label: __("Operating Margin"), tone: "indigo" },
];

pms.FinancialManagement = class FinancialManagement {
	constructor(page) {
		this.page = page;
		this.charts = {};
		this.page.set_secondary_action(__("Refresh"), () => this.refresh(), "refresh");
		this.page.add_menu_item(__("Rent Collection Report"), () =>
			frappe.set_route("query-report", "Rent Collection")
		);
		this.page.add_menu_item(__("Financial Dashboard"), () =>
			frappe.set_route("pms-dashboard")
		);

		this.$root = $(this.template()).appendTo(this.page.main);
		this.$root.find(".fm-refresh").on("click", () => this.refresh());

		// redraw charts when the layout width changes (sidebar toggle, resize)
		$(window).on(
			"resize.fm",
			frappe.utils.debounce(() => this.data && this.render_charts(), 250)
		);
	}

	template() {
		const tile = (t) => `
			<div class="fm-tile fm-tone-${t.tone}" data-key="${t.key}">
				<div class="fm-tile-icon">
					<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"
						stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${FM_ICONS[t.key]}</svg>
				</div>
				<div class="fm-tile-body">
					<div class="fm-tile-label">${t.label}</div>
					<div class="fm-tile-value">—</div>
					<div class="fm-tile-note"></div>
				</div>
			</div>`;
		const panel = (key, title, subtitle) => `
			<div class="fm-panel fm-panel-${key}">
				<div class="fm-panel-head">
					<div class="fm-panel-title">${title}</div>
					<div class="fm-panel-sub">${subtitle}</div>
				</div>
				<div class="fm-chart" data-chart="${key}"></div>
			</div>`;

		return `
			<div class="fm-dashboard">
				<div class="fm-header">
					<div class="fm-title">${__("Financial Management Dashboard")}</div>
					<div class="fm-header-meta">
						<span class="fm-sample-badge hide">${__("Sample data")}</span>
						<span class="fm-refreshed text-muted"></span>
						<button class="btn btn-default btn-sm fm-refresh" title="${__("Refresh")}">
							${frappe.utils.icon("refresh", "sm")}
						</button>
					</div>
				</div>

				<div class="fm-tiles fm-tiles-top">
					${FM_TILES.slice(0, 5).map(tile).join("")}
				</div>

				<div class="fm-middle">
					<div class="fm-middle-left">
						<div class="fm-tiles fm-tiles-small">
							${FM_TILES.slice(5).map(tile).join("")}
						</div>
						${panel("occupancy_trend", __("Occupancy Trend"), __("Last 6 months"))}
					</div>
					${panel("billed_vs_collected", __("Rent Billed vs Collected"), __("Last 6 months"))}
				</div>

				<div class="fm-bottom">
					${panel("income_vs_expense", __("Income vs Expenses"), __("Last 6 months"))}
					${panel("receivables_ageing", __("Receivables by Age"), __("Outstanding rent by days overdue"))}
				</div>
			</div>`;
	}

	refresh() {
		this.$root.addClass("fm-loading");
		frappe
			.xcall("pms.pms.financial_dashboard.get_dashboard_data")
			.then((data) => {
				this.data = data;
				this.render();
			})
			.finally(() => this.$root.removeClass("fm-loading"));
	}

	render() {
		const d = this.data;
		this.$root.find(".fm-sample-badge").toggleClass("hide", !d.is_sample);
		this.$root.find(".fm-refreshed").text(__("Data refreshed at {0}", [d.refreshed_at]));

		FM_TILES.forEach((t) => {
			const kpi = d.kpis[t.key] || {};
			const $tile = this.$root.find(`.fm-tile[data-key="${t.key}"]`);
			$tile.find(".fm-tile-value").text(this.format(kpi.value, kpi.format));
			$tile.find(".fm-tile-note").text(kpi.note || "");
			$tile.attr("title", kpi.format === "currency" ? format_currency(kpi.value, d.currency, 0) : "");
		});

		this.render_charts();
	}

	render_charts() {
		const d = this.data;
		const money = (v) => this.format(v, "currency");
		const percent = (v) => `${flt(v, 1)}%`;

		this.chart("occupancy_trend", {
			type: "line",
			data: {
				labels: d.occupancy_trend.labels,
				datasets: [{ name: __("Occupancy"), values: d.occupancy_trend.values }],
			},
			colors: ["#2563eb"],
			lineOptions: { showDots: 1, dotSize: 6 },
			valuesOverPoints: 1,
			axisOptions: { xIsSeries: 1, shortenYAxisNumbers: 1, numberFormatter: percent },
			tooltipOptions: { formatTooltipY: percent },
			height: 250,
		}, percent);

		this.chart("billed_vs_collected", {
			type: "line",
			data: {
				labels: d.billed_vs_collected.labels,
				datasets: [
					{ name: __("Billed"), values: d.billed_vs_collected.billed },
					{ name: __("Collected"), values: d.billed_vs_collected.collected },
				],
			},
			colors: ["#15803d", "#4ade80"],
			lineOptions: { showDots: 1, dotSize: 5 },
			valuesOverPoints: 1,
			axisOptions: { xIsSeries: 1, shortenYAxisNumbers: 1, numberFormatter: money },
			tooltipOptions: { formatTooltipY: money },
			height: 385,
		}, money);

		this.chart("income_vs_expense", {
			type: "bar",
			data: {
				labels: d.income_vs_expense.labels,
				datasets: [
					{ name: __("Income"), values: d.income_vs_expense.income },
					{ name: __("Expenses"), values: d.income_vs_expense.expense },
				],
			},
			colors: ["#db2777", "#f59e0b"],
			barOptions: { spaceRatio: 0.35 },
			valuesOverPoints: 1,
			axisOptions: { shortenYAxisNumbers: 1, numberFormatter: money, seriesLabelSpaceRatio: 1.6 },
			tooltipOptions: { formatTooltipY: money },
			height: 300,
		}, money);

		this.chart("receivables_ageing", {
			type: "bar",
			data: {
				labels: d.receivables_ageing.labels,
				datasets: [{ name: __("Outstanding"), values: d.receivables_ageing.values }],
			},
			colors: ["#6d28d9"],
			barOptions: { spaceRatio: 0.3 },
			valuesOverPoints: 1,
			axisOptions: { shortenYAxisNumbers: 1, numberFormatter: money, seriesLabelSpaceRatio: 1.6 },
			tooltipOptions: { formatTooltipY: money },
			height: 300,
		}, money);
	}

	chart(key, options, value_format) {
		const el = this.$root.find(`.fm-chart[data-chart="${key}"]`)[0];
		el.innerHTML = "";
		this.charts[key] = new frappe.Chart(el, { animate: 0, truncateLegends: 0, ...options });

		// frappe.Chart writes its own K/M numbers over points and bars, and
		// redraws them whenever it re-renders; keep them in the same format
		// as the tiles, written from the data.
		const relabel = () => {
			options.data.datasets.forEach((dataset, i) => {
				$(el).find(`g.dataset-${i} text.data-point-value`).each((j, text) => {
					const index = Number($(text).parent().attr("data-point-index"));
					const label = value_format(dataset.values[index]);
					if (text.textContent !== label) text.textContent = label;
				});
			});
		};
		this.observers = this.observers || {};
		this.observers[key] && this.observers[key].disconnect();
		this.observers[key] = new MutationObserver(relabel);
		this.observers[key].observe(el, { childList: true, subtree: true });
		relabel();
	}

	format(value, kind) {
		if (value == null) return "—";
		if (kind === "percent") return `${flt(value, 1)}%`;
		const country = frappe.sys_defaults && frappe.sys_defaults.country;
		const symbol = get_currency_symbol(this.data.currency) || "";
		return symbol + frappe.utils.shorten_number(value, country, 4, 1).replace(" ", "");
	}
};
