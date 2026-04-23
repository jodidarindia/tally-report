import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import {
  Truck, Package, Clock, Users, DollarSign, Boxes, AlertTriangle,
  CheckCircle2, Search, Download, Plus, X, User, ChevronDown, ChevronUp,
  Megaphone, Sparkles, Bug, Zap
} from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL;

const fmt = (n) => {
  if (!n || n === 0) return '0';
  if (Math.abs(n) >= 100000) return `Rs.${(n / 100000).toFixed(2)}L`;
  if (Math.abs(n) >= 1000) return `Rs.${(n / 1000).toFixed(1)}K`;
  return `Rs.${n.toLocaleString('en-IN')}`;
};

const STATUS_COLORS = {
  new: '#64748b', queued: '#3b82f6', processing: '#f59e0b', packed: '#8b5cf6',
  dispatched: '#10b981', info_shared: '#06b6d4', hold: '#ef4444',
};

const UPDATES = [
  { date: '2026-04-23', type: 'feature', icon: Sparkles, color: '#8b5cf6',
    title: 'Dispatch Terminal Launched',
    desc: 'Kanban board for warehouse dispatches with LR tracking, document uploads, and porter settlement.' },
  { date: '2026-04-16', type: 'bugfix', icon: Bug, color: '#ef4444',
    title: 'Outstanding Calculation Fixed',
    desc: 'Opening balances now correctly computed per FY using Tally\'s base year. Journal voucher party-specific amounts fixed.' },
  { date: '2026-04-16', type: 'bugfix', icon: Bug, color: '#ef4444',
    title: 'SPIP Analysis Corrected',
    desc: 'Item name extraction fixed — sales data now properly linked to inventory for gap analysis.' },
  { date: '2026-04-10', type: 'feature', icon: Zap, color: '#f59e0b',
    title: 'Desktop Agent v9',
    desc: 'Data deletion reconciliation, command queue for remote resyncs, dual-schedule syncing (5-min sales, 20-min full).' },
  { date: '2026-04-08', type: 'feature', icon: Sparkles, color: '#8b5cf6',
    title: 'CRM Targets Overhaul',
    desc: 'Bulk percentage target setting, customer removal/reactivation per FY, read-only for completed years.' },
  { date: '2026-04-05', type: 'feature', icon: Sparkles, color: '#8b5cf6',
    title: 'Digital Questionnaire',
    desc: 'Public customer intake forms with SuperAdmin leads view and Excel export.' },
];

export default function DispatchAdmin({ selectedFY, companyId }) {
  const [tab, setTab] = useState('overview');
  const [summary, setSummary] = useState(null);
  const [settlement, setSettlement] = useState([]);
  const [pendingCards, setPendingCards] = useState([]);
  const [employees, setEmployees] = useState([]);
  const [porters, setPorters] = useState([]);
  const [loading, setLoading] = useState(true);
  const [reassignCard, setReassignCard] = useState(null);
  const [newPorter, setNewPorter] = useState({ name: '', phone: '' });
  const [showAddPorter, setShowAddPorter] = useState(false);
  const [payPorter, setPayPorter] = useState(null);
  const [payAmount, setPayAmount] = useState('');
  const [payRef, setPayRef] = useState('');

  const headers = useCallback(() => {
    const token = localStorage.getItem('flowra_token');
    return { Authorization: `Bearer ${token}`, 'X-Company-Id': companyId || '' };
  }, [companyId]);

  const fetchAll = useCallback(async () => {
    try {
      const [summaryR, settlementR, cardsR, empR, porterR] = await Promise.all([
        axios.get(`${API}/api/dispatch/summary?company_id=${companyId || ''}`, { headers: headers() }),
        axios.get(`${API}/api/dispatch/porter-settlement`, { headers: headers() }),
        axios.get(`${API}/api/dispatch/cards?status=active&company_id=${companyId || ''}`, { headers: headers() }),
        axios.get(`${API}/api/dispatch/employees`, { headers: headers() }),
        axios.get(`${API}/api/dispatch/porters`, { headers: headers() }),
      ]);
      if (summaryR.data.success) setSummary(summaryR.data.data);
      if (settlementR.data.success) setSettlement(settlementR.data.data.settlement || []);
      if (cardsR.data.success) setPendingCards((cardsR.data.data.cards || []).filter(c => !['dispatched', 'info_shared'].includes(c.status)));
      if (empR.data.success) setEmployees(empR.data.data.employees || []);
      if (porterR.data.success) setPorters(porterR.data.data.porters || []);
    } catch (e) { console.error(e); }
    setLoading(false);
  }, [companyId, headers]);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  const reassign = async (cardId, assignTo) => {
    try {
      const r = await axios.patch(`${API}/api/dispatch/cards/${cardId}/assign`, { assign_to: assignTo }, { headers: headers() });
      if (r.data.success) { toast.success('Reassigned'); fetchAll(); setReassignCard(null); }
      else toast.error(r.data.error);
    } catch (e) { toast.error(e.response?.data?.error || 'Failed'); }
  };

  const autoCreate = async () => {
    try {
      const r = await axios.post(`${API}/api/dispatch/auto-create`, {}, { headers: headers() });
      if (r.data.success) { toast.success(r.data.message); fetchAll(); }
      else toast.error(r.data.error);
    } catch (e) { toast.error('Auto-create failed'); }
  };

  const addPorter = async () => {
    if (!newPorter.name.trim()) return toast.error('Porter name required');
    try {
      const r = await axios.post(`${API}/api/dispatch/porters`, newPorter, { headers: headers() });
      if (r.data.success) { toast.success('Porter added'); setNewPorter({ name: '', phone: '' }); setShowAddPorter(false); fetchAll(); }
      else toast.error(r.data.error);
    } catch (e) { toast.error('Failed'); }
  };

  const recordPayment = async () => {
    if (!payPorter || !payAmount) return;
    try {
      const r = await axios.post(`${API}/api/dispatch/porter-payment`, {
        porter_name: payPorter, amount: parseFloat(payAmount), payment_ref: payRef,
      }, { headers: headers() });
      if (r.data.success) { toast.success('Payment recorded'); setPayPorter(null); setPayAmount(''); setPayRef(''); fetchAll(); }
      else toast.error(r.data.error);
    } catch (e) { toast.error('Failed'); }
  };

  const tabs = [
    { id: 'overview', label: 'Overview' },
    { id: 'pending', label: `Pending (${pendingCards.length})` },
    { id: 'porters', label: 'Porter Settlement' },
    { id: 'employees', label: 'Employees' },
    { id: 'updates', label: 'Updates' },
  ];

  if (loading) return <div className="flex items-center justify-center h-48"><div className="animate-spin w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full" /></div>;

  return (
    <div data-testid="dispatch-admin">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 mb-5">
        <div>
          <h1 className="text-xl font-bold text-slate-900">Dispatch Management</h1>
          <p className="text-xs text-slate-500 mt-0.5">Admin dashboard for dispatch operations</p>
        </div>
        <button onClick={autoCreate} className="flex items-center gap-1.5 text-xs bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg transition" data-testid="dispatch-auto-create">
          <Package size={14} /> Create Cards from Invoices
        </button>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-5 border-b border-slate-200 overflow-x-auto" data-testid="dispatch-admin-tabs">
        {tabs.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)}
            className={`px-4 py-2 text-xs font-medium border-b-2 transition whitespace-nowrap ${tab === t.id ? 'border-blue-600 text-blue-600' : 'border-transparent text-slate-500 hover:text-slate-700'}`}
            data-testid={`tab-${t.id}`}>{t.label}</button>
        ))}
      </div>

      {/* Overview Tab */}
      {tab === 'overview' && summary && (
        <div className="space-y-5">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <StatCard icon={Truck} color="#10b981" label="Dispatched Today" value={summary.dispatched_count} />
            <StatCard icon={Clock} color="#f59e0b" label="Pending" value={summary.pending_count} />
            <StatCard icon={AlertTriangle} color="#ef4444" label="On Hold" value={summary.hold_count} />
            <StatCard icon={Boxes} color="#3b82f6" label="Total Boxes" value={summary.total_boxes} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <StatCard icon={DollarSign} color="#8b5cf6" label="Transport Charges" value={fmt(summary.total_transport_charges)} />
            <StatCard icon={Users} color="#06b6d4" label="Porter Charges" value={fmt(summary.total_porter_charges)} />
          </div>

          {summary.transport_breakdown?.length > 0 && (
            <div className="bg-white rounded-xl border border-slate-200 p-4">
              <h3 className="text-sm font-semibold text-slate-700 mb-3">Transport Breakdown (Today)</h3>
              <div className="space-y-2">
                {summary.transport_breakdown.map((t, i) => (
                  <div key={i} className="flex items-center justify-between py-1.5 border-b border-slate-50 last:border-0">
                    <span className="text-xs text-slate-700 font-medium">{t.name || 'Unknown'}</span>
                    <div className="flex gap-4 text-xs text-slate-500">
                      <span>{t.count} dispatches</span>
                      <span className="font-medium text-slate-700">{fmt(t.charges)}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {summary.employee_breakdown?.length > 0 && (
            <div className="bg-white rounded-xl border border-slate-200 p-4">
              <h3 className="text-sm font-semibold text-slate-700 mb-3">Employee Performance (Today)</h3>
              <div className="space-y-2">
                {summary.employee_breakdown.map((e, i) => (
                  <div key={i} className="flex items-center justify-between py-1.5 border-b border-slate-50 last:border-0">
                    <span className="text-xs text-slate-700 font-medium">{e.name?.split('@')[0] || 'Unassigned'}</span>
                    <span className="text-xs font-bold text-blue-600">{e.count} dispatches</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Pending Tab */}
      {tab === 'pending' && (
        <div className="space-y-2">
          {pendingCards.length === 0 && <p className="text-center text-sm text-slate-400 py-10">No pending dispatch cards</p>}
          {pendingCards.map(c => (
            <div key={c.card_id} className="bg-white rounded-xl border border-slate-200 p-3" data-testid={`pending-${c.card_id}`}>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-2 h-8 rounded-full" style={{ background: STATUS_COLORS[c.status] || '#94a3b8' }} />
                  <div>
                    <div className="text-xs font-semibold text-slate-900">{c.invoice_number}</div>
                    <div className="text-[10px] text-slate-500">{c.party_name}</div>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-[10px] px-2 py-0.5 rounded-full font-semibold" style={{ background: (STATUS_COLORS[c.status] || '#94a3b8') + '20', color: STATUS_COLORS[c.status] }}>
                    {c.status?.toUpperCase()}
                  </span>
                  <span className="text-[10px] text-slate-400">@{(c.assigned_to || 'none').split('@')[0]}</span>
                  <button onClick={() => setReassignCard(c.card_id)} className="text-[10px] text-blue-600 hover:underline" data-testid={`reassign-${c.card_id}`}>Reassign</button>
                </div>
              </div>
              {c.notes && <div className="text-[10px] text-slate-400 mt-1 ml-5 italic">{c.notes}</div>}
            </div>
          ))}
        </div>
      )}

      {/* Porters Tab */}
      {tab === 'porters' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-slate-700">Porter Settlement</h3>
            <button onClick={() => setShowAddPorter(true)} className="flex items-center gap-1 text-xs bg-blue-600 text-white px-3 py-1.5 rounded-lg hover:bg-blue-700 transition" data-testid="add-porter-btn">
              <Plus size={13} /> Add Porter
            </button>
          </div>
          <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
            <table className="w-full text-xs">
              <thead className="bg-slate-50 border-b border-slate-200">
                <tr>
                  <th className="px-3 py-2.5 text-left font-semibold text-slate-600">Porter</th>
                  <th className="px-3 py-2.5 text-left font-semibold text-slate-600">Phone</th>
                  <th className="px-3 py-2.5 text-right font-semibold text-slate-600">Dispatches</th>
                  <th className="px-3 py-2.5 text-right font-semibold text-slate-600">Total Charges</th>
                  <th className="px-3 py-2.5 text-right font-semibold text-slate-600">Paid</th>
                  <th className="px-3 py-2.5 text-right font-semibold text-slate-600">Balance Due</th>
                  <th className="px-3 py-2.5 text-center font-semibold text-slate-600">Action</th>
                </tr>
              </thead>
              <tbody>
                {settlement.map((p, i) => (
                  <tr key={i} className="border-b border-slate-50 hover:bg-slate-25" data-testid={`porter-row-${p.porter_id}`}>
                    <td className="px-3 py-2.5 font-medium text-slate-800">{p.name}</td>
                    <td className="px-3 py-2.5 text-slate-500">{p.phone || '-'}</td>
                    <td className="px-3 py-2.5 text-right text-slate-600">{p.dispatch_count}</td>
                    <td className="px-3 py-2.5 text-right text-slate-600">{fmt(p.total_charges)}</td>
                    <td className="px-3 py-2.5 text-right text-green-600">{fmt(p.total_paid)}</td>
                    <td className="px-3 py-2.5 text-right font-bold" style={{ color: p.balance_due > 0 ? '#ef4444' : '#10b981' }}>{fmt(p.balance_due)}</td>
                    <td className="px-3 py-2.5 text-center">
                      {p.balance_due > 0 && (
                        <button onClick={() => { setPayPorter(p.name); setPayAmount(String(p.balance_due)); }}
                          className="text-[10px] text-blue-600 hover:underline" data-testid={`pay-porter-${p.porter_id}`}>Record Payment</button>
                      )}
                    </td>
                  </tr>
                ))}
                {settlement.length === 0 && (
                  <tr><td colSpan={7} className="px-3 py-8 text-center text-slate-400">No porters yet. Add porters to start tracking.</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Employees Tab */}
      {tab === 'employees' && (
        <div className="space-y-3">
          <p className="text-xs text-slate-500">Dispatch employees are created from Setup &gt; Manage Users with role "dispatch".</p>
          {employees.length === 0 && <p className="text-sm text-slate-400 py-8 text-center">No dispatch employees created yet. Go to Setup to add users with "dispatch" role.</p>}
          {employees.map((e, i) => (
            <div key={i} className="bg-white rounded-xl border border-slate-200 p-3 flex items-center gap-3" data-testid={`emp-${e.username}`}>
              <div className="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center"><User size={14} className="text-blue-600" /></div>
              <div>
                <div className="text-xs font-semibold text-slate-900">{e.name || e.username}</div>
                <div className="text-[10px] text-slate-500">{e.username}</div>
              </div>
              <span className="ml-auto text-[10px] bg-blue-50 text-blue-600 px-2 py-0.5 rounded-full font-semibold">dispatch</span>
            </div>
          ))}
        </div>
      )}

      {/* Updates Tab */}
      {tab === 'updates' && (
        <div className="space-y-3" data-testid="app-updates">
          <div className="flex items-center gap-2 mb-2">
            <Megaphone size={16} className="text-blue-600" />
            <h3 className="text-sm font-semibold text-slate-700">FLOWRA Updates & Changelog</h3>
          </div>
          {UPDATES.map((u, i) => {
            const Icon = u.icon;
            return (
              <div key={i} className="bg-white rounded-xl border border-slate-200 p-4 flex items-start gap-3" data-testid={`update-${i}`}>
                <div className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0" style={{ background: u.color + '15' }}>
                  <Icon size={15} style={{ color: u.color }} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-0.5">
                    <span className="text-xs font-bold text-slate-900">{u.title}</span>
                    <span className="text-[9px] px-1.5 py-0.5 rounded-full font-semibold" style={{ background: u.color + '15', color: u.color }}>
                      {u.type === 'feature' ? 'NEW' : u.type === 'bugfix' ? 'FIX' : 'UPDATE'}
                    </span>
                  </div>
                  <p className="text-[11px] text-slate-500 leading-relaxed">{u.desc}</p>
                  <span className="text-[10px] text-slate-400 mt-1 block">{u.date}</span>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Reassign Modal */}
      {reassignCard && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={() => setReassignCard(null)}>
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-sm p-5" onClick={e => e.stopPropagation()}>
            <h3 className="text-sm font-bold text-slate-900 mb-3">Reassign Card</h3>
            <div className="space-y-2">
              {employees.map(e => (
                <button key={e.username} onClick={() => reassign(reassignCard, e.username)}
                  className="w-full text-left px-3 py-2 text-xs bg-slate-50 hover:bg-blue-50 rounded-lg transition" data-testid={`reassign-to-${e.username}`}>
                  {e.name || e.username}
                </button>
              ))}
              {employees.length === 0 && <p className="text-xs text-slate-400 py-4 text-center">No dispatch employees available</p>}
            </div>
            <button onClick={() => setReassignCard(null)} className="mt-3 w-full px-3 py-2 text-xs bg-slate-100 text-slate-700 rounded-lg hover:bg-slate-200 transition">Cancel</button>
          </div>
        </div>
      )}

      {/* Add Porter Modal */}
      {showAddPorter && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={() => setShowAddPorter(false)}>
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-sm p-5" onClick={e => e.stopPropagation()}>
            <h3 className="text-sm font-bold text-slate-900 mb-3">Add Porter</h3>
            <div className="space-y-3">
              <div>
                <label className="text-[10px] font-semibold text-slate-500 uppercase mb-1 block">Name</label>
                <input value={newPorter.name} onChange={e => setNewPorter(p => ({ ...p, name: e.target.value }))} className="w-full px-2.5 py-1.5 text-xs border border-slate-200 rounded-lg" data-testid="porter-name-input" />
              </div>
              <div>
                <label className="text-[10px] font-semibold text-slate-500 uppercase mb-1 block">Phone</label>
                <input value={newPorter.phone} onChange={e => setNewPorter(p => ({ ...p, phone: e.target.value }))} className="w-full px-2.5 py-1.5 text-xs border border-slate-200 rounded-lg" data-testid="porter-phone-input" />
              </div>
            </div>
            <div className="flex gap-2 mt-4">
              <button onClick={() => setShowAddPorter(false)} className="flex-1 px-3 py-2 text-xs bg-slate-100 text-slate-700 rounded-lg">Cancel</button>
              <button onClick={addPorter} className="flex-1 px-3 py-2 text-xs bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition" data-testid="porter-save">Save</button>
            </div>
          </div>
        </div>
      )}

      {/* Pay Porter Modal */}
      {payPorter && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={() => setPayPorter(null)}>
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-sm p-5" onClick={e => e.stopPropagation()}>
            <h3 className="text-sm font-bold text-slate-900 mb-1">Record Payment</h3>
            <p className="text-xs text-slate-500 mb-3">Porter: {payPorter}</p>
            <div className="space-y-3">
              <div>
                <label className="text-[10px] font-semibold text-slate-500 uppercase mb-1 block">Amount</label>
                <input type="number" value={payAmount} onChange={e => setPayAmount(e.target.value)} className="w-full px-2.5 py-1.5 text-xs border border-slate-200 rounded-lg" data-testid="pay-amount" />
              </div>
              <div>
                <label className="text-[10px] font-semibold text-slate-500 uppercase mb-1 block">Payment Reference</label>
                <input value={payRef} onChange={e => setPayRef(e.target.value)} placeholder="Cheque no, UPI ref, etc." className="w-full px-2.5 py-1.5 text-xs border border-slate-200 rounded-lg" data-testid="pay-ref" />
              </div>
            </div>
            <div className="flex gap-2 mt-4">
              <button onClick={() => setPayPorter(null)} className="flex-1 px-3 py-2 text-xs bg-slate-100 text-slate-700 rounded-lg">Cancel</button>
              <button onClick={recordPayment} className="flex-1 px-3 py-2 text-xs bg-green-600 text-white rounded-lg hover:bg-green-700 transition" data-testid="pay-confirm">Confirm Payment</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function StatCard({ icon: Icon, color, label, value }) {
  return (
    <div className="bg-white rounded-xl border border-slate-200 p-3">
      <div className="flex items-center gap-2 mb-1.5">
        <div className="w-6 h-6 rounded-md flex items-center justify-center" style={{ background: color + '15' }}>
          <Icon size={13} style={{ color }} />
        </div>
        <span className="text-[10px] text-slate-500 font-medium">{label}</span>
      </div>
      <div className="text-lg font-bold text-slate-900">{value}</div>
    </div>
  );
}
