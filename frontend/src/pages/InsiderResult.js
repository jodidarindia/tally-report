import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import {
  Users, TrendingUp, Package, AlertTriangle, Activity, Target,
  UserCheck, UserX, UserMinus, ArrowUpRight, ArrowDownRight,
  BarChart3, Search, ChevronDown, ChevronUp, Info
} from 'lucide-react';
import {
  AreaChart, Area, BarChart, Bar, LineChart, Line, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
  ComposedChart, ReferenceLine
} from 'recharts';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

const TABS = [
  { id: 'lifecycle', label: 'Customer Lifecycle', icon: Users },
  { id: 'forecast', label: 'Sales Forecast', icon: TrendingUp },
  { id: 'spip', label: 'SPIP Analysis', icon: Package },
  { id: 'concentration', label: 'Concentration Risk', icon: Target },
];

const STATUS_COLORS = {
  active: '#10B981',
  inactive: '#F59E0B',
  lost: '#EF4444',
};

const GAP_COLORS = {
  out_of_stock: '#EF4444',
  understocked: '#F97316',
  dead_stock: '#8B5CF6',
  overstocked: '#F59E0B',
  balanced: '#10B981',
  no_movement: '#94A3B8',
};

const GAP_LABELS = {
  out_of_stock: 'Out of Stock',
  understocked: 'Understocked',
  dead_stock: 'Dead Stock',
  overstocked: 'Overstocked',
  balanced: 'Balanced',
  no_movement: 'No Movement (12m)',
};

const RISK_COLORS = {
  critical: { bg: 'bg-red-50', text: 'text-red-700', border: 'border-red-200', label: 'Critical' },
  high: { bg: 'bg-orange-50', text: 'text-orange-700', border: 'border-orange-200', label: 'High Risk' },
  moderate: { bg: 'bg-yellow-50', text: 'text-yellow-700', border: 'border-yellow-200', label: 'Moderate' },
  healthy: { bg: 'bg-green-50', text: 'text-green-700', border: 'border-green-200', label: 'Healthy' },
  no_data: { bg: 'bg-slate-50', text: 'text-slate-500', border: 'border-slate-200', label: 'No Data' },
};

const fmt = (n) => {
  if (n === undefined || n === null) return '0';
  if (n >= 10000000) return `${(n / 10000000).toFixed(2)} Cr`;
  if (n >= 100000) return `${(n / 100000).toFixed(2)} L`;
  if (n >= 1000) return `${(n / 1000).toFixed(1)} K`;
  return Number(n).toLocaleString('en-IN', { maximumFractionDigits: 0 });
};

const fmtFull = (n) => Number(n || 0).toLocaleString('en-IN', { maximumFractionDigits: 2 });

const StatCard = ({ icon: Icon, label, value, sub, color = 'bg-slate-50', textColor = 'text-slate-900', testId, onClick, selected = false }) => (
  <div
    className={`${color} rounded-xl p-4 border ${selected ? 'border-slate-800 ring-2 ring-slate-300' : 'border-slate-100'} ${onClick ? 'cursor-pointer transition hover:ring-2 hover:ring-offset-1 hover:ring-slate-200' : ''}`}
    onClick={onClick}
    data-testid={testId}
    role={onClick ? 'button' : undefined}
    tabIndex={onClick ? 0 : undefined}
    onKeyDown={onClick ? (e) => { if (e.key === 'Enter' || e.key === ' ') onClick(); } : undefined}
  >
    <div className="flex items-center gap-2 mb-1">
      <Icon size={16} className={textColor} />
      <span className="text-xs font-medium text-slate-500">{label}</span>
    </div>
    <div className={`text-xl font-bold ${textColor}`}>{value}</div>
    {sub && <div className="text-xs text-slate-500 mt-0.5">{sub}</div>}
  </div>
);

const InsiderResult = ({ selectedFY, companyId }) => {
  const [activeTab, setActiveTab] = useState('lifecycle');
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');

  // Data states
  const [lifecycle, setLifecycle] = useState(null);
  const [forecast, setForecast] = useState(null);
  const [spip, setSpip] = useState(null);
  const [concentration, setConcentration] = useState(null);

  // Sub-filters
  const [lifecycleFilter, setLifecycleFilter] = useState('all');
  const [spipFilter, setSpipFilter] = useState('all');
  const [sortField, setSortField] = useState('');
  const [sortDir, setSortDir] = useState('desc');
  // Pagination — single source of truth for both Lifecycle and SPIP tables.
  // Reset to 1 whenever the active tab, filter or search changes (below).
  const [lifecyclePage, setLifecyclePage] = useState(1);
  const [spipPage, setSpipPage] = useState(1);
  const PAGE_SIZE = 50;

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const fyParam = selectedFY ? `fy=${selectedFY}` : '';
      if (activeTab === 'lifecycle') {
        const res = await axios.get(`${API}/insights/customer-lifecycle?${fyParam}`);
        setLifecycle(res.data?.data || null);
      } else if (activeTab === 'forecast') {
        const res = await axios.get(`${API}/insights/sales-forecast?${fyParam}`);
        setForecast(res.data?.data || null);
      } else if (activeTab === 'spip') {
        const res = await axios.get(`${API}/insights/spip-analysis?${fyParam}`);
        setSpip(res.data?.data || null);
      } else if (activeTab === 'concentration') {
        const res = await axios.get(`${API}/insights/concentration-risk?${fyParam}`);
        setConcentration(res.data?.data || null);
      }
    } catch (err) {
      console.error('Insider Result fetch failed:', err?.response?.status, err?.response?.data, err);
      toast.error(`Failed to load ${activeTab} data: ${err?.response?.status || err?.message || 'unknown error'}`);
    } finally {
      setLoading(false);
    }
  }, [activeTab, selectedFY]);

  useEffect(() => { fetchData(); }, [fetchData]);

  // Reset pagination on filter/search/tab change so the user always lands on
  // page 1 (otherwise switching from a 1800-row "all" view to a 30-row
  // "active" view leaves you on a non-existent page 36).
  useEffect(() => { setLifecyclePage(1); }, [lifecycleFilter, search, activeTab, selectedFY]);
  useEffect(() => { setSpipPage(1); }, [spipFilter, search, activeTab, selectedFY]);

  const handleSort = (field) => {
    if (sortField === field) setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    else { setSortField(field); setSortDir('desc'); }
  };

  const sortData = (data, field, dir) => {
    if (!field) return data;
    return [...data].sort((a, b) => {
      const va = a[field] ?? 0;
      const vb = b[field] ?? 0;
      if (typeof va === 'string') return dir === 'asc' ? va.localeCompare(vb) : vb.localeCompare(va);
      return dir === 'asc' ? va - vb : vb - va;
    });
  };

  const SortTh = ({ field, label, className = '' }) => (
    <th
      className={`px-3 py-2.5 text-left text-xs font-semibold text-slate-600 cursor-pointer select-none hover:bg-slate-50 ${className}`}
      onClick={() => handleSort(field)}
      data-testid={`sort-${field}`}
    >
      <span className="flex items-center gap-1">
        {label}
        {sortField === field ? (sortDir === 'asc' ? ' \u2191' : ' \u2193') : ''}
      </span>
    </th>
  );

  // Compact pager — used by Lifecycle and SPIP tables. Hides itself when there
  // are fewer rows than one page. Includes First / Prev / Next / Last and a
  // "page X of Y" indicator. Keeps row counts honest for users who previously
  // saw "Showing 100 of 1844" with no way to reach the rest.
  const Pager = ({ page, total, pageSize, onPage, testIdPrefix }) => {
    const totalPages = Math.max(1, Math.ceil(total / pageSize));
    if (total <= pageSize) {
      return (
        <div className="p-3 text-center text-xs text-slate-400" data-testid={`${testIdPrefix}-empty`}>
          {total === 0 ? 'No rows' : `Showing ${total} of ${total}`}
        </div>
      );
    }
    const start = (page - 1) * pageSize + 1;
    const end = Math.min(page * pageSize, total);
    const go = (p) => onPage(Math.max(1, Math.min(totalPages, p)));
    const btn = "px-2.5 py-1 text-xs border border-slate-200 rounded hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed";
    return (
      <div className="flex items-center justify-between gap-2 p-3 border-t border-slate-100" data-testid={testIdPrefix}>
        <div className="text-xs text-slate-500">
          Showing <span className="font-medium text-slate-700">{start}–{end}</span> of <span className="font-medium text-slate-700">{total}</span>
        </div>
        <div className="flex items-center gap-1.5">
          <button onClick={() => go(1)} disabled={page === 1} className={btn} data-testid={`${testIdPrefix}-first`}>« First</button>
          <button onClick={() => go(page - 1)} disabled={page === 1} className={btn} data-testid={`${testIdPrefix}-prev`}>‹ Prev</button>
          <span className="px-2 text-xs text-slate-600 font-medium" data-testid={`${testIdPrefix}-current`}>Page {page} / {totalPages}</span>
          <button onClick={() => go(page + 1)} disabled={page === totalPages} className={btn} data-testid={`${testIdPrefix}-next`}>Next ›</button>
          <button onClick={() => go(totalPages)} disabled={page === totalPages} className={btn} data-testid={`${testIdPrefix}-last`}>Last »</button>
        </div>
      </div>
    );
  };

  const CustomTooltip = ({ active, payload, label }) => {
    if (!active || !payload?.length) return null;
    return (
      <div className="bg-white border border-slate-200 rounded-lg shadow-lg p-3 text-xs">
        <div className="font-semibold text-slate-700 mb-1">{label}</div>
        {payload.map((p, i) => (
          <div key={i} className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full" style={{ backgroundColor: p.color }} />
            <span className="text-slate-500">{p.name}:</span>
            <span className="font-medium text-slate-800">{typeof p.value === 'number' ? fmtFull(p.value) : p.value}</span>
          </div>
        ))}
      </div>
    );
  };

  // ============ LIFECYCLE TAB ============
  const renderLifecycle = () => {
    if (!lifecycle) return null;
    const { active, inactive, lost, summary, trend } = lifecycle;

    const pieData = [
      { name: 'Active', value: summary.active_count, color: STATUS_COLORS.active },
      { name: 'Inactive', value: summary.inactive_count, color: STATUS_COLORS.inactive },
      { name: 'Lost', value: summary.lost_count, color: STATUS_COLORS.lost },
    ];

    const allCustomers = [
      ...active.map(c => ({ ...c, _status: 'active' })),
      ...inactive.map(c => ({ ...c, _status: 'inactive' })),
      ...lost.map(c => ({ ...c, _status: 'lost' })),
    ];

    let filtered = lifecycleFilter === 'all' ? allCustomers : allCustomers.filter(c => c._status === lifecycleFilter);
    if (search) filtered = filtered.filter(c => c.customer_name.toLowerCase().includes(search.toLowerCase()));
    filtered = sortData(filtered, sortField, sortDir);

    return (
      <div className="space-y-6">
        {/* Summary cards (clickable to filter) */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <StatCard icon={UserCheck} label="Active Customers" value={summary.active_count} sub={`Revenue: ${fmt(summary.active_revenue)}`} color="bg-emerald-50" textColor="text-emerald-700" testId="stat-active" onClick={() => setLifecycleFilter(lifecycleFilter === 'active' ? 'all' : 'active')} selected={lifecycleFilter === 'active'} />
          <StatCard icon={UserMinus} label="Inactive (90+ days)" value={summary.inactive_count} sub={`Revenue: ${fmt(summary.inactive_revenue)}`} color="bg-amber-50" textColor="text-amber-700" testId="stat-inactive" onClick={() => setLifecycleFilter(lifecycleFilter === 'inactive' ? 'all' : 'inactive')} selected={lifecycleFilter === 'inactive'} />
          <StatCard icon={UserX} label="Lost (180+ days)" value={summary.lost_count} sub={`Revenue: ${fmt(summary.lost_revenue)}`} color="bg-red-50" textColor="text-red-700" testId="stat-lost" onClick={() => setLifecycleFilter(lifecycleFilter === 'lost' ? 'all' : 'lost')} selected={lifecycleFilter === 'lost'} />
          <StatCard icon={Users} label="Total Customers" value={allCustomers.length} sub="All — click to clear filter" color="bg-blue-50" textColor="text-blue-700" testId="stat-total" onClick={() => setLifecycleFilter('all')} selected={lifecycleFilter === 'all'} />
        </div>

        {/* Charts */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {/* Pie Chart */}
          <div className="bg-white rounded-xl border border-slate-200 p-4" data-testid="lifecycle-pie-chart">
            <h3 className="text-sm font-semibold text-slate-700 mb-3">Customer Distribution</h3>
            <ResponsiveContainer width="100%" height={240}>
              <PieChart>
                <Pie data={pieData} cx="50%" cy="50%" innerRadius={55} outerRadius={90} dataKey="value" nameKey="name" paddingAngle={3}>
                  {pieData.map((entry, i) => <Cell key={i} fill={entry.color} />)}
                </Pie>
                <Tooltip content={<CustomTooltip />} />
                <Legend verticalAlign="bottom" height={36} iconType="circle" />
              </PieChart>
            </ResponsiveContainer>
          </div>

          {/* Monthly Trend */}
          <div className="bg-white rounded-xl border border-slate-200 p-4" data-testid="lifecycle-trend-chart">
            <h3 className="text-sm font-semibold text-slate-700 mb-3">Monthly Active Customers</h3>
            <ResponsiveContainer width="100%" height={240}>
              <AreaChart data={trend}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                <XAxis dataKey="month" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip content={<CustomTooltip />} />
                <Area type="monotone" dataKey="active" stroke="#10B981" fill="#10B98133" name="Active" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Customer Table */}
        <div className="bg-white rounded-xl border border-slate-200" data-testid="lifecycle-table">
          <div className="p-4 border-b border-slate-100 flex flex-col sm:flex-row items-start sm:items-center gap-3">
            <h3 className="text-sm font-semibold text-slate-700">Customer Details</h3>
            <div className="flex items-center gap-2 ml-auto flex-wrap">
              <div className="relative">
                <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400" />
                <input
                  value={search} onChange={e => setSearch(e.target.value)}
                  placeholder="Search customer..."
                  className="pl-8 pr-3 py-1.5 text-xs border border-slate-200 rounded-lg w-48 focus:outline-none focus:ring-1 focus:ring-blue-500"
                  data-testid="lifecycle-search"
                />
              </div>
              <select value={lifecycleFilter} onChange={e => setLifecycleFilter(e.target.value)} className="text-xs border border-slate-200 rounded-lg px-2 py-1.5" data-testid="lifecycle-filter">
                <option value="all">All Status ({allCustomers.length})</option>
                <option value="active">Active ({summary.active_count})</option>
                <option value="inactive">Inactive ({summary.inactive_count})</option>
                <option value="lost">Lost ({summary.lost_count})</option>
              </select>
            </div>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead className="bg-slate-50 border-b border-slate-100">
                <tr>
                  <SortTh field="customer_name" label="Customer" />
                  <th className="px-3 py-2.5 text-left text-xs font-semibold text-slate-600">Status</th>
                  <SortTh field="days_since_last" label="Days Since Last" />
                  <SortTh field="total_revenue" label="Revenue" />
                  <SortTh field="transaction_count" label="Transactions" />
                  <th className="px-3 py-2.5 text-left text-xs font-semibold text-slate-600">Last Txn</th>
                </tr>
              </thead>
              <tbody>
                {filtered
                  .slice((lifecyclePage - 1) * PAGE_SIZE, lifecyclePage * PAGE_SIZE)
                  .map((c, i) => (
                  <tr key={i} className="border-b border-slate-50 hover:bg-slate-25" data-testid={`lifecycle-row-${i}`}>
                    <td className="px-3 py-2.5 font-medium text-slate-800 max-w-[200px] truncate">{c.customer_name}</td>
                    <td className="px-3 py-2.5">
                      <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold capitalize ${
                        c._status === 'active' ? 'bg-emerald-100 text-emerald-700' :
                        c._status === 'inactive' ? 'bg-amber-100 text-amber-700' :
                        'bg-red-100 text-red-700'
                      }`}>{c._status}</span>
                    </td>
                    <td className="px-3 py-2.5 text-slate-600">{c.days_since_last === 999 ? 'N/A' : `${c.days_since_last}d`}</td>
                    <td className="px-3 py-2.5 font-medium text-slate-800">{fmt(c.total_revenue)}</td>
                    <td className="px-3 py-2.5 text-slate-600">{c.transaction_count}</td>
                    <td className="px-3 py-2.5 text-slate-500">{c.last_transaction || 'N/A'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pager
            page={lifecyclePage}
            total={filtered.length}
            pageSize={PAGE_SIZE}
            onPage={setLifecyclePage}
            testIdPrefix="lifecycle-pager"
          />
        </div>
      </div>
    );
  };

  // ============ FORECAST TAB ============
  const renderForecast = () => {
    if (!forecast) return null;
    const timeline = forecast.timeline || [];
    const forecasts = forecast.forecasts || [];
    const yoy = forecast.yoy || [];
    const monthComparison = forecast.month_comparison || [];
    const s = forecast.summary || {};

    const chartData = [
      ...timeline.map(t => ({ month: t.month, revenue: t.revenue, forecast: null, type: 'actual' })),
      // Bridge actual → forecast: include the last actual month's revenue as
      // the FIRST point of the forecast line so the line connects visually
      // (Recharts wouldn't otherwise — undefined → defined creates a gap).
      ...(forecasts.length && timeline.length ? [{
        month: timeline[timeline.length - 1].month,
        revenue: null,
        forecast: timeline[timeline.length - 1].revenue,
        type: 'bridge',
      }] : []),
      ...forecasts.map(f => ({
        month: f.month,
        revenue: null,
        forecast: f.forecast_revenue,
        type: 'forecast',
        confidence: f.confidence,
        based_on: f.based_on_prev_fy_month,
        growth_trend_pct: f.growth_trend_pct,
      })),
    ];

    // Pivot month_comparison into a chart-friendly shape:
    // Backend returns [{ month_num: '04', month_name: 'Apr', data: [{fy: '2025-26', revenue: ...}, ...]}]
    // We need [{ month: 'Apr', '2024-25': 12L, '2025-26': 18L, ... }] for the chart.
    const allFYKeys = new Set();
    monthComparison.forEach(row => (row.data || []).forEach(d => allFYKeys.add(d.fy)));
    const fyKeys = [...allFYKeys].sort();
    const fyColors = ['#94a3b8', '#0EA5E9', '#2563EB', '#8B5CF6', '#10B981'];

    const compChartRows = monthComparison.map(row => {
      const out = { month: row.month_name };
      (row.data || []).forEach(d => {
        out[d.fy] = d.revenue || 0;
      });
      return out;
    });

    // Compute YoY % delta vs the previous FY for each month (for the table).
    const compTableRows = compChartRows.map(row => {
      const out = { month: row.month };
      fyKeys.forEach((fy, idx) => {
        out[fy] = row[fy] || 0;
        if (idx > 0) {
          const prev = row[fyKeys[idx - 1]] || 0;
          out[`${fy}_delta`] = prev > 0 ? ((out[fy] - prev) / prev) * 100 : null;
        }
      });
      return out;
    });

    return (
      <div className="space-y-6">
        {/* Summary */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <StatCard icon={BarChart3} label="Monthly Average" value={fmt(s.avg_monthly_revenue)} sub={`${s.total_months} months of data`} color="bg-blue-50" textColor="text-blue-700" testId="stat-avg-revenue" />
          <StatCard icon={TrendingUp} label="Best Month" value={s.best_month || 'N/A'} sub={`Revenue: ${fmt(s.best_month_revenue)}`} color="bg-emerald-50" textColor="text-emerald-700" testId="stat-best-month" />
          {forecasts[0] && (
            <StatCard icon={ArrowUpRight} label="Next Month Forecast" value={fmt(forecasts[0].forecast_revenue)} sub={`Confidence: ${forecasts[0].confidence}`} color="bg-purple-50" textColor="text-purple-700" testId="stat-forecast-next" />
          )}
          {forecasts[2] && (
            <StatCard icon={Target} label="3-Month Forecast" value={fmt(forecasts[2].forecast_revenue)} sub={`Confidence: ${forecasts[2].confidence}`} color="bg-indigo-50" textColor="text-indigo-700" testId="stat-forecast-3m" />
          )}
        </div>

        {/* Revenue Timeline Chart */}
        <div className="bg-white rounded-xl border border-slate-200 p-4" data-testid="forecast-chart">
          <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
            <h3 className="text-sm font-semibold text-slate-700">Revenue Trend & Forecast</h3>
            {forecasts[0]?.based_on_prev_fy_month && (
              <span className="text-[11px] text-slate-500" data-testid="forecast-method-note">
                Forecast = same-month previous FY × growth trend
                {forecasts[0].growth_trend_pct !== null && (
                  <span className={`ml-1 font-medium ${forecasts[0].growth_trend_pct >= 0 ? 'text-emerald-600' : 'text-rose-500'}`}>
                    ({forecasts[0].growth_trend_pct >= 0 ? '▲' : '▼'} {Math.abs(forecasts[0].growth_trend_pct)}%)
                  </span>
                )}
              </span>
            )}
          </div>
          <ResponsiveContainer width="100%" height={320}>
            <ComposedChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis dataKey="month" tick={{ fontSize: 10 }} angle={-35} textAnchor="end" height={50} />
              <YAxis tick={{ fontSize: 10 }} tickFormatter={v => fmt(v)} />
              <Tooltip content={<CustomTooltip />} />
              <Legend />
              <Bar dataKey="revenue" fill="#2563EB" name="Actual Revenue" radius={[3, 3, 0, 0]} />
              <Line
                type="monotone"
                dataKey="forecast"
                stroke="#8B5CF6"
                strokeWidth={2.5}
                strokeDasharray="6 3"
                dot={{ fill: '#8B5CF6', r: 4 }}
                connectNulls
                name="Forecast"
              />
            </ComposedChart>
          </ResponsiveContainer>
        </div>

        {/* YoY Comparison */}
        <div className="bg-white rounded-xl border border-slate-200 p-4" data-testid="yoy-chart">
          <h3 className="text-sm font-semibold text-slate-700 mb-3">Financial Year Comparison</h3>
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={yoy}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis dataKey="year" tick={{ fontSize: 11 }} tickFormatter={v => `FY ${v}`} />
              <YAxis tick={{ fontSize: 10 }} tickFormatter={v => fmt(v)} />
              <Tooltip content={<CustomTooltip />} />
              <Bar dataKey="revenue" fill="#0EA5E9" name="Revenue" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Cross-FY Month-over-Month — answers "How did Apr-26 do vs Apr-25?" */}
        {compChartRows.length > 0 && fyKeys.length > 0 && (
          <div className="bg-white rounded-xl border border-slate-200 p-4" data-testid="month-comparison-chart">
            <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
              <h3 className="text-sm font-semibold text-slate-700">Month-over-Month FY Comparison</h3>
              <span className="text-[11px] text-slate-500">{fyKeys.length} FYs · {compChartRows.length} months</span>
            </div>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={compChartRows}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                <XAxis dataKey="month" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 10 }} tickFormatter={v => fmt(v)} />
                <Tooltip content={<CustomTooltip />} />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                {fyKeys.map((fy, idx) => (
                  <Bar
                    key={fy}
                    dataKey={fy}
                    fill={fyColors[idx % fyColors.length]}
                    name={`FY ${fy}`}
                    radius={[3, 3, 0, 0]}
                  />
                ))}
              </BarChart>
            </ResponsiveContainer>

            {/* Compact table with %-deltas vs previous FY */}
            <div className="overflow-x-auto mt-4" data-testid="month-comparison-table">
              <table className="w-full text-xs">
                <thead className="bg-slate-50 border-b border-slate-100">
                  <tr>
                    <th className="px-3 py-2 text-left font-semibold text-slate-600">Month</th>
                    {fyKeys.map((fy, idx) => (
                      <th key={fy} className="px-3 py-2 text-right font-semibold text-slate-600">
                        FY {fy}{idx > 0 ? <span className="block text-[9px] font-normal text-slate-400">vs prev FY</span> : null}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {compTableRows.map((row, i) => (
                    <tr key={i} className="border-b border-slate-50">
                      <td className="px-3 py-2 font-medium text-slate-700">{row.month}</td>
                      {fyKeys.map((fy, idx) => {
                        const v = row[fy] || 0;
                        const delta = row[`${fy}_delta`];
                        return (
                          <td key={fy} className="px-3 py-2 text-right">
                            <div className="font-medium text-slate-800">{v ? fmt(v) : <span className="text-slate-300">—</span>}</div>
                            {idx > 0 && delta !== null && delta !== undefined && (
                              <div className={`text-[10px] ${delta >= 0 ? 'text-emerald-600' : 'text-rose-500'}`}>
                                {delta >= 0 ? '▲' : '▼'} {Math.abs(delta).toFixed(1)}%
                              </div>
                            )}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Monthly Details Table */}
        <div className="bg-white rounded-xl border border-slate-200" data-testid="forecast-table">
          <div className="p-4 border-b border-slate-100">
            <h3 className="text-sm font-semibold text-slate-700">Monthly Breakdown</h3>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead className="bg-slate-50 border-b border-slate-100">
                <tr>
                  <SortTh field="month" label="Month" />
                  <SortTh field="revenue" label="Revenue" />
                  <SortTh field="count" label="Vouchers" />
                  <SortTh field="unique_customers" label="Unique Customers" />
                </tr>
              </thead>
              <tbody>
                {sortData([...timeline].reverse(), sortField, sortDir).slice(0, 24).map((t, i) => (
                  <tr key={i} className="border-b border-slate-50 hover:bg-slate-25" data-testid={`forecast-row-${i}`}>
                    <td className="px-3 py-2.5 font-medium text-slate-700">{t.month}</td>
                    <td className="px-3 py-2.5 font-semibold text-slate-800">{fmt(t.revenue)}</td>
                    <td className="px-3 py-2.5 text-slate-600">{t.count}</td>
                    <td className="px-3 py-2.5 text-slate-600">{t.unique_customers}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    );
  };

  // ============ SPIP TAB ============
  const renderSpip = () => {
    if (!spip) return null;
    const items = spip.items || [];
    const summary = spip.summary || {};
    const total_items = spip.total_items || 0;

    const gapData = Object.entries(summary).map(([key, count]) => ({
      name: GAP_LABELS[key] || key,
      value: count,
      fill: GAP_COLORS[key] || '#94a3b8',
    }));

    let filtered = spipFilter === 'all' ? items : items.filter(i => i.gap_type === spipFilter);
    if (search) {
      // Global search — name + part_number + aliases (case-insensitive
      // substring). Mirrors the Inventory page behavior so users find an
      // item by ANY known reference (Tally LANGUAGENAME alias, customer's
      // SKU, brand part-no etc.).
      const s = search.toLowerCase().trim();
      filtered = filtered.filter(i =>
        (i.item_name || '').toLowerCase().includes(s)
        || (i.part_number || '').toLowerCase().includes(s)
        || (Array.isArray(i.aliases) && i.aliases.some(a => (a || '').toLowerCase().includes(s)))
      );
    }
    filtered = sortData(filtered, sortField, sortDir);

    return (
      <div className="space-y-6">
        {/* Summary badges */}
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-3">
          {Object.entries(summary).map(([key, count]) => (
            <div key={key} className="rounded-xl p-3 border" style={{ borderColor: GAP_COLORS[key] + '40', backgroundColor: GAP_COLORS[key] + '10' }} data-testid={`spip-stat-${key}`}>
              <div className="text-xs text-slate-500 mb-1">{GAP_LABELS[key] || key}</div>
              <div className="text-lg font-bold" style={{ color: GAP_COLORS[key] }}>{count}</div>
            </div>
          ))}
          <div className="rounded-xl p-3 border border-slate-200 bg-slate-50" data-testid="spip-stat-total">
            <div className="text-xs text-slate-500 mb-1">Total Items</div>
            <div className="text-lg font-bold text-slate-800">{total_items}</div>
          </div>
        </div>

        {/* Gap Distribution Chart */}
        <div className="bg-white rounded-xl border border-slate-200 p-4" data-testid="spip-chart">
          <h3 className="text-sm font-semibold text-slate-700 mb-3">Inventory Gap Distribution</h3>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={gapData} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis type="number" tick={{ fontSize: 11 }} />
              <YAxis type="category" dataKey="name" tick={{ fontSize: 11 }} width={100} />
              <Tooltip content={<CustomTooltip />} />
              <Bar dataKey="value" name="Items" radius={[0, 4, 4, 0]}>
                {gapData.map((entry, i) => <Cell key={i} fill={entry.fill} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Info banner — surfaces the analysis window so the user knows
            whether SPIP used the selected FY or fell back to a 12-month
            rolling window. Backend may auto-fall-back when the FY is
            partial (e.g. FY 26-27 mid-year has < 6 mo of data). */}
        <div className="bg-blue-50 border border-blue-100 rounded-xl p-3 flex items-start gap-2" data-testid="spip-info">
          <Info size={16} className="text-blue-500 mt-0.5 flex-shrink-0" />
          <div className="text-xs text-blue-700 leading-relaxed">
            <strong>SPIP Analysis</strong> compares Sales velocity vs Stock levels to identify inventory gaps.
            {spip.window?.window_type === 'rolling' && (
              <span className="block mt-1" data-testid="spip-window-note">
                Window: <strong>{spip.window.window_label}</strong>
                {spip.window.window_start && spip.window.window_end &&
                  <span className="text-blue-500"> ({spip.window.window_start} → {spip.window.window_end})</span>
                }
              </span>
            )}
            {spip.window?.window_type === 'fy' && (
              <span className="block mt-1">
                Window: <strong>FY {spip.window.window_label}</strong>
              </span>
            )}
          </div>
        </div>

        {/* Items Table */}
        <div className="bg-white rounded-xl border border-slate-200" data-testid="spip-table">
          <div className="p-4 border-b border-slate-100 flex flex-col sm:flex-row items-start sm:items-center gap-3">
            <h3 className="text-sm font-semibold text-slate-700">Item Details</h3>
            <div className="flex items-center gap-2 ml-auto flex-wrap">
              <div className="relative">
                <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400" />
                <input
                  value={search} onChange={e => setSearch(e.target.value)}
                  placeholder="Search name / part-no / alias"
                  className="pl-8 pr-3 py-1.5 text-xs border border-slate-200 rounded-lg w-56 focus:outline-none focus:ring-1 focus:ring-blue-500"
                  data-testid="spip-search"
                />
              </div>
              <select value={spipFilter} onChange={e => setSpipFilter(e.target.value)} className="text-xs border border-slate-200 rounded-lg px-2 py-1.5" data-testid="spip-filter">
                <option value="all">All Types</option>
                <option value="out_of_stock">Out of Stock</option>
                <option value="understocked">Understocked</option>
                <option value="dead_stock">Dead Stock</option>
                <option value="overstocked">Overstocked</option>
                <option value="balanced">Balanced</option>
                <option value="no_movement">No Movement (12m)</option>
              </select>
            </div>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead className="bg-slate-50 border-b border-slate-100">
                <tr>
                  <SortTh field="item_name" label="Item" />
                  <th className="px-3 py-2.5 text-left text-xs font-semibold text-slate-600">Gap Type</th>
                  <SortTh field="stock_qty" label="Stock Qty" />
                  <SortTh field="qty_sold" label="Qty Sold" />
                  <SortTh field="monthly_avg_sales" label="Monthly Avg" />
                  <SortTh field="months_of_stock" label="Months Stock" />
                  <SortTh field="revenue" label="Revenue" />
                </tr>
              </thead>
              <tbody>
                {filtered
                  .slice((spipPage - 1) * PAGE_SIZE, spipPage * PAGE_SIZE)
                  .map((item, i) => (
                  <tr key={i} className="border-b border-slate-50 hover:bg-slate-25" data-testid={`spip-row-${i}`}>
                    <td className="px-3 py-2.5 font-medium text-slate-800 max-w-[200px] truncate">{item.item_name}</td>
                    <td className="px-3 py-2.5">
                      <span
                        className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold"
                        style={{ backgroundColor: (GAP_COLORS[item.gap_type] || '#94a3b8') + '20', color: GAP_COLORS[item.gap_type] || '#64748b' }}
                      >
                        {GAP_LABELS[item.gap_type] || item.gap_type}
                      </span>
                    </td>
                    <td className="px-3 py-2.5 text-slate-600">{item.stock_qty}</td>
                    <td className="px-3 py-2.5 text-slate-600">{item.qty_sold}</td>
                    <td className="px-3 py-2.5 text-slate-600">{item.monthly_avg_sales}</td>
                    <td className="px-3 py-2.5 text-slate-600">{item.months_of_stock >= 999 ? '\u221E' : item.months_of_stock}</td>
                    <td className="px-3 py-2.5 font-medium text-slate-800">{fmt(item.revenue)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pager
            page={spipPage}
            total={filtered.length}
            pageSize={PAGE_SIZE}
            onPage={setSpipPage}
            testIdPrefix="spip-pager"
          />
        </div>
      </div>
    );
  };

  // ============ CONCENTRATION RISK TAB ============
  const renderConcentration = () => {
    if (!concentration) return null;
    const customers = concentration.customers || [];
    const s = concentration.summary || {};
    const risk_level = concentration.risk_level || 'no_data';
    const riskStyle = RISK_COLORS[risk_level] || RISK_COLORS.no_data;

    // Build Pareto chart data
    const paretoData = customers.slice(0, 30).map(c => ({
      name: (c.customer_name || '').length > 18 ? (c.customer_name || '').slice(0, 16) + '...' : (c.customer_name || ''),
      revenue: c.revenue,
      cumulative: c.cumulative_pct,
    }));

    return (
      <div className="space-y-6">
        {/* Risk Level Banner */}
        <div className={`${riskStyle.bg} ${riskStyle.border} border rounded-xl p-4 flex items-center gap-4`} data-testid="risk-banner">
          <AlertTriangle size={28} className={riskStyle.text} />
          <div>
            <div className={`text-lg font-bold ${riskStyle.text}`}>Concentration Risk: {riskStyle.label}</div>
            <div className="text-xs text-slate-600 mt-0.5">
              Top 5 customers contribute {s.top5_pct}% of total revenue ({fmt(s.top5_revenue)})
            </div>
          </div>
        </div>

        {/* Summary cards */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <StatCard icon={Users} label="Total Customers" value={s.total_customers} sub={`Total: ${fmt(s.total_revenue)}`} testId="stat-total-customers" />
          <StatCard icon={Target} label="Top 5 Share" value={`${s.top5_pct}%`} sub={fmt(s.top5_revenue)} color={s.top5_pct > 60 ? 'bg-red-50' : 'bg-slate-50'} textColor={s.top5_pct > 60 ? 'text-red-700' : 'text-slate-900'} testId="stat-top5" />
          <StatCard icon={BarChart3} label="Top 10 Share" value={`${s.top10_pct}%`} sub={fmt(s.top10_revenue)} color={s.top10_pct > 80 ? 'bg-orange-50' : 'bg-slate-50'} textColor={s.top10_pct > 80 ? 'text-orange-700' : 'text-slate-900'} testId="stat-top10" />
          <StatCard icon={Activity} label="Top 20% Share" value={`${s.top20pct_pct}%`} sub="Pareto indicator" color={s.top20pct_pct > 80 ? 'bg-yellow-50' : 'bg-slate-50'} testId="stat-top20" />
        </div>

        {/* Pareto Chart */}
        <div className="bg-white rounded-xl border border-slate-200 p-4" data-testid="pareto-chart">
          <h3 className="text-sm font-semibold text-slate-700 mb-3">Revenue Concentration (Pareto)</h3>
          <ResponsiveContainer width="100%" height={320}>
            <ComposedChart data={paretoData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis dataKey="name" tick={{ fontSize: 9 }} angle={-40} textAnchor="end" height={70} />
              <YAxis yAxisId="left" tick={{ fontSize: 10 }} tickFormatter={v => fmt(v)} />
              <YAxis yAxisId="right" orientation="right" tick={{ fontSize: 10 }} domain={[0, 100]} tickFormatter={v => `${v}%`} />
              <Tooltip content={<CustomTooltip />} />
              <Legend />
              <Bar yAxisId="left" dataKey="revenue" fill="#2563EB" name="Revenue" radius={[3, 3, 0, 0]} />
              <Line yAxisId="right" type="monotone" dataKey="cumulative" stroke="#EF4444" strokeWidth={2} dot={{ fill: '#EF4444', r: 3 }} name="Cumulative %" />
              <ReferenceLine yAxisId="right" y={80} stroke="#F59E0B" strokeDasharray="5 5" label={{ value: '80%', position: 'left', fontSize: 10, fill: '#F59E0B' }} />
            </ComposedChart>
          </ResponsiveContainer>
        </div>

        {/* Customer Table */}
        <div className="bg-white rounded-xl border border-slate-200" data-testid="concentration-table">
          <div className="p-4 border-b border-slate-100">
            <h3 className="text-sm font-semibold text-slate-700">Customer Revenue Ranking</h3>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead className="bg-slate-50 border-b border-slate-100">
                <tr>
                  <th className="px-3 py-2.5 text-left text-xs font-semibold text-slate-600 w-12">#</th>
                  <SortTh field="customer_name" label="Customer" />
                  <SortTh field="revenue" label="Revenue" />
                  <SortTh field="pct_of_total" label="% of Total" />
                  <SortTh field="cumulative_pct" label="Cumulative %" />
                </tr>
              </thead>
              <tbody>
                {sortData(customers, sortField, sortDir).map((c, i) => (
                  <tr key={i} className={`border-b border-slate-50 hover:bg-slate-25 ${c.rank <= 5 ? 'bg-red-50/30' : ''}`} data-testid={`concentration-row-${i}`}>
                    <td className="px-3 py-2.5 text-slate-500 font-medium">{c.rank}</td>
                    <td className="px-3 py-2.5 font-medium text-slate-800 max-w-[220px] truncate">{c.customer_name}</td>
                    <td className="px-3 py-2.5 font-semibold text-slate-800">{fmt(c.revenue)}</td>
                    <td className="px-3 py-2.5">
                      <div className="flex items-center gap-2">
                        <div className="w-16 h-1.5 bg-slate-100 rounded-full overflow-hidden">
                          <div className="h-full bg-blue-500 rounded-full" style={{ width: `${Math.min(c.pct_of_total, 100)}%` }} />
                        </div>
                        <span className="text-slate-600">{c.pct_of_total}%</span>
                      </div>
                    </td>
                    <td className="px-3 py-2.5">
                      <span className={`font-medium ${c.cumulative_pct <= 80 ? 'text-red-600' : 'text-slate-500'}`}>
                        {c.cumulative_pct}%
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="space-y-4" data-testid="insider-result-page">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-slate-900" data-testid="insider-title">Insider Result</h1>
          <p className="text-xs text-slate-500 mt-0.5">Advanced business intelligence analytics</p>
        </div>
      </div>

      {/* Tab Navigation */}
      <div className="flex items-center gap-1 bg-white rounded-xl border border-slate-200 p-1 overflow-x-auto" data-testid="insider-tabs">
        {TABS.map(tab => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => { setActiveTab(tab.id); setSearch(''); setSortField(''); }}
              data-testid={`tab-${tab.id}`}
              className={`flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-medium whitespace-nowrap transition-colors ${
                isActive ? 'bg-[#2563EB] text-white shadow-sm' : 'text-slate-600 hover:bg-slate-50'
              }`}
            >
              <Icon size={14} />
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* Content */}
      {loading ? (
        <div className="flex items-center justify-center h-[40vh]" data-testid="insider-loading">
          <div className="text-center">
            <div className="w-8 h-8 border-2 border-slate-200 border-t-blue-600 rounded-full animate-spin mx-auto mb-3" />
            <p className="text-sm text-slate-500">Loading analytics...</p>
          </div>
        </div>
      ) : (
        <>
          {activeTab === 'lifecycle' && renderLifecycle()}
          {activeTab === 'forecast' && renderForecast()}
          {activeTab === 'spip' && renderSpip()}
          {activeTab === 'concentration' && renderConcentration()}
        </>
      )}
    </div>
  );
};

export default InsiderResult;
