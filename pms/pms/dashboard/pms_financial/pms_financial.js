import React, { useState } from "react";
import {
 LayoutDashboard, Building2, DoorOpen, Users, FileText,
 Wallet, Wrench, BarChart3, Settings, HelpCircle, LogOut,
 Search, Plus, Bell, Download, ArrowUpRight, ArrowDownRight,
 DollarSign, TrendingUp, Clock, ChevronDown
} from "lucide-react";
import {
 ResponsiveContainer, AreaChart, Area, LineChart, Line,
 XAxis, YAxis, CartesianGrid, Tooltip, BarChart, Bar,
 PieChart, Pie, Cell
} from "recharts";

const GREEN = "#16a34a";
const GREEN_SOFT = "#dcfce7";
const RED = "#ef4444";
const AMBER = "#f59e0b";
const INK = "#0f2f22";
const MUTE = "#6b7f75";

const cashFlow = [
 { m: "Jan", income: 96, expenses: 41, net: 55 },
 { m: "Feb", income: 104, expenses: 44, net: 60 },
 { m: "Mar", income: 112, expenses: 39, net: 73 },
 { m: "Apr", income: 108, expenses: 47, net: 61 },
 { m: "May", income: 121, expenses: 43, net: 78 },
 { m: "Jun", income: 128, expenses: 42, net: 86 },
 { m: "Jul", income: 133, expenses: 48, net: 85 },
 { m: "Aug", income: 126, expenses: 45, net: 81 },
 { m: "Sep", income: 130, expenses: 40, net: 90 },
 { m: "Oct", income: 138, expenses: 46, net: 92 },
 { m: "Nov", income: 142, expenses: 44, net: 98 },
 { m: "Dec", income: 149, expenses: 50, net: 99 },
];

const revenue = cashFlow.map((d, i) => ({
 m: d.m,
 now: d.income,
 prev: Math.round(d.income * (0.82 + (i % 4) * 0.03)),
}));

const expenseBreak = [
 { name: "Maintenance", value: 16800, color: "#16a34a" },
 { name: "Utilities", value: 11200, color: "#4ade80" },
 { name: "Operations", value: 8600, color: "#a78bfa" },
 { name: "Services", value: 5700, color: "#f59e0b" },
];
const expenseTotal = expenseBreak.reduce((s, e) => s + e.value, 0);

const nav = [
 { icon: LayoutDashboard, label: "Dashboard", active: true },
 { icon: Building2, label: "Buildings" },
 { icon: DoorOpen, label: "Units" },
 { icon: Users, label: "Tenants" },
 { icon: FileText, label: "Leases" },
 { icon: Wallet, label: "Rent Collection" },
 { icon: Wrench, label: "Maintenance" },
 { icon: BarChart3, label: "Reports" },
];

function money(n) {
 return "$" + n.toLocaleString("en-US");
}

function Kpi({ icon: Icon, label, value, delta, up, sub }) {
 return (
   <div className="rounded-2xl bg-white p-5 border" style={{ borderColor: "#eef2f0" }}>
     <div className="flex items-start justify-between">
       <span className="text-sm" style={{ color: MUTE }}>{label}</span>
       <div className="h-8 w-8 rounded-lg grid place-items-center" style={{ background: "#f2f7f4" }}>
         <Icon size={16} style={{ color: MUTE }} />
       </div>
     </div>
     <div className="mt-3 text-2xl font-semibold tracking-tight" style={{ color: INK }}>{value}</div>
     <div className="mt-2 flex items-center gap-1 text-xs font-medium"
          style={{ color: up ? GREEN : RED }}>
       {up ? <ArrowUpRight size={14} /> : <ArrowDownRight size={14} />}
       {delta}
       <span className="ml-1 font-normal" style={{ color: MUTE }}>{sub}</span>
     </div>
   </div>
 );
}

function ChartTip({ active, payload, label }) {
 if (!active || !payload?.length) return null;
 return (
   <div className="rounded-xl bg-white px-3 py-2 shadow-lg border text-xs"
        style={{ borderColor: "#eef2f0" }}>
     <div className="font-semibold mb-1" style={{ color: INK }}>{label}</div>
     {payload.map((p) => (
       <div key={p.name} className="flex items-center gap-2" style={{ color: MUTE }}>
         <span className="h-2 w-2 rounded-full" style={{ background: p.color || p.stroke }} />
         <span className="capitalize">{p.name}</span>
         <span className="ml-auto font-medium" style={{ color: INK }}>${p.value}k</span>
       </div>
     ))}
   </div>
 );
}

export default function PmsDashboard() {
 const [active, setActive] = useState("Dashboard");
 const [period, setPeriod] = useState("This Year");

 return (
   <div className="min-h-screen w-full flex text-[15px]"
        style={{ background: "#f5f8f6", fontFamily: "'Inter','Segoe UI',system-ui,sans-serif" }}>
     {/* Sidebar */}
     <aside className="hidden md:flex w-60 shrink-0 flex-col bg-white border-r px-4 py-5"
            style={{ borderColor: "#eef2f0" }}>
       <div className="flex items-center gap-2 px-2 mb-7">
         <div className="h-9 w-9 rounded-xl grid place-items-center" style={{ background: GREEN }}>
           <Building2 size={18} color="#fff" />
         </div>
         <div>
           <div className="font-bold leading-none" style={{ color: INK }}>NextOra</div>
           <div className="text-[11px] tracking-wide" style={{ color: MUTE }}>PMS</div>
         </div>
       </div>

       <p className="px-3 text-[11px] font-semibold uppercase tracking-wider mb-2" style={{ color: "#9fb3a9" }}>Menu</p>
       <nav className="flex flex-col gap-1">
         {nav.map((n) => {
           const on = active === n.label;
           return (
             <button key={n.label} onClick={() => setActive(n.label)}
               className="flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition"
               style={{
                 background: on ? GREEN_SOFT : "transparent",
                 color: on ? "#166534" : "#42544c",
               }}>
               <n.icon size={18} />
               {n.label}
             </button>
           );
         })}
       </nav>

       <p className="px-3 text-[11px] font-semibold uppercase tracking-wider mt-6 mb-2" style={{ color: "#9fb3a9" }}>General</p>
       <nav className="flex flex-col gap-1">
         {[["Settings", Settings], ["Help", HelpCircle], ["Logout", LogOut]].map(([l, I]) => (
           <button key={l} className="flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium" style={{ color: "#42544c" }}>
             <I size={18} /> {l}
           </button>
         ))}
       </nav>

       <div className="mt-auto rounded-2xl p-4 text-white" style={{ background: "linear-gradient(160deg,#166534,#16a34a)" }}>
         <p className="font-semibold text-sm">Occupancy</p>
         <p className="text-[12px] opacity-80 mt-0.5">11 of 12 units leased</p>
         <div className="mt-3 h-1.5 w-full rounded-full bg-white/25">
           <div className="h-full rounded-full bg-white" style={{ width: "92%" }} />
         </div>
         <p className="mt-2 text-2xl font-bold">92%</p>
       </div>
     </aside>

     {/* Main */}
     <main className="flex-1 min-w-0 flex flex-col">
       {/* Topbar */}
       <header className="flex items-center gap-4 px-6 py-4 border-b bg-white/70 backdrop-blur"
               style={{ borderColor: "#eef2f0" }}>
         <div>
           <h1 className="text-lg font-semibold" style={{ color: INK }}>Financial</h1>
           <p className="text-xs" style={{ color: MUTE }}>Rent, expenses and collections across your portfolio</p>
         </div>
         <div className="ml-auto hidden lg:flex items-center gap-2 rounded-xl px-3 py-2 w-72 border" style={{ borderColor: "#eef2f0", background: "#f7faf8" }}>
           <Search size={16} style={{ color: MUTE }} />
           <input placeholder="Search property, tenant or invoice"
                  className="bg-transparent outline-none text-sm w-full" style={{ color: INK }} />
         </div>
         <button className="flex items-center gap-1.5 rounded-xl px-3.5 py-2 text-sm font-medium text-white" style={{ background: GREEN }}>
           <Plus size={16} /> Add Transaction
         </button>
         <button className="h-9 w-9 grid place-items-center rounded-xl border" style={{ borderColor: "#eef2f0" }}>
           <Bell size={16} style={{ color: MUTE }} />
         </button>
         <div className="flex items-center gap-2 pl-1">
           <div className="h-9 w-9 rounded-full grid place-items-center text-white text-sm font-semibold" style={{ background: "#166534" }}>NX</div>
           <div className="hidden xl:block leading-tight">
             <div className="text-sm font-medium" style={{ color: INK }}>Administrator</div>
             <div className="text-[11px]" style={{ color: MUTE }}>NextOraPMS</div>
           </div>
           <ChevronDown size={16} style={{ color: MUTE }} />
         </div>
       </header>

       <div className="p-6 flex flex-col gap-5 overflow-y-auto">
         {/* Tabs + export */}
         <div className="flex items-center gap-2">
           {["Overview", "Transactions", "Invoices"].map((t, i) => (
             <button key={t}
               className="rounded-lg px-3.5 py-1.5 text-sm font-medium"
               style={i === 0
                 ? { background: GREEN_SOFT, color: "#166534" }
                 : { color: MUTE }}>
               {t}
             </button>
           ))}
           <button className="ml-auto flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-sm font-medium"
                   style={{ borderColor: "#eef2f0", color: "#42544c" }}>
             <Download size={15} /> Export
           </button>
         </div>

         {/* KPI row */}
         <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
           <Kpi icon={DollarSign} label="Rent Collected (This Month)" value={money(128400)} delta="+14.2%" up sub="vs last month" />
           <Kpi icon={TrendingUp} label="Expenses (This Month)" value={money(42300)} delta="-6.1%" up={false} sub="vs last month" />
           <Kpi icon={Wallet} label="Net Income (This Month)" value={money(86100)} delta="+18.7%" up sub="vs last month" />
           <Kpi icon={Clock} label="Pending Rent" value={money(23750)} delta="5 overdue" up={false} sub="across 3 tenants" />
         </div>

         {/* Cash flow + donut */}
         <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
           <div className="lg:col-span-2 rounded-2xl bg-white p-5 border" style={{ borderColor: "#eef2f0" }}>
             <div className="flex items-center justify-between mb-2">
               <div>
                 <h3 className="font-semibold" style={{ color: INK }}>Cash Flow Analysis</h3>
                 <div className="flex items-center gap-4 mt-2 text-xs" style={{ color: MUTE }}>
                   <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full" style={{ background: GREEN }} />Income</span>
                   <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full" style={{ background: RED }} />Expenses</span>
                   <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full" style={{ background: AMBER }} />Net</span>
                 </div>
               </div>
               <button onClick={() => setPeriod(period === "This Year" ? "Last Year" : "This Year")}
                       className="flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-medium"
                       style={{ borderColor: "#eef2f0", color: "#42544c" }}>
                 {period} <ChevronDown size={14} />
               </button>
             </div>
             <ResponsiveContainer width="100%" height={260}>
               <AreaChart data={cashFlow} margin={{ top: 10, right: 8, left: -18, bottom: 0 }}>
                 <defs>
                   <linearGradient id="inc" x1="0" y1="0" x2="0" y2="1">
                     <stop offset="0%" stopColor={GREEN} stopOpacity={0.25} />
                     <stop offset="100%" stopColor={GREEN} stopOpacity={0} />
                   </linearGradient>
                 </defs>
                 <CartesianGrid vertical={false} stroke="#eef2f0" />
                 <XAxis dataKey="m" tickLine={false} axisLine={false} tick={{ fill: MUTE, fontSize: 11 }} />
                 <YAxis tickLine={false} axisLine={false} tick={{ fill: MUTE, fontSize: 11 }} tickFormatter={(v) => `$${v}k`} />
                 <Tooltip content={<ChartTip />} />
                 <Area type="monotone" dataKey="income" stroke={GREEN} strokeWidth={2.5} fill="url(#inc)" />
                 <Line type="monotone" dataKey="expenses" stroke={RED} strokeWidth={2} strokeDasharray="5 4" dot={false} />
                 <Line type="monotone" dataKey="net" stroke={AMBER} strokeWidth={2} strokeDasharray="5 4" dot={false} />
               </AreaChart>
             </ResponsiveContainer>
           </div>

           <div className="rounded-2xl bg-white p-5 border" style={{ borderColor: "#eef2f0" }}>
             <h3 className="font-semibold mb-1" style={{ color: INK }}>Expense Breakdown</h3>
             <div className="relative">
               <ResponsiveContainer width="100%" height={190}>
                 <PieChart>
                   <Pie data={expenseBreak} dataKey="value" innerRadius={62} outerRadius={82} paddingAngle={3} stroke="none">
                     {expenseBreak.map((e) => <Cell key={e.name} fill={e.color} />)}
                   </Pie>
                 </PieChart>
               </ResponsiveContainer>
               <div className="absolute inset-0 grid place-items-center pointer-events-none">
                 <div className="text-center">
                   <div className="text-[11px]" style={{ color: MUTE }}>Total Expenses</div>
                   <div className="text-xl font-semibold" style={{ color: INK }}>{money(expenseTotal)}</div>
                 </div>
               </div>
             </div>
             <div className="mt-3 space-y-2">
               {expenseBreak.map((e) => (
                 <div key={e.name} className="flex items-center gap-2 text-sm">
                   <span className="h-2.5 w-2.5 rounded-sm" style={{ background: e.color }} />
                   <span style={{ color: "#42544c" }}>{e.name}</span>
                   <span className="ml-auto font-medium" style={{ color: INK }}>{money(e.value)}</span>
                   <span className="w-10 text-right text-xs" style={{ color: MUTE }}>{Math.round(e.value / expenseTotal * 100)}%</span>
                 </div>
               ))}
             </div>
           </div>
         </div>

         {/* Revenue comparison */}
         <div className="rounded-2xl bg-white p-5 border" style={{ borderColor: "#eef2f0" }}>
           <div className="flex items-center justify-between mb-3">
             <h3 className="font-semibold" style={{ color: INK }}>Revenue Comparison</h3>
             <div className="flex items-center gap-4 text-xs" style={{ color: MUTE }}>
               <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full" style={{ background: GREEN }} />2026</span>
               <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full" style={{ background: "#d5e8dd" }} />2025</span>
             </div>
           </div>
           <ResponsiveContainer width="100%" height={230}>
             <BarChart data={revenue} margin={{ top: 6, right: 8, left: -18, bottom: 0 }} barGap={4}>
               <CartesianGrid vertical={false} stroke="#eef2f0" />
               <XAxis dataKey="m" tickLine={false} axisLine={false} tick={{ fill: MUTE, fontSize: 11 }} />
               <YAxis tickLine={false} axisLine={false} tick={{ fill: MUTE, fontSize: 11 }} tickFormatter={(v) => `$${v}k`} />
               <Tooltip content={<ChartTip />} cursor={{ fill: "#f3f7f5" }} />
               <Bar dataKey="prev" name="2025" fill="#d5e8dd" radius={[4, 4, 0, 0]} />
               <Bar dataKey="now" name="2026" fill={GREEN} radius={[4, 4, 0, 0]} />
             </BarChart>
           </ResponsiveContainer>
         </div>
       </div>
     </main>
   </div>
 );
}
