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
};

const GAP_LABELS = {
  out_of_stock: 'Out of Stock',
  understocked: 'Understocked',
  dead_stock: 'Dead Stock',
  overstocked: 'Overstocked',
  balanced: 'Balanced',
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

const StatCard = ({ icon: Icon, label, value, sub, color = 'bg-slate-50', textColor = 'text-slate-900', testId }) => (
  <div className={`${color} rounded-xl p-4 border border-slate-100`} data-testid={testId}>
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
      toast.error('Failed to load insights data');
    } finally {
      setLoading(false);
    }
  }, [activeTab, selectedFY]);

  useEffect(() => { fetchData(); }, [fetchData]);

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
        {/* Summary cards */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <StatCard icon={UserCheck} label="Active Customers" value={summary.active_count} sub={`Revenue: ${fmt(summary.active_revenue)}`} color="bg-emerald-50" textColor="text-emerald-700" testId="stat-active" />
          <StatCard icon={UserMinus} label="Inactive (90+ days)" value={summary.inactive_count} sub={`Revenue: ${fmt(summary.inactive_revenue)}`} color="bg-amber-50" textColor="text-amber-700" testId="stat-inactive" />
          <StatCard icon={UserX} label="Lost (180+ days)" value={summary.lost_count} sub={`Revenue: ${fmt(summary.lost_revenue)}`} color="bg-red-50" textColor="text-red-700" testId="stat-lost" />
          <StatCard icon={Users} label="Total Customers" value={allCustomers.length} sub="All time" color="bg-blue-50" textColor="text-blue-700" testId="stat-total" />
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
                <option value="all">All Status</option>
                <option value="active">Active</option>
                <option value="inactive">Inactive</option>
                <option value="lost">Lost</option>
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
                {filtered.slice(0, 100).map((c, i) => (
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
          {filtered.length > 100 && (
            <div className="p-3 text-center text-xs text-slate-400">Showing 100 of {filtered.length} customers</div>
          )}
        </div>
      </div>
    );
  };

  // ============ FORECAST TAB ============
  const renderForecast = () => {
    if (!forecast) return null;
    const { timeline, forecasts, yoy, summary: s } = forecast;

    const chartData = [
      ...timeline.map(t => ({ month: t.month, revenue: t.revenue, type: 'actual' })),
      ...forecasts.map(f => ({ month: f.month, forecast: f.forecast_revenue, type: 'forecast' })),
    ];

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
          <h3 className="text-sm font-semibold text-slate-700 mb-3">Revenue Trend & Forecast</h3>
          <ResponsiveContainer width="100%" height={320}>
            <ComposedChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis dataKey="month" tick={{ fontSize: 10 }} angle={-35} textAnchor="end" height={50} />
              <YAxis tick={{ fontSize: 10 }} tickFormatter={v => fmt(v)} />
              <Tooltip content={<CustomTooltip />} />
              <Legend />
              <Bar dataKey="revenue" fill="#2563EB" name="Actual Revenue" radius={[3, 3, 0, 0]} />
              <Line type="monotone" dataKey="forecast" stroke="#8B5CF6" strokeWidth={2} strokeDasharray="6 3" dot={{ fill: '#8B5CF6', r: 4 }} name="Forecast" />
            </ComposedChart>
          </ResponsiveContainer>
        </div>

        {/* YoY Comparison */}
        <div className="bg-white rounded-xl border border-slate-200 p-4" data-testid="yoy-chart">
          <h3 className="text-sm font-semibold text-slate-700 mb-3">Year-over-Year Comparison</h3>
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={yoy}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis dataKey="year" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 10 }} tickFormatter={v => fmt(v)} />
              <Tooltip content={<CustomTooltip />} />
              <Bar dataKey="revenue" fill="#0EA5E9" name="Revenue" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

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
    const { items, summary, total_items } = spip;

    const gapData = Object.entries(summary).map(([key, count]) => ({
      name: GAP_LABELS[key] || key,
      value: count,
      fill: GAP_COLORS[key] || '#94a3b8',
    }));

    let filtered = spipFilter === 'all' ? items : items.filter(i => i.gap_type === spipFilter);
    if (search) filtered = filtered.filter(i => i.item_name.toLowerCase().includes(search.toLowerCase()));
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

        {/* Info banner */}
        <div className="bg-blue-50 border border-blue-100 rounded-xl p-3 flex items-start gap-2" data-testid="spip-info">
          <Info size={16} className="text-blue-500 mt-0.5 flex-shrink-0" />
          <div className="text-xs text-blue-700">
            <strong>SPIP Analysis</strong> compares Sales velocity vs Purchase/Stock levels to identify inventory gaps.
            Items are classified by months of remaining stock relative to average monthly sales rate.
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
                  placeholder="Search item..."
                  className="pl-8 pr-3 py-1.5 text-xs border border-slate-200 rounded-lg w-48 focus:outline-none focus:ring-1 focus:ring-blue-500"
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
                {filtered.slice(0, 100).map((item, i) => (
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
          {filtered.length > 100 && (
            <div className="p-3 text-center text-xs text-slate-400">Showing 100 of {filtered.length} items</div>
          )}
        </div>
      </div>
    );
  };

  // ============ CONCENTRATION RISK TAB ============
  const renderConcentration = () => {
    if (!concentration) return null;
    const { customers, summary: s, risk_level } = concentration;
    const riskStyle = RISK_COLORS[risk_level] || RISK_COLORS.no_data;

    // Build Pareto chart data
    const paretoData = customers.slice(0, 30).map(c => ({
      name: c.customer_name.length > 18 ? c.customer_name.slice(0, 16) + '...' : c.customer_name,
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
