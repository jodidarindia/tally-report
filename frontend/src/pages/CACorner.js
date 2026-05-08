import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import {
  Landmark, TrendingUp, TrendingDown, Brain, ArrowUpCircle, ArrowDownCircle,
  Loader, IndianRupee, BarChart3, ChevronDown, ChevronUp, RefreshCw, Download,
  PieChart, Layers
} from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL + '/api';
const fmtRs = (v) => `Rs.${(v || 0).toLocaleString('en-IN', { maximumFractionDigits: 0 })}`;

const CACorner = ({ selectedFY, excludeBranches }) => {
  const [activeTab, setActiveTab] = useState('cashflow');
  const [loading, setLoading] = useState(false);
  const [cashFlow, setCashFlow] = useState(null);
  const [plData, setPlData] = useState(null);
  const [plView, setPlView] = useState('annual');
  const [aiInsights, setAiInsights] = useState(null);
  const [aiLoading, setAiLoading] = useState(false);
  const [sortField, setSortField] = useState('');
  const [sortDir, setSortDir] = useState('desc');
  const [bsData, setBsData] = useState(null);
  const [drillType, setDrillType] = useState('expense');
  const [drillData, setDrillData] = useState(null);
  const [expandedGroups, setExpandedGroups] = useState({});

  const fetchCashFlow = useCallback(async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${API}/ca-corner/cash-flow`, { params: { fy: selectedFY } });
      if (res.data?.success) setCashFlow(res.data.data);
    } catch { toast.error('Failed to load cash flow'); }
    finally { setLoading(false); }
  }, [selectedFY]);

  const fetchPL = useCallback(async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${API}/ca-corner/profit-loss`, { params: { fy: selectedFY, view: plView } });
      if (res.data?.success) setPlData(res.data.data);
    } catch { toast.error('Failed to load P&L'); }
    finally { setLoading(false); }
  }, [selectedFY, plView]);

  const fetchBS = useCallback(async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${API}/ca-corner/balance-sheet`, { params: { fy: selectedFY } });
      if (res.data?.success) setBsData(res.data.data);
    } catch { toast.error('Failed to load Balance Sheet'); }
    finally { setLoading(false); }
  }, [selectedFY]);

  const fetchDrill = useCallback(async (type) => {
    setLoading(true);
    try {
      const res = await axios.get(`${API}/ca-corner/pl-drilldown`, { params: { type } });
      if (res.data?.success) setDrillData(res.data.data);
    } catch { toast.error('Failed to load drill-down'); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => {
    if (activeTab === 'cashflow') fetchCashFlow();
    else if (activeTab === 'pl') fetchPL();
    else if (activeTab === 'bs') fetchBS();
    else if (activeTab === 'drill') fetchDrill(drillType);
  }, [activeTab, fetchCashFlow, fetchPL, fetchBS, fetchDrill, drillType]);

  const fetchAIInsights = async () => {
    setAiLoading(true);
    try {
      const res = await axios.post(`${API}/ca-corner/expense-insights`, {});
      if (res.data?.success) setAiInsights(res.data.data);
      else toast.error(res.data?.error || 'Failed');
    } catch (e) { toast.error(e.response?.data?.error || 'AI analysis failed'); }
    finally { setAiLoading(false); }
  };

  const toggleSort = (field) => {
    if (sortField === field) setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    else { setSortField(field); setSortDir('desc'); }
  };

  const tabs = [
    { id: 'cashflow', label: 'Cash Flow', icon: Landmark },
    { id: 'pl', label: 'P&L Report', icon: BarChart3 },
    { id: 'bs', label: 'Balance Sheet', icon: Layers },
    { id: 'drill', label: 'Ledger Drill-Down', icon: PieChart },
    { id: 'ai', label: 'AI Expense Insights', icon: Brain },
  ];

  return (
    <div data-testid="ca-corner-page">
      <div className="mb-6">
        <h1 className="text-2xl sm:text-4xl font-light tracking-tight text-slate-900" style={{ fontFamily: 'Outfit, sans-serif' }}>
          CA Corner
        </h1>
        <p className="mt-1 text-sm text-slate-600">Cash Flow, Expense Analysis & Profit/Loss</p>
      </div>

      {/* Tabs */}
      <div className="bg-white border border-slate-200 rounded-xl p-1.5 mb-6 flex gap-1.5 overflow-x-auto">
        {tabs.map(tab => {
          const Icon = tab.icon;
          return (
            <button key={tab.id} onClick={() => setActiveTab(tab.id)} data-testid={`tab-${tab.id}`}
              className={`flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg transition-all font-medium min-w-fit ${
                activeTab === tab.id ? 'bg-[#2563EB] text-white text-sm' : 'text-slate-600 hover:bg-slate-50 text-xs sm:text-sm'
              }`}>
              <Icon size={16} />
              <span className="text-center leading-tight sm:whitespace-nowrap">{tab.label}</span>
            </button>
          );
        })}
      </div>

      {loading && <div className="flex items-center justify-center h-40"><div className="loading-spinner" /><span className="ml-3 text-slate-600">Loading...</span></div>}

      {/* Cash Flow Tab */}
      {activeTab === 'cashflow' && !loading && cashFlow && <CashFlowView data={cashFlow} />}
      {activeTab === 'cashflow' && !loading && !cashFlow && (
        <div className="text-center py-16 text-slate-400">
          <Landmark size={48} className="mx-auto mb-3 text-slate-300" />
          <p className="font-medium">No cash flow data available</p>
          <p className="text-sm mt-1">Sync bank & cash ledger data from Tally* to see your cash flow statement</p>
        </div>
      )}

      {/* AI Insights Tab */}
      {activeTab === 'ai' && <AIInsightsView insights={aiInsights} loading={aiLoading} onAnalyze={fetchAIInsights} />}

      {/* P&L Tab */}
      {activeTab === 'pl' && !loading && (
        <PLView data={plData} view={plView} setView={setPlView} sortField={sortField} sortDir={sortDir} toggleSort={toggleSort} />
      )}

      {/* Balance Sheet Tab */}
      {activeTab === 'bs' && !loading && <BalanceSheetView data={bsData} />}

      {/* Ledger Drill-Down Tab */}
      {activeTab === 'drill' && !loading && (
        <DrillDownView data={drillData} drillType={drillType} setDrillType={setDrillType}
          expanded={expandedGroups} toggleExpand={(g) => setExpandedGroups(e => ({...e, [g]: !e[g]}))} />
      )}
    </div>
  );
};

/* ─── Cash Flow View ────────────────────────────────── */
const CashFlowView = ({ data }) => {
  const s = data.summary || {};
  const banks = data.bank_details || [];

  return (
    <div data-testid="cashflow-view">
      {/* Summary Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
        <div className="bg-white border border-slate-200 rounded-xl p-4">
          <div className="text-xs text-slate-500 mb-1">Opening (Cash + Bank)</div>
          <div className="text-xl font-bold text-slate-900" data-testid="cf-opening">{fmtRs(s.opening_total)}</div>
        </div>
        <div className="bg-white border border-slate-200 rounded-xl p-4">
          <div className="text-xs text-slate-500 mb-1">Closing (Cash + Bank)</div>
          <div className="text-xl font-bold text-slate-900" data-testid="cf-closing">{fmtRs(s.closing_total)}</div>
        </div>
        <div className="bg-white border border-slate-200 rounded-xl p-4">
          <div className="text-xs text-green-600 mb-1">Total Receipts</div>
          <div className="text-xl font-bold text-green-700">{fmtRs(s.total_receipts)}</div>
        </div>
        <div className="bg-white border border-slate-200 rounded-xl p-4">
          <div className="text-xs text-red-500 mb-1">Total Payments</div>
          <div className="text-xl font-bold text-red-600">{fmtRs(s.total_payments)}</div>
        </div>
      </div>

      {/* Net Change */}
      <div className={`rounded-xl p-5 mb-6 border ${s.net_change >= 0 ? 'bg-green-50 border-green-200' : 'bg-red-50 border-red-200'}`}>
        <div className="flex items-center gap-3">
          {s.net_change >= 0 ? <ArrowUpCircle size={28} className="text-green-600" /> : <ArrowDownCircle size={28} className="text-red-600" />}
          <div>
            <div className="text-sm text-slate-600">Net Cash Change</div>
            <div className={`text-2xl font-bold ${s.net_change >= 0 ? 'text-green-700' : 'text-red-700'}`}>{fmtRs(s.net_change)}</div>
          </div>
        </div>
      </div>

      {/* Operating / Investing / Financing */}
      <div className="grid sm:grid-cols-3 gap-4 mb-6">
        <FlowSection title="Operating Activities" items={data.operating?.items || []} net={data.operating?.net} color="blue" />
        <FlowSection title="Investing Activities" items={data.investing?.items || []} net={data.investing?.net} color="amber" />
        <FlowSection title="Financing Activities" items={data.financing?.items || []} net={data.financing?.net} color="purple" />
      </div>

      {/* Bank/Cash Details */}
      {banks.length > 0 && (
        <div className="bg-white border border-slate-200 rounded-xl overflow-x-auto">
          <div className="p-4 border-b border-slate-100">
            <h3 className="font-semibold text-slate-900">Bank & Cash Accounts</h3>
          </div>
          <table className="data-table min-w-[500px]" data-testid="bank-details-table">
            <thead><tr>
              <th>Account</th><th>Type</th><th className="numeric">Opening</th><th className="numeric">Closing</th>
            </tr></thead>
            <tbody>
              {banks.map((b, i) => (
                <tr key={i}>
                  <td className="font-medium text-slate-900">{b.name}<div className="text-xs text-slate-400">{b.bank_name} {b.account_number ? `...${b.account_number.slice(-4)}` : ''}</div></td>
                  <td><span className={`px-2 py-0.5 rounded text-xs font-medium ${b.type === 'bank' ? 'bg-blue-100 text-blue-700' : b.type === 'bank_od' ? 'bg-red-100 text-red-700' : 'bg-green-100 text-green-700'}`}>{b.type === 'bank_od' ? 'OD' : b.type}</span></td>
                  <td className="numeric">{fmtRs(b.opening)}</td>
                  <td className="numeric font-semibold">{fmtRs(b.closing)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};

const MoMCell = ({ pct, positiveGood = true }) => {
  if (pct === null || pct === undefined) return <span className="text-slate-300">—</span>;
  const isUp = pct > 0;
  const good = positiveGood ? isUp : !isUp;
  const color = Math.abs(pct) < 0.1 ? 'text-slate-400'
    : good ? 'text-green-600' : 'text-red-500';
  const arrow = Math.abs(pct) < 0.1 ? '·' : (isUp ? '▲' : '▼');
  return <span className={color}>{arrow} {Math.abs(pct).toFixed(1)}%</span>;
};

const FlowSection = ({ title, items, net, color }) => {
  const colors = { blue: 'bg-blue-50 border-blue-200 text-blue-800', amber: 'bg-amber-50 border-amber-200 text-amber-800', purple: 'bg-purple-50 border-purple-200 text-purple-800' };
  return (
    <div className={`border rounded-xl p-4 ${colors[color] || 'bg-slate-50 border-slate-200'}`}>
      <h3 className="font-semibold text-sm mb-3">{title}</h3>
      {items.length > 0 ? items.map((item, i) => (
        <div key={i} className="flex justify-between text-sm py-1">
          <span className="text-slate-700">{item.label}</span>
          <span className="font-medium">{fmtRs(item.amount)}</span>
        </div>
      )) : <p className="text-xs text-slate-400">No data synced yet</p>}
      <div className="border-t mt-2 pt-2 flex justify-between font-bold text-sm">
        <span>Net</span><span>{fmtRs(net || 0)}</span>
      </div>
    </div>
  );
};

/* ─── AI Insights View ──────────────────────────────── */
const AIInsightsView = ({ insights, loading, onAnalyze }) => (
  <div data-testid="ai-insights-view">
    {!insights && !loading && (
      <div className="text-center py-16">
        <Brain size={56} className="mx-auto mb-4 text-[#2563EB]" />
        <h3 className="text-xl font-bold text-slate-900 mb-2">AI Expense Analysis</h3>
        <p className="text-slate-500 mb-6 max-w-md mx-auto">Our AI will analyze your Tally* expense data and provide actionable insights to reduce costs and improve profitability.</p>
        <button onClick={onAnalyze} className="px-8 py-3 bg-[#2563EB] text-white rounded-lg font-medium hover:bg-[#1D4ED8] transition-colors" data-testid="analyze-btn">
          <Brain size={18} className="inline mr-2" /> Analyze Expenses
        </button>
      </div>
    )}
    {loading && (
      <div className="text-center py-16">
        <Loader size={40} className="mx-auto mb-4 text-[#2563EB] animate-spin" />
        <p className="text-slate-600 font-medium">Analyzing your expense data...</p>
        <p className="text-slate-400 text-sm mt-1">This may take 15-30 seconds</p>
      </div>
    )}
    {insights && !loading && (
      <div>
        {/* Summary Cards */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
          <div className="bg-white border border-slate-200 rounded-xl p-4">
            <div className="text-xs text-slate-500 mb-1">Total Income</div>
            <div className="text-lg font-bold text-green-700">{fmtRs(insights.expense_summary?.total_income)}</div>
          </div>
          <div className="bg-white border border-slate-200 rounded-xl p-4">
            <div className="text-xs text-slate-500 mb-1">Total Expense</div>
            <div className="text-lg font-bold text-red-600">{fmtRs(insights.expense_summary?.total_expense)}</div>
          </div>
          <div className="bg-white border border-slate-200 rounded-xl p-4">
            <div className="text-xs text-slate-500 mb-1">Net P&L</div>
            <div className={`text-lg font-bold ${(insights.expense_summary?.net_profit_loss || 0) >= 0 ? 'text-green-700' : 'text-red-600'}`}>{fmtRs(insights.expense_summary?.net_profit_loss)}</div>
          </div>
          <div className="bg-white border border-slate-200 rounded-xl p-4">
            <div className="text-xs text-slate-500 mb-1">Expense Ratio</div>
            <div className="text-lg font-bold text-amber-600">{insights.expense_summary?.expense_ratio || 0}%</div>
          </div>
        </div>

        {/* AI Analysis */}
        <div className="bg-white border border-slate-200 rounded-xl p-6 mb-6">
          <div className="flex items-center gap-2 mb-4">
            <Brain size={20} className="text-[#2563EB]" />
            <h3 className="font-bold text-slate-900">AI Analysis</h3>
          </div>
          <div className="prose prose-slate max-w-none text-sm leading-relaxed whitespace-pre-wrap" data-testid="ai-analysis-text">
            {insights.analysis}
          </div>
        </div>

        {/* Top Expenses Table */}
        {insights.expense_summary?.top_expenses?.length > 0 && (
          <div className="bg-white border border-slate-200 rounded-xl overflow-x-auto">
            <div className="p-4 border-b border-slate-100"><h3 className="font-semibold text-slate-900">Top 10 Expenses</h3></div>
            <table className="data-table min-w-[400px]" data-testid="top-expenses-table">
              <thead><tr><th>Expense</th><th>Group</th><th className="numeric">Amount</th></tr></thead>
              <tbody>
                {insights.expense_summary.top_expenses.map((e, i) => (
                  <tr key={i}>
                    <td className="font-medium text-slate-900">{e.name}</td>
                    <td className="text-slate-500 text-sm">{e.group}</td>
                    <td className="numeric font-semibold text-red-600">{fmtRs(e.amount)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <div className="mt-4 text-center">
          <button onClick={onAnalyze} className="text-sm text-[#2563EB] hover:underline" data-testid="re-analyze-btn">
            <RefreshCw size={14} className="inline mr-1" /> Re-analyze
          </button>
        </div>
      </div>
    )}
  </div>
);

/* ─── P&L View ──────────────────────────────────────── */
const PLView = ({ data, view, setView, sortField, sortDir, toggleSort }) => {
  if (!data) return (
    <div className="text-center py-16 text-slate-400">
      <BarChart3 size={48} className="mx-auto mb-3 text-slate-300" />
      <p className="font-medium">No P&L data available</p>
      <p className="text-sm mt-1">Sync P&L data from Tally* first</p>
    </div>
  );

  const months = ["Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec", "Jan", "Feb", "Mar"];

  return (
    <div data-testid="pl-view">
      {/* Toggle */}
      <div className="flex items-center gap-3 mb-6">
        <span className="text-sm text-slate-600">View:</span>
        <div className="bg-white border border-slate-200 rounded-lg p-1 flex gap-1">
          <button onClick={() => setView('annual')} data-testid="pl-annual-btn"
            className={`px-4 py-1.5 rounded text-sm font-medium transition-colors ${view === 'annual' ? 'bg-[#2563EB] text-white' : 'text-slate-600 hover:bg-slate-50'}`}>
            Annual
          </button>
          <button onClick={() => setView('monthly')} data-testid="pl-monthly-btn"
            className={`px-4 py-1.5 rounded text-sm font-medium transition-colors ${view === 'monthly' ? 'bg-[#2563EB] text-white' : 'text-slate-600 hover:bg-slate-50'}`}>
            Monthly
          </button>
        </div>
      </div>

      {/* Summary — Tally-style breakdown */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
        <div className="bg-green-50 border border-green-200 rounded-xl p-4">
          <div className="text-xs text-green-600 mb-1">Sales (Net)</div>
          <div className="text-lg font-bold text-green-700">{fmtRs(data.total_sales)}</div>
        </div>
        <div className="bg-red-50 border border-red-200 rounded-xl p-4">
          <div className="text-xs text-red-500 mb-1">Purchases (Net)</div>
          <div className="text-lg font-bold text-red-600">{fmtRs(data.total_purchases)}</div>
        </div>
        <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-4">
          <div className="text-xs text-emerald-600 mb-1">Indirect Income</div>
          <div className="text-lg font-bold text-emerald-700">{fmtRs(data.indirect_income)}</div>
        </div>
        <div className="bg-orange-50 border border-orange-200 rounded-xl p-4">
          <div className="text-xs text-orange-500 mb-1">Indirect Expense</div>
          <div className="text-lg font-bold text-orange-600">{fmtRs(data.indirect_expense)}</div>
        </div>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
        <div className="bg-blue-50 border border-blue-200 rounded-xl p-5">
          <div className="text-sm text-blue-600 mb-1">Gross Profit</div>
          <div className={`text-2xl font-bold ${(data.gross_profit || 0) >= 0 ? 'text-blue-700' : 'text-red-600'}`}>{fmtRs(data.gross_profit)}</div>
        </div>
        <div className="bg-slate-50 border border-slate-200 rounded-xl p-5">
          <div className="text-sm text-slate-600 mb-1">Stock Movement</div>
          <div className="text-base font-medium text-slate-700">Open: {fmtRs(data.opening_stock)}</div>
          <div className="text-base font-medium text-slate-700">Close: {fmtRs(data.closing_stock)}</div>
        </div>
        <div className={`rounded-xl p-5 border ${(data.net_profit_loss || 0) >= 0 ? 'bg-indigo-50 border-indigo-200' : 'bg-amber-50 border-amber-200'}`}>
          <div className="text-sm text-slate-600 mb-1">Net Profit / Loss</div>
          <div className={`text-2xl font-bold ${(data.net_profit_loss || 0) >= 0 ? 'text-indigo-700' : 'text-red-600'}`}>{fmtRs(data.net_profit_loss)}</div>
        </div>
      </div>

      {/* Monthly View */}
      {view === 'monthly' && data.monthly?.length > 0 && (
        <div className="bg-white border border-slate-200 rounded-xl overflow-x-auto mb-6">
          <table className="data-table min-w-[900px]" data-testid="pl-monthly-table">
            <thead><tr>
              <th>Particulars</th>
              {months.map(m => <th key={m} className="numeric cursor-pointer" onClick={() => toggleSort(m)}>{m} {sortField === m ? (sortDir === 'asc' ? '↑' : '↓') : ''}</th>)}
              <th className="numeric font-bold">Total</th>
            </tr></thead>
            <tbody>
              <tr className="bg-green-50/50">
                <td className="font-semibold text-green-700">Sales</td>
                {data.monthly.map((m, i) => <td key={i} className="numeric text-green-700">{fmtRs(m.sales)}</td>)}
                <td className="numeric font-bold text-green-700">{fmtRs(data.monthly.reduce((s, m) => s + m.sales, 0))}</td>
              </tr>
              <tr className="bg-green-50/30 text-[11px]" data-testid="pl-monthly-sales-mom">
                <td className="text-slate-500 italic pl-4">M-o-M change</td>
                {data.monthly.map((m, i) => <td key={i} className="numeric"><MoMCell pct={m.sales_change_pct} positiveGood /></td>)}
                <td></td>
              </tr>
              <tr className="bg-red-50/50">
                <td className="font-semibold text-red-600">Purchases</td>
                {data.monthly.map((m, i) => <td key={i} className="numeric text-red-600">{fmtRs(m.purchases)}</td>)}
                <td className="numeric font-bold text-red-600">{fmtRs(data.monthly.reduce((s, m) => s + m.purchases, 0))}</td>
              </tr>
              <tr className="bg-red-50/30 text-[11px]" data-testid="pl-monthly-purchases-mom">
                <td className="text-slate-500 italic pl-4">M-o-M change</td>
                {data.monthly.map((m, i) => <td key={i} className="numeric"><MoMCell pct={m.purchases_change_pct} positiveGood={false} /></td>)}
                <td></td>
              </tr>
              {data.monthly_meta?.stock_aware && (
                <tr className="bg-amber-50/40 text-[11px]" data-testid="pl-monthly-cogs">
                  <td className="text-amber-700 italic pl-4">Cost of Goods Sold</td>
                  {data.monthly.map((m, i) => <td key={i} className="numeric text-amber-700">{fmtRs(m.cogs)}</td>)}
                  <td className="numeric font-medium text-amber-800">{fmtRs(data.monthly.reduce((s, m) => s + (m.cogs || 0), 0))}</td>
                </tr>
              )}
              <tr className="border-t-2 border-slate-300">
                <td className="font-bold text-slate-900">Gross Profit{data.monthly_meta?.stock_aware ? '' : ' (Trading)'}</td>
                {data.monthly.map((m, i) => <td key={i} className={`numeric font-semibold ${m.gross_profit >= 0 ? 'text-blue-700' : 'text-red-600'}`}>{fmtRs(m.gross_profit)}</td>)}
                <td className="numeric font-bold text-blue-700">{fmtRs(data.monthly.reduce((s, m) => s + m.gross_profit, 0))}</td>
              </tr>
              <tr className="text-[11px]" data-testid="pl-monthly-gp-mom">
                <td className="text-slate-500 italic pl-4">M-o-M change</td>
                {data.monthly.map((m, i) => <td key={i} className="numeric"><MoMCell pct={m.gp_change_pct} positiveGood /></td>)}
                <td></td>
              </tr>
              <tr>
                <td className="text-slate-600">Receipts</td>
                {data.monthly.map((m, i) => <td key={i} className="numeric text-slate-600">{fmtRs(m.receipts)}</td>)}
                <td className="numeric font-medium">{fmtRs(data.monthly.reduce((s, m) => s + m.receipts, 0))}</td>
              </tr>
            </tbody>
          </table>
          {(data.notices || []).length > 0 && (
            <div className="px-4 py-3 border-t border-slate-100 bg-slate-50/50 space-y-1" data-testid="pl-monthly-notices">
              {data.notices.map((n, i) => (
                <p key={i} className="text-[11px] text-slate-500 italic flex gap-1.5">
                  <span className="text-blue-500">ⓘ</span><span>{n}</span>
                </p>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Annual View - Income & Expense Ledgers */}
      {view === 'annual' && (
        <div className="grid sm:grid-cols-2 gap-4">
          <LedgerTable title="Income" items={data.income || []} color="green" />
          <LedgerTable title="Expenses" items={data.expense || []} color="red" />
        </div>
      )}
    </div>
  );
};

const LedgerTable = ({ title, items, color }) => {
  const [expanded, setExpanded] = useState(true);
  const total = items.reduce((s, i) => s + (i.amount || 0), 0);

  return (
    <div className="bg-white border border-slate-200 rounded-xl overflow-hidden">
      <button onClick={() => setExpanded(!expanded)} className="w-full flex items-center justify-between p-4 hover:bg-slate-50">
        <h3 className={`font-bold ${color === 'green' ? 'text-green-700' : 'text-red-600'}`}>{title} ({items.length})</h3>
        <div className="flex items-center gap-3">
          <span className={`font-bold ${color === 'green' ? 'text-green-700' : 'text-red-600'}`}>{fmtRs(total)}</span>
          {expanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
        </div>
      </button>
      {expanded && items.length > 0 && (
        <div className="overflow-x-auto">
          <table className="data-table w-full" data-testid={`${title.toLowerCase()}-ledger-table`}>
            <thead><tr><th>Ledger</th><th>Group</th><th className="numeric">Amount</th></tr></thead>
            <tbody>
              {items.sort((a, b) => (b.amount || 0) - (a.amount || 0)).map((item, i) => (
                <tr key={i}>
                  <td className="font-medium text-slate-800">{item.ledger_name}</td>
                  <td className="text-slate-500 text-sm">{item.parent_group}</td>
                  <td className={`numeric font-medium ${color === 'green' ? 'text-green-700' : 'text-red-600'}`}>{fmtRs(item.amount)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};

export default CACorner;

/* ─── Balance Sheet View ────────────────────────────── */
const BalanceSheetView = ({ data }) => {
  const [expanded, setExpanded] = useState({});
  if (!data) return <div className="text-center text-sm text-slate-400 py-10">No balance sheet data. Run desktop agent to sync ledgers.</div>;

  const toggle = (key) => setExpanded(e => ({...e, [key]: !e[key]}));

  const GroupSection = ({ title, groups, total, color }) => (
    <div className="bg-white rounded-xl border border-slate-200 overflow-hidden" data-testid={`bs-${title.toLowerCase().replace(/\s/g,'-')}`}>
      <div className="p-3 sm:p-4 border-b border-slate-100 flex items-center justify-between">
        <h3 className="text-sm font-bold" style={{color}}>{title}</h3>
        <span className="text-sm font-bold" style={{color}}>{fmtRs(total)}</span>
      </div>
      {groups.length === 0 && <p className="text-center text-xs text-slate-400 py-4">No data</p>}
      {groups.map((g, gi) => (
        <div key={gi} className="border-b border-slate-50 last:border-0">
          <button onClick={() => toggle(`${title}-${gi}`)} className="w-full text-left px-3 sm:px-4 py-2.5 flex items-center justify-between hover:bg-slate-25 transition">
            <span className="text-xs font-semibold text-slate-700">{g.group}</span>
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold text-slate-900">{fmtRs(g.total)}</span>
              <ChevronDown size={14} className={`text-slate-400 transition ${expanded[`${title}-${gi}`] ? 'rotate-180' : ''}`}/>
            </div>
          </button>
          {expanded[`${title}-${gi}`] && g.ledgers && (
            <div className="px-3 sm:px-4 pb-2.5 space-y-0.5">
              {g.ledgers.sort((a,b) => b.amount - a.amount).map((l, li) => (
                <div key={li} className="flex items-center justify-between text-xs py-0.5 pl-4 border-l-2 border-slate-200">
                  <span className="text-slate-600 truncate mr-2">{l.name}</span>
                  <span className="text-slate-800 font-medium flex-shrink-0">{fmtRs(l.amount)}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  );

  return (
    <div data-testid="bs-view" className="space-y-4">
      {data.notice && <div className="bg-amber-50 border border-amber-200 rounded-xl p-3 text-xs text-amber-800">{data.notice}</div>}
      {data.source === 'derived_from_all_ledgers' && (
        <div className="flex items-center gap-2 text-xs text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-lg px-3 py-1.5 inline-flex">
          <span className="text-[10px]">✓</span> FY {data.fy} · {data.view === 'opening' ? 'Opening Balance view' : 'Closing Balance view'} · {data.ledger_count} ledgers + {data.debtor_count} debtors + {data.creditor_count} creditors
        </div>
      )}
      {data.message && <div className="bg-amber-50 border border-amber-200 rounded-xl p-3 text-xs text-amber-800">{data.message}</div>}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div className="space-y-3">
          <GroupSection title="Assets" groups={data.assets || []} total={data.total_assets || 0} color="#10b981"/>
        </div>
        <div className="space-y-3">
          <GroupSection title="Liabilities & Capital" groups={data.liabilities || []} total={data.total_liabilities || 0} color="#ef4444"/>
        </div>
      </div>
      <div className="grid grid-cols-3 gap-3">
        <div className="bg-green-50 border border-green-200 rounded-xl p-3 text-center">
          <div className="text-[10px] text-green-600 uppercase font-semibold">Total Assets</div>
          <div className="text-lg font-bold text-green-700">{fmtRs(data.total_assets)}</div>
        </div>
        <div className="bg-red-50 border border-red-200 rounded-xl p-3 text-center">
          <div className="text-[10px] text-red-600 uppercase font-semibold">Liabilities + Capital</div>
          <div className="text-lg font-bold text-red-700">{fmtRs(data.total_liabilities)}</div>
        </div>
        <div className={`rounded-xl p-3 text-center border ${Math.abs(data.difference || 0) < 1 ? 'bg-emerald-50 border-emerald-200' : 'bg-amber-50 border-amber-200'}`}>
          <div className="text-[10px] uppercase font-semibold text-slate-600">Difference</div>
          <div className={`text-lg font-bold ${Math.abs(data.difference || 0) < 1 ? 'text-emerald-700' : 'text-amber-700'}`}>{fmtRs(data.difference || 0)}</div>
        </div>
      </div>
    </div>
  );
};

/* ─── Ledger Drill-Down View ────────────────────────── */
const DrillDownView = ({ data, drillType, setDrillType, expanded, toggleExpand }) => {
  return (
    <div data-testid="drill-view">
      <div className="flex items-center gap-2 mb-4">
        <button onClick={() => setDrillType('income')} className={`px-3 py-1.5 text-xs rounded-lg font-medium transition ${drillType === 'income' ? 'bg-green-600 text-white' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'}`} data-testid="drill-income">Income</button>
        <button onClick={() => setDrillType('expense')} className={`px-3 py-1.5 text-xs rounded-lg font-medium transition ${drillType === 'expense' ? 'bg-red-600 text-white' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'}`} data-testid="drill-expense">Expense</button>
        {data && <span className="ml-auto text-sm font-bold text-slate-900">Total: {fmtRs(data.total)}</span>}
      </div>
      {!data && <p className="text-center text-sm text-slate-400 py-10">No P&L data synced yet.</p>}
      {data && data.groups?.length === 0 && <p className="text-center text-sm text-slate-400 py-10">No {drillType} ledgers found.</p>}
      {data && data.groups?.map((g, gi) => (
        <div key={gi} className="bg-white rounded-xl border border-slate-200 mb-2 overflow-hidden" data-testid={`drill-group-${gi}`}>
          <button onClick={() => toggleExpand(gi)} className="w-full text-left p-3 flex items-center justify-between hover:bg-slate-25 transition">
            <div className="min-w-0 flex-1">
              <div className="text-xs font-bold text-slate-800">{g.group}</div>
              <div className="text-[10px] text-slate-500">{g.ledgers?.length || 0} ledgers | {g.pct}% of total</div>
            </div>
            <div className="flex items-center gap-2 flex-shrink-0">
              <span className="text-sm font-bold" style={{color: drillType === 'income' ? '#10b981' : '#ef4444'}}>{fmtRs(g.total)}</span>
              <ChevronDown size={14} className={`text-slate-400 transition ${expanded[gi] ? 'rotate-180' : ''}`}/>
            </div>
          </button>
          {expanded[gi] && g.ledgers && (
            <div className="border-t border-slate-100">
              {g.ledgers.map((l, li) => (
                <div key={li} className="px-4 py-2 flex items-center justify-between border-b border-slate-50 last:border-0 text-xs">
                  <span className="text-slate-700 truncate mr-2">{l.name}</span>
                  <div className="flex items-center gap-3 flex-shrink-0">
                    <div className="w-20 h-1.5 bg-slate-100 rounded-full overflow-hidden"><div className="h-full rounded-full" style={{width: `${Math.min(l.pct, 100)}%`, background: drillType === 'income' ? '#10b981' : '#ef4444'}}/></div>
                    <span className="text-[10px] text-slate-400 w-10 text-right">{l.pct}%</span>
                    <span className="font-medium text-slate-900 w-24 text-right">{fmtRs(l.amount)}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  );
};
