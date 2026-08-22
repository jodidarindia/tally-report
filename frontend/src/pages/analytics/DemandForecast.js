// Demand Forecast tab (Analytics menu) — iter-155.
//
// Access control: admin-only. Backend enforces at /api/analytics/forecast/*
// (returns 403 for other roles); the frontend just renders a friendly
// notice if the API refuses. Every request carries the X-Company-ID
// header set by the shared axios interceptor.
import React, { useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import { Loader2, Download, TrendingUp, AlertTriangle, PackageX, Sparkles } from 'lucide-react';
import { toast } from 'sonner';
import { getErpLabel } from '../../utils/agentSource';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const NUM = (v, opts = {}) => Number(v || 0).toLocaleString('en-IN', { maximumFractionDigits: 0, ...opts });

const DemandForecast = () => {
  const [horizon, setHorizon] = useState(3);
  const [festival, setFestival] = useState(false);
  const [growth, setGrowth] = useState(0);
  const [loading, setLoading] = useState(true);
  const [overview, setOverview] = useState(null);
  const [season, setSeason] = useState(null);
  const [cohort, setCohort] = useState(null);
  const [error, setError] = useState('');

  const load = async () => {
    setLoading(true);
    setError('');
    try {
      const params = { horizon_months: horizon, festival_lens: festival, growth_pct: growth };
      const [ov, se, co] = await Promise.all([
        axios.get(`${API}/analytics/forecast/overview`, { params }),
        axios.get(`${API}/analytics/forecast/season`, { params: { top: 25, horizon_months: horizon, festival_lens: festival } }),
        axios.get(`${API}/analytics/forecast/cohort`, { params: { top_customers: 15, horizon_months: horizon } }),
      ]);
      if (ov.data?.success) setOverview(ov.data.data);
      if (se.data?.success) setSeason(se.data.data);
      if (co.data?.success) setCohort(co.data.data);
    } catch (e) {
      const detail = e?.response?.data?.detail || e?.response?.data?.error || e.message;
      if (e?.response?.status === 403) {
        setError('This tab is available to tenant admins only.');
      } else {
        setError(detail || 'Failed to load forecast');
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, [horizon, festival, growth]);

  const exportCsv = async () => {
    try {
      const r = await axios.get(`${API}/analytics/forecast/export`, {
        params: { horizon_months: horizon, festival_lens: festival, growth_pct: growth },
        responseType: 'blob',
      });
      const url = window.URL.createObjectURL(new Blob([r.data]));
      const a = document.createElement('a');
      a.href = url;
      a.download = `forecast_${new Date().toISOString().slice(0, 10)}.csv`;
      a.click();
      window.URL.revokeObjectURL(url);
      toast.success('CSV downloaded');
    } catch (_) {
      toast.error('Export failed');
    }
  };

  const heatmapMax = useMemo(() => {
    if (!season?.rows) return 0;
    let mx = 0;
    for (const r of season.rows) {
      for (const v of [...(r.past_12 || []), ...(r.forecast || [])]) mx = Math.max(mx, v);
    }
    return mx || 1;
  }, [season]);

  const heatColour = (v) => {
    if (!v) return '#F1F5F9';
    const t = Math.min(1, v / heatmapMax);
    const r = Math.round(220 + (37 - 220) * t);
    const g = Math.round(240 + (99 - 240) * t);
    const b = Math.round(238 + (235 - 238) * t);
    return `rgb(${r},${g},${b})`;
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24">
        <Loader2 className="animate-spin text-slate-400" size={28} />
        <span className="ml-3 text-slate-500">Crunching {getErpLabel()} history — one moment…</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6 bg-rose-50 border border-rose-200 rounded-lg text-rose-800">
        <div className="font-semibold mb-1 flex items-center gap-2">
          <AlertTriangle size={18} /> {error}
        </div>
      </div>
    );
  }

  const kpi = overview?.kpi || {};
  const buyList = overview?.buy_list || [];

  return (
    <div className="space-y-6" data-testid="demand-forecast-tab">
      {/* Controls */}
      <div className="flex flex-wrap items-end gap-4 p-4 bg-white rounded-lg border border-slate-200">
        <div>
          <label className="block text-xs uppercase tracking-wide text-slate-500 mb-1">Horizon</label>
          <select value={horizon} onChange={(e) => setHorizon(Number(e.target.value))}
                  className="px-3 py-2 border border-slate-200 rounded-md text-sm"
                  data-testid="forecast-horizon-select">
            {[1, 2, 3, 6, 9, 12].map((h) => (
              <option key={h} value={h}>Next {h} month{h > 1 ? 's' : ''}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-xs uppercase tracking-wide text-slate-500 mb-1">Growth (%)</label>
          <input type="number" value={growth}
                 onChange={(e) => setGrowth(Number(e.target.value))}
                 step={5} min={-50} max={100}
                 className="px-3 py-2 border border-slate-200 rounded-md text-sm w-24"
                 data-testid="forecast-growth-input" />
        </div>
        <label className="inline-flex items-center gap-2 text-sm text-slate-700 cursor-pointer">
          <input type="checkbox" checked={festival}
                 onChange={(e) => setFestival(e.target.checked)}
                 data-testid="forecast-festival-toggle" />
          Apply festival + monsoon lens
        </label>
        <div className="ml-auto flex items-center gap-2">
          <button onClick={load}
                  className="px-3 py-2 text-sm border border-slate-200 rounded-md hover:bg-slate-50"
                  data-testid="forecast-refresh-btn">Refresh</button>
          <button onClick={exportCsv}
                  className="px-3 py-2 text-sm bg-blue-600 text-white rounded-md hover:bg-blue-700 inline-flex items-center gap-1.5"
                  data-testid="forecast-export-btn">
            <Download size={14} /> Export CSV
          </button>
        </div>
      </div>

      {/* KPI band */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <KpiCard icon={<TrendingUp size={16} />} label="SKUs analysed" value={NUM(kpi.total_skus_analysed)}
                 tint="bg-slate-50 text-slate-700" />
        <KpiCard icon={<Sparkles size={16} />} label="Projected units" value={NUM(kpi.projected_units)}
                 tint="bg-blue-50 text-blue-800" />
        <KpiCard icon={<Sparkles size={16} />} label="Projected revenue"
                 value={`Rs.${NUM(kpi.projected_revenue)}`} tint="bg-emerald-50 text-emerald-800" />
        <KpiCard icon={<AlertTriangle size={16} />} label="Stockout risk"
                 value={NUM(kpi.stockout_skus) + ' SKUs'} tint="bg-amber-50 text-amber-800" />
        <KpiCard icon={<PackageX size={16} />} label="Excess stock"
                 value={NUM(kpi.excess_skus) + ' SKUs'} tint="bg-rose-50 text-rose-800" />
      </div>

      <div className="text-xs text-slate-500">
        FYs used: <span className="font-semibold">{(kpi.fys_used || []).join(', ') || 'none'}</span>
        {festival && kpi.festival_lens && <span className="ml-3">· Festival lens ON</span>}
        {growth !== 0 && <span className="ml-3">· What-if growth {growth > 0 ? '+' : ''}{growth}%</span>}
      </div>

      {/* Consolidated Buy List */}
      <div className="bg-white border border-slate-200 rounded-lg overflow-hidden">
        <div className="px-4 py-3 border-b border-slate-100 flex items-center justify-between">
          <h3 className="text-sm font-semibold text-slate-800">Consolidated Buy List <span className="text-xs text-slate-400">(top {buyList.length})</span></h3>
        </div>
        <div className="overflow-x-auto max-h-[440px]">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 sticky top-0">
              <tr className="text-xs uppercase text-slate-500">
                <Th>Item</Th>
                <Th>Stock group</Th>
                <Th className="text-right">Current</Th>
                <Th className="text-right">Forecast</Th>
                <Th className="text-right">Range (low – high)</Th>
                <Th className="text-right">Reorder pt</Th>
                <Th className="text-right">Confidence</Th>
                <Th>Buy by</Th>
                <Th>Class</Th>
              </tr>
            </thead>
            <tbody>
              {buyList.map((r, i) => (
                <tr key={r.item_id} className={`border-t border-slate-100 ${r.stockout_risk ? 'bg-amber-50/30' : ''}`}
                    data-testid={`forecast-buy-row-${i}`}>
                  <Td className="max-w-[260px] truncate" title={r.item_name}>{r.item_name}</Td>
                  <Td className="text-xs text-slate-500 max-w-[140px] truncate">{r.stock_group}</Td>
                  <Td className="text-right">{NUM(r.current_stock)}</Td>
                  <Td className="text-right font-semibold">{NUM(r.forecast_units, { maximumFractionDigits: 1 })}</Td>
                  <Td className="text-right text-xs text-slate-500">
                    {NUM(r.forecast_low, { maximumFractionDigits: 1 })} – {NUM(r.forecast_high, { maximumFractionDigits: 1 })}
                  </Td>
                  <Td className="text-right">{NUM(r.reorder_point, { maximumFractionDigits: 1 })}</Td>
                  <Td className="text-right"><ConfPill pct={r.confidence_pct} /></Td>
                  <Td className={`text-xs ${r.buy_by ? 'text-rose-700 font-semibold' : 'text-slate-400'}`}>{r.buy_by || '—'}</Td>
                  <Td><VelocityPill cls={r.velocity_class} /></Td>
                </tr>
              ))}
              {!buyList.length && (
                <tr><td colSpan={9} className="p-6 text-center text-slate-400 text-sm">
                  Nothing to reorder in the next {horizon} month(s). All SKUs adequately stocked.
                </td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Season heatmap */}
      {season?.rows?.length > 0 && (
        <div className="bg-white border border-slate-200 rounded-lg p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold text-slate-800">
              Demand by month — past 12 + next {horizon}
              <span className="ml-2 text-xs text-slate-400">
                (top {season.rows.length} SKUs · lighter = low, deeper blue = high)
              </span>
            </h3>
          </div>
          <div className="overflow-x-auto">
            <table className="w-max text-xs">
              <thead>
                <tr>
                  <th className="text-left px-2 py-1 text-slate-500 w-[220px]">SKU</th>
                  {[...(season.rows[0].past_12 || []), ...(season.rows[0].forecast || [])].map((_, i) => {
                    const total = (season.rows[0].past_12?.length || 0);
                    const isFcst = i >= total;
                    return (
                      <th key={i} className={`px-1 py-1 ${isFcst ? 'text-blue-600 font-semibold' : 'text-slate-400'}`}>
                        {isFcst ? `+${i - total + 1}` : `-${total - i}`}
                      </th>
                    );
                  })}
                </tr>
              </thead>
              <tbody>
                {season.rows.map((r) => (
                  <tr key={r.item_id}>
                    <td className="px-2 py-1 truncate max-w-[220px]" title={r.item_name}>{r.item_name}</td>
                    {[...(r.past_12 || []), ...(r.forecast || [])].map((v, i) => (
                      <td key={i} className="w-6 h-6 text-center align-middle"
                          style={{ background: heatColour(v) }}
                          title={`${v.toFixed(1)} units`}>
                        &nbsp;
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Cohort demand */}
      {cohort?.rows?.length > 0 && (
        <div className="bg-white border border-slate-200 rounded-lg p-4">
          <h3 className="text-sm font-semibold text-slate-800 mb-3">
            Top customers — projected next-horizon demand
            <span className="ml-2 text-xs text-slate-400">
              (same months last year → {cohort.target_months?.join(', ')})
            </span>
          </h3>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-xs uppercase text-slate-500 border-b border-slate-100">
                <Th>Customer</Th>
                <Th className="text-right">Lifetime vouchers</Th>
                <Th className="text-right">Lifetime revenue</Th>
                <Th className="text-right">Projected units (next {horizon}mo)</Th>
                <Th className="text-right">Projected revenue</Th>
              </tr>
            </thead>
            <tbody>
              {cohort.rows.map((r, i) => (
                <tr key={i} className="border-t border-slate-100" data-testid={`forecast-cohort-row-${i}`}>
                  <Td className="max-w-[280px] truncate" title={r.party_name}>{r.party_name}</Td>
                  <Td className="text-right">{NUM(r.lifetime_vouchers)}</Td>
                  <Td className="text-right text-slate-500">Rs.{NUM(r.lifetime_revenue)}</Td>
                  <Td className="text-right font-semibold">{NUM(r.projected_units_next_horizon, { maximumFractionDigits: 1 })}</Td>
                  <Td className="text-right text-emerald-700 font-semibold">Rs.{NUM(r.projected_revenue_next_horizon)}</Td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <p className="text-xs text-slate-400 text-center pt-4">
        Analysed only your own SKUs across all synced FYs. Every request scoped to tenant + company. Admin access only.
      </p>
    </div>
  );
};

const KpiCard = ({ icon, label, value, tint }) => (
  <div className={`p-3 rounded-lg ${tint}`}>
    <div className="flex items-center gap-1.5 text-xs uppercase font-semibold opacity-80">{icon} {label}</div>
    <div className="text-xl font-bold mt-1">{value}</div>
  </div>
);

const Th = ({ children, className = '' }) => <th className={`px-3 py-2 text-left font-semibold ${className}`}>{children}</th>;
const Td = ({ children, className = '', title }) => <td className={`px-3 py-2 ${className}`} title={title}>{children}</td>;

const VelocityPill = ({ cls }) => {
  const map = { A: 'bg-emerald-100 text-emerald-800', B: 'bg-blue-100 text-blue-800',
                C: 'bg-amber-100 text-amber-800', new: 'bg-slate-100 text-slate-600' };
  return <span className={`px-1.5 py-0.5 rounded text-[10px] font-semibold ${map[cls] || map.new}`}>{cls}</span>;
};

const ConfPill = ({ pct }) => {
  const color = pct >= 75 ? 'bg-emerald-500' : pct >= 50 ? 'bg-blue-500' : 'bg-amber-500';
  return (
    <span className="inline-flex items-center gap-1 text-xs">
      <span className={`inline-block w-2 h-2 rounded-full ${color}`} />
      {pct}%
    </span>
  );
};

export default DemandForecast;
