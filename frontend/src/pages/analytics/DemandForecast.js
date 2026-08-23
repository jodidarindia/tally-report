// Demand Forecast tab (Analytics menu) — iter-155.
//
// Access control: admin-only. Backend enforces at /api/analytics/forecast/*
// (returns 403 for other roles); the frontend just renders a friendly
// notice if the API refuses. Every request carries the X-Company-ID
// header set by the shared axios interceptor.
import React, { useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import { Loader2, Download, TrendingUp, AlertTriangle, PackageX, Sparkles, X, ChevronRight } from 'lucide-react';
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
  // Wave 2 — per-SKU deep dive
  const [deepDive, setDeepDive] = useState(null); // { loading, data, error }

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

  const openDeepDive = async (itemId) => {
    setDeepDive({ loading: true, data: null, error: '' });
    try {
      const r = await axios.get(`${API}/analytics/forecast/sku/${encodeURIComponent(itemId)}`, {
        params: { horizon_months: horizon, festival_lens: festival, growth_pct: growth },
      });
      if (r.data?.success) {
        setDeepDive({ loading: false, data: r.data.data, error: '' });
      } else {
        setDeepDive({ loading: false, data: null, error: r.data?.error || 'Failed to load SKU details' });
      }
    } catch (e) {
      setDeepDive({ loading: false, data: null,
        error: e?.response?.data?.error || e?.response?.data?.detail || e.message });
    }
  };
  const closeDeepDive = () => setDeepDive(null);

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
                <tr key={r.item_id}
                    className={`border-t border-slate-100 cursor-pointer hover:bg-blue-50/40 transition-colors ${r.stockout_risk ? 'bg-amber-50/30' : ''}`}
                    onClick={() => openDeepDive(r.item_id)}
                    data-testid={`forecast-buy-row-${i}`}>
                  <Td className="max-w-[260px] truncate" title={r.item_name}>
                    <span className="inline-flex items-center gap-1">
                      <ChevronRight size={12} className="text-slate-400" />
                      {r.item_name}
                    </span>
                  </Td>
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

      {deepDive && (
        <DeepDiveModal payload={deepDive} onClose={closeDeepDive} horizon={horizon} />
      )}
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

/* ─── Wave 2: Per-SKU Deep Dive Modal ────────────────────────────────── */
const DeepDiveModal = ({ payload, onClose, horizon }) => {
  const { loading, data, error } = payload;
  return (
    <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-sm flex items-start md:items-center justify-center p-4 overflow-y-auto"
         onClick={onClose} data-testid="forecast-deepdive-modal">
      <div className="bg-white rounded-lg shadow-2xl max-w-5xl w-full my-8 border border-slate-200"
           onClick={(e) => e.stopPropagation()}>
        <div className="px-5 py-3 border-b border-slate-100 flex items-center justify-between">
          <h3 className="text-sm font-semibold text-slate-800">Per-SKU Deep Dive</h3>
          <button onClick={onClose} className="p-1 rounded hover:bg-slate-100"
                  data-testid="forecast-deepdive-close">
            <X size={16} className="text-slate-500" />
          </button>
        </div>
        <div className="p-5">
          {loading && (
            <div className="flex items-center justify-center py-16">
              <Loader2 className="animate-spin text-slate-400" size={24} />
              <span className="ml-3 text-slate-500 text-sm">Loading details…</span>
            </div>
          )}
          {error && !loading && (
            <div className="p-4 bg-rose-50 border border-rose-200 rounded text-rose-800 text-sm">
              {error}
            </div>
          )}
          {data && !loading && (
            <DeepDiveContent data={data} horizon={horizon} />
          )}
        </div>
      </div>
    </div>
  );
};

const DeepDiveContent = ({ data, horizon }) => {
  const sku = data.sku || {};
  const pastLabels = data.past_month_labels || [];
  const fcstLabels = data.forecast_month_labels || [];
  const past = sku.past_12 || [];
  const fcst = sku.monthly_forecast || [];
  const low = sku.monthly_forecast_low || [];
  const high = sku.monthly_forecast_high || [];

  // Chart dimensions
  const W = 780, H = 220, PAD_L = 40, PAD_R = 20, PAD_T = 16, PAD_B = 30;
  const totalMonths = past.length + fcst.length;
  const allVals = [...past, ...fcst, ...high];
  const yMax = Math.max(1, ...allVals) * 1.15;

  const xAt = (i) => PAD_L + (i * (W - PAD_L - PAD_R)) / Math.max(1, totalMonths - 1);
  const yAt = (v) => H - PAD_B - ((v || 0) / yMax) * (H - PAD_T - PAD_B);

  // Build path strings
  const pastPath = past.map((v, i) => `${i === 0 ? 'M' : 'L'}${xAt(i)},${yAt(v)}`).join(' ');
  const fcstStart = past.length; // first forecast column
  // Connect the last actual to the first forecast for visual continuity
  const fcstPath = fcst.length
    ? `M${xAt(fcstStart - 1)},${yAt(past[past.length - 1] || 0)} ` +
      fcst.map((v, i) => `L${xAt(fcstStart + i)},${yAt(v)}`).join(' ')
    : '';
  // P25 / P75 band as a closed polygon
  const bandTop = low.map((_, i) => `${xAt(fcstStart + i)},${yAt(high[i] || 0)}`).join(' ');
  const bandBot = low.map((_, i) => `${xAt(fcstStart + low.length - 1 - i)},${yAt(low[low.length - 1 - i] || 0)}`).join(' ');
  const bandPoly = fcst.length ? `${bandTop} ${bandBot}` : '';

  return (
    <div className="space-y-5" data-testid="forecast-deepdive-content">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="text-lg font-semibold text-slate-800">{sku.item_name}</div>
          <div className="text-xs text-slate-500 mt-0.5">
            {sku.stock_group ? <>Group: <span className="font-medium">{sku.stock_group}</span> · </> : null}
            History: {sku.history_months || 0} mo ({sku.non_zero_months || 0} with sales) ·
            Velocity: <VelocityPill cls={sku.velocity_class} />
          </div>
        </div>
        <div className="flex flex-wrap gap-2 text-xs">
          <Chip label="Current stock" value={NUM(sku.current_stock)} tint="bg-slate-100 text-slate-700" />
          <Chip label={`Forecast (${horizon}mo)`} value={NUM(sku.forecast_units, { maximumFractionDigits: 1 })}
                tint="bg-blue-100 text-blue-800" />
          <Chip label="Reorder point" value={NUM(sku.reorder_point, { maximumFractionDigits: 1 })}
                tint="bg-amber-100 text-amber-800" />
          <Chip label="Safety stock" value={NUM(sku.safety_stock, { maximumFractionDigits: 1 })}
                tint="bg-slate-100 text-slate-700" />
          <Chip label="Confidence" value={`${sku.confidence_pct || 0}%`} tint="bg-emerald-100 text-emerald-800" />
        </div>
      </div>

      {sku.buy_by && (
        <div className="p-3 bg-rose-50 border border-rose-200 rounded text-rose-800 text-sm">
          <AlertTriangle size={14} className="inline mr-1.5 -mt-0.5" />
          Stockout risk — reorder by <span className="font-semibold">{sku.buy_by}</span>
        </div>
      )}

      {/* SVG chart */}
      <div className="border border-slate-200 rounded bg-slate-50/60 p-3">
        <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto" data-testid="forecast-deepdive-chart">
          {/* Y-axis grid */}
          {[0, 0.25, 0.5, 0.75, 1].map((f) => {
            const y = yAt(yMax * f);
            return (
              <g key={f}>
                <line x1={PAD_L} y1={y} x2={W - PAD_R} y2={y}
                      stroke="#E2E8F0" strokeWidth="1" strokeDasharray="2 4" />
                <text x={PAD_L - 6} y={y + 3} fontSize="9" fill="#94A3B8" textAnchor="end">
                  {Math.round(yMax * f)}
                </text>
              </g>
            );
          })}

          {/* Forecast region divider */}
          {fcst.length > 0 && (
            <line x1={xAt(fcstStart - 0.5)} y1={PAD_T} x2={xAt(fcstStart - 0.5)} y2={H - PAD_B}
                  stroke="#CBD5E1" strokeWidth="1" strokeDasharray="3 3" />
          )}

          {/* Festival month backgrounds (past + future) */}
          {pastLabels.map((lbl, i) =>
            lbl.festival_tag ? (
              <rect key={`fp-${i}`} x={xAt(i) - 10} y={PAD_T} width="20" height={H - PAD_T - PAD_B}
                    fill="#FDE68A" opacity="0.35" />
            ) : null,
          )}
          {fcstLabels.map((lbl, i) =>
            lbl.festival_tag ? (
              <rect key={`ff-${i}`} x={xAt(fcstStart + i) - 10} y={PAD_T} width="20" height={H - PAD_T - PAD_B}
                    fill="#FDE68A" opacity="0.55" />
            ) : null,
          )}

          {/* Confidence band (P25 – P75) */}
          {bandPoly && (
            <polygon points={bandPoly} fill="#3B82F6" opacity="0.15" />
          )}

          {/* Past actuals line */}
          {pastPath && <path d={pastPath} stroke="#64748B" strokeWidth="1.75" fill="none" />}
          {past.map((v, i) => (
            <circle key={`p-${i}`} cx={xAt(i)} cy={yAt(v)} r="2.5" fill="#64748B" />
          ))}

          {/* Forecast line (dashed) */}
          {fcstPath && (
            <path d={fcstPath} stroke="#2563EB" strokeWidth="2" fill="none" strokeDasharray="5 3" />
          )}
          {fcst.map((v, i) => (
            <circle key={`f-${i}`} cx={xAt(fcstStart + i)} cy={yAt(v)} r="3" fill="#2563EB" />
          ))}

          {/* X-axis labels — every other month to avoid crowding */}
          {[...pastLabels, ...fcstLabels].map((lbl, i) => {
            if (totalMonths > 10 && i % 2 !== 0 && i !== totalMonths - 1) return null;
            return (
              <text key={`xl-${i}`} x={xAt(i)} y={H - PAD_B + 14} fontSize="9"
                    fill={i >= fcstStart ? '#2563EB' : '#94A3B8'}
                    textAnchor="middle" fontWeight={i >= fcstStart ? '600' : '400'}>
                {lbl?.label}
              </text>
            );
          })}
        </svg>
        <div className="flex items-center gap-4 text-xs text-slate-500 mt-2 flex-wrap">
          <span className="inline-flex items-center gap-1">
            <span className="inline-block w-3 h-0.5 bg-slate-500" /> Actual (past 12mo)
          </span>
          <span className="inline-flex items-center gap-1">
            <span className="inline-block w-3 border-t-2 border-dashed border-blue-600" /> Forecast
          </span>
          <span className="inline-flex items-center gap-1">
            <span className="inline-block w-3 h-2 bg-blue-500/20 border border-blue-500/30" /> P25 – P75 band
          </span>
          <span className="inline-flex items-center gap-1">
            <span className="inline-block w-3 h-2 bg-amber-200/70" /> Festival / monsoon month
          </span>
        </div>
      </div>

      {/* Monthly forecast breakdown */}
      <div>
        <div className="text-xs uppercase tracking-wide text-slate-500 mb-2 font-semibold">
          Monthly forecast breakdown
        </div>
        <div className="overflow-x-auto border border-slate-200 rounded">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-xs uppercase text-slate-500">
              <tr>
                <Th>Month</Th>
                <Th className="text-right">Forecast</Th>
                <Th className="text-right">Low (P25)</Th>
                <Th className="text-right">High (P75)</Th>
                <Th>Notes</Th>
              </tr>
            </thead>
            <tbody>
              {fcst.map((v, i) => {
                const lbl = fcstLabels[i] || {};
                const tag = lbl.festival_tag;
                return (
                  <tr key={i} className="border-t border-slate-100"
                      data-testid={`forecast-deepdive-month-${i}`}>
                    <Td>{lbl.label || `+${i + 1}`}</Td>
                    <Td className="text-right font-semibold">{NUM(v, { maximumFractionDigits: 1 })}</Td>
                    <Td className="text-right text-slate-500">{NUM(low[i], { maximumFractionDigits: 1 })}</Td>
                    <Td className="text-right text-slate-500">{NUM(high[i], { maximumFractionDigits: 1 })}</Td>
                    <Td className="text-xs">
                      {tag ? (
                        <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-amber-100 text-amber-800 font-semibold">
                          <Sparkles size={10} /> {tag}
                        </span>
                      ) : (
                        <span className="text-slate-400">—</span>
                      )}
                    </Td>
                  </tr>
                );
              })}
              {!fcst.length && (
                <tr><td colSpan={5} className="p-4 text-center text-slate-400 text-sm">
                  No forecast data available for this SKU.
                </td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

const Chip = ({ label, value, tint }) => (
  <div className={`px-2.5 py-1.5 rounded ${tint}`}>
    <div className="text-[10px] uppercase font-semibold opacity-70">{label}</div>
    <div className="text-sm font-bold">{value}</div>
  </div>
);

export default DemandForecast;
