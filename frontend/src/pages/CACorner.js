import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import {
  Landmark, TrendingUp, TrendingDown, Brain, ArrowUpCircle, ArrowDownCircle,
  Loader, IndianRupee, BarChart3, ChevronDown, ChevronUp, RefreshCw, Download
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

  useEffect(() => {
    if (activeTab === 'cashflow') fetchCashFlow();
    else if (activeTab === 'pl') fetchPL();
  }, [activeTab, fetchCashFlow, fetchPL]);

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
    { id: 'ai', label: 'AI Expense Insights', icon: Brain },
    { id: 'pl', label: 'P&L Report', icon: BarChart3 },
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

      {/* Summary */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
        <div className="bg-green-50 border border-green-200 rounded-xl p-5">
          <div className="text-sm text-green-600 mb-1">Total Income</div>
          <div className="text-2xl font-bold text-green-700">{fmtRs(data.total_income)}</div>
        </div>
        <div className="bg-red-50 border border-red-200 rounded-xl p-5">
          <div className="text-sm text-red-500 mb-1">Total Expense</div>
          <div className="text-2xl font-bold text-red-600">{fmtRs(data.total_expense)}</div>
        </div>
        <div className={`rounded-xl p-5 border ${data.net_profit_loss >= 0 ? 'bg-blue-50 border-blue-200' : 'bg-amber-50 border-amber-200'}`}>
          <div className="text-sm text-slate-600 mb-1">Net Profit / Loss</div>
          <div className={`text-2xl font-bold ${data.net_profit_loss >= 0 ? 'text-blue-700' : 'text-red-600'}`}>{fmtRs(data.net_profit_loss)}</div>
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
              <tr className="bg-red-50/50">
                <td className="font-semibold text-red-600">Purchases</td>
                {data.monthly.map((m, i) => <td key={i} className="numeric text-red-600">{fmtRs(m.purchases)}</td>)}
                <td className="numeric font-bold text-red-600">{fmtRs(data.monthly.reduce((s, m) => s + m.purchases, 0))}</td>
              </tr>
              <tr className="border-t-2 border-slate-300">
                <td className="font-bold text-slate-900">Gross Profit</td>
                {data.monthly.map((m, i) => <td key={i} className={`numeric font-semibold ${m.gross_profit >= 0 ? 'text-blue-700' : 'text-red-600'}`}>{fmtRs(m.gross_profit)}</td>)}
                <td className="numeric font-bold text-blue-700">{fmtRs(data.monthly.reduce((s, m) => s + m.gross_profit, 0))}</td>
              </tr>
              <tr>
                <td className="text-slate-600">Receipts</td>
                {data.monthly.map((m, i) => <td key={i} className="numeric text-slate-600">{fmtRs(m.receipts)}</td>)}
                <td className="numeric font-medium">{fmtRs(data.monthly.reduce((s, m) => s + m.receipts, 0))}</td>
              </tr>
            </tbody>
          </table>
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
