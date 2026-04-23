import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import {
  Truck, Package, Clock, Users, DollarSign, Boxes, AlertTriangle,
  CheckCircle2, Search, Plus, X, User, Calendar, ArrowRight
} from 'lucide-react';
import DispatchTerminal from './DispatchTerminal';

const API = process.env.REACT_APP_BACKEND_URL;
const fmt = n => { if(!n||n===0) return '0'; if(Math.abs(n)>=100000) return `Rs.${(n/100000).toFixed(2)}L`; if(Math.abs(n)>=1000) return `Rs.${(n/1000).toFixed(1)}K`; return `Rs.${n.toLocaleString('en-IN')}`; };
const STATUS_COLORS = { new:'#64748b', queued:'#3b82f6', processing:'#f59e0b', packed:'#8b5cf6', dispatched:'#10b981', info_shared:'#06b6d4', hold:'#ef4444' };

export default function DispatchAdmin({ selectedFY, companyId }) {
  const [tab, setTab] = useState('board');
  const [summary, setSummary] = useState(null);
  const [settlement, setSettlement] = useState([]);
  const [pendingCards, setPendingCards] = useState([]);
  const [employees, setEmployees] = useState([]);
  const [loading, setLoading] = useState(true);
  const [reassignCard, setReassignCard] = useState(null);
  const [settings, setSettings] = useState({});
  const [startDate, setStartDate] = useState('');
  const [creating, setCreating] = useState(false);
  // Porter
  const [showAddPorter, setShowAddPorter] = useState(false);
  const [np, setNp] = useState({name:'',phone:''});
  const [payPorter, setPayPorter] = useState(null); const [payAmt, setPayAmt] = useState(''); const [payRef, setPayRef] = useState('');

  const hdr = useCallback(() => ({ Authorization: `Bearer ${localStorage.getItem('flowra_token')}`, 'X-Company-Id': companyId||'' }), [companyId]);

  const fetchAll = useCallback(async () => {
    try {
      const [sR,stR,cR,eR,seR] = await Promise.all([
        axios.get(`${API}/api/dispatch/summary?company_id=${companyId||''}`, {headers:hdr()}),
        axios.get(`${API}/api/dispatch/porter-settlement`, {headers:hdr()}),
        axios.get(`${API}/api/dispatch/cards?status=active&company_id=${companyId||''}`, {headers:hdr()}),
        axios.get(`${API}/api/dispatch/employees`, {headers:hdr()}),
        axios.get(`${API}/api/dispatch/settings`, {headers:hdr()}),
      ]);
      if(sR.data.success) setSummary(sR.data.data);
      if(stR.data.success) setSettlement(stR.data.data.settlement||[]);
      if(cR.data.success) setPendingCards((cR.data.data.cards||[]).filter(c=>!['dispatched','info_shared'].includes(c.status)));
      if(eR.data.success) setEmployees(eR.data.data.employees||[]);
      if(seR.data.success) { setSettings(seR.data.data||{}); setStartDate(seR.data.data?.start_date||''); }
    } catch(e) { console.error(e); }
    setLoading(false);
  }, [companyId, hdr]);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  const autoCreate = async () => {
    if(!startDate) return toast.error('Select a start date first');
    setCreating(true);
    try {
      const r = await axios.post(`${API}/api/dispatch/auto-create`, {from_date: startDate}, {headers:hdr()});
      if(r.data.success) { toast.success(r.data.message); fetchAll(); } else toast.error(r.data.error);
    } catch(e) { toast.error(e.response?.data?.error||'Failed'); }
    setCreating(false);
  };

  const reassign = async (cardId, to) => {
    try {
      const r = await axios.patch(`${API}/api/dispatch/cards/${cardId}/assign`, {assign_to:to}, {headers:hdr()});
      if(r.data.success) { toast.success('Reassigned'); fetchAll(); setReassignCard(null); } else toast.error(r.data.error);
    } catch(e) { toast.error(e.response?.data?.error||'Failed'); }
  };

  const addPorter = async () => {
    if(!np.name.trim()) return toast.error('Name required');
    try { const r = await axios.post(`${API}/api/dispatch/porters`, np, {headers:hdr()}); if(r.data.success){toast.success('Added');setNp({name:'',phone:''});setShowAddPorter(false);fetchAll();}else toast.error(r.data.error); } catch{toast.error('Failed');}
  };
  const recordPay = async () => {
    if(!payPorter||!payAmt) return;
    try { const r=await axios.post(`${API}/api/dispatch/porter-payment`, {porter_name:payPorter,amount:parseFloat(payAmt),payment_ref:payRef},{headers:hdr()}); if(r.data.success){toast.success('Recorded');setPayPorter(null);setPayAmt('');setPayRef('');fetchAll();}else toast.error(r.data.error); } catch{toast.error('Failed');}
  };

  const tabs = [
    {id:'board', label:'Kanban Board'},
    {id:'overview', label:'Overview'},
    {id:'pending', label:`Pending (${pendingCards.length})`},
    {id:'porters', label:'Porters'},
    {id:'employees', label:'Employees'},
  ];

  if(loading) return <div className="flex items-center justify-center h-48"><div className="animate-spin w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full"/></div>;

  return (
    <div data-testid="dispatch-admin">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 mb-4">
        <div><h1 className="text-lg sm:text-xl font-bold text-slate-900">Dispatch Management</h1><p className="text-xs text-slate-500 mt-0.5">Admin dashboard</p></div>
        <div className="flex items-center gap-2 flex-wrap">
          <div className="flex items-center gap-1.5 bg-slate-50 border border-slate-200 rounded-lg px-2 py-1">
            <Calendar size={13} className="text-slate-400"/>
            <input type="date" value={startDate} onChange={e=>setStartDate(e.target.value)} className="text-xs bg-transparent border-0 outline-none w-28" data-testid="start-date"/>
          </div>
          <button onClick={autoCreate} disabled={creating} className="flex items-center gap-1.5 text-xs bg-blue-600 hover:bg-blue-700 text-white px-3 py-1.5 rounded-lg disabled:opacity-50" data-testid="auto-create-btn">
            <Package size={13}/>{creating?'Creating...':'Create Cards'}
          </button>
        </div>
      </div>

      {!settings.start_date && <div className="mb-4 bg-amber-50 border border-amber-200 rounded-xl p-3 text-xs text-amber-800" data-testid="setup-notice">
        <strong>First-time setup:</strong> Select a date above to begin creating dispatch cards. Only invoices from this date onward will generate cards. Older invoices are assumed already dispatched.
      </div>}

      <div className="flex gap-1 mb-4 border-b border-slate-200 overflow-x-auto" data-testid="admin-tabs">
        {tabs.map(t=><button key={t.id} onClick={()=>setTab(t.id)} className={`px-3 sm:px-4 py-2 text-xs font-medium border-b-2 transition whitespace-nowrap ${tab===t.id?'border-blue-600 text-blue-600':'border-transparent text-slate-500 hover:text-slate-700'}`} data-testid={`tab-${t.id}`}>{t.label}</button>)}
      </div>

      {/* KANBAN BOARD TAB */}
      {tab==='board' && <DispatchTerminal selectedFY={selectedFY} companyId={companyId}/>}

      {/* OVERVIEW TAB */}
      {tab==='overview' && summary && <div className="space-y-4">
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 sm:gap-3">
          <Stat icon={Truck} color="#10b981" label="Dispatched Today" value={summary.dispatched_count}/>
          <Stat icon={Clock} color="#f59e0b" label="Pending" value={summary.pending_count}/>
          <Stat icon={AlertTriangle} color="#ef4444" label="On Hold" value={summary.hold_count}/>
          <Stat icon={Boxes} color="#3b82f6" label="Total Boxes" value={summary.total_boxes}/>
        </div>
        <div className="grid grid-cols-2 gap-2 sm:gap-3">
          <Stat icon={DollarSign} color="#8b5cf6" label="Transport Charges" value={fmt(summary.total_transport_charges)}/>
          <Stat icon={Users} color="#06b6d4" label="Porter Charges" value={fmt(summary.total_porter_charges)}/>
        </div>
        {summary.transport_breakdown?.length>0 && <div className="bg-white rounded-xl border border-slate-200 p-3 sm:p-4">
          <h3 className="text-xs sm:text-sm font-semibold text-slate-700 mb-2">Transport (Today)</h3>
          {summary.transport_breakdown.map((t,i)=><div key={i} className="flex items-center justify-between py-1.5 border-b border-slate-50 last:border-0 text-xs"><span className="text-slate-700 font-medium truncate">{t.name}</span><div className="flex gap-3 text-slate-500"><span>{t.count} dispatches</span><span className="font-medium text-slate-700">{fmt(t.charges)}</span></div></div>)}
        </div>}
        {summary.employee_breakdown?.length>0 && <div className="bg-white rounded-xl border border-slate-200 p-3 sm:p-4">
          <h3 className="text-xs sm:text-sm font-semibold text-slate-700 mb-2">Employee Performance (Today)</h3>
          {summary.employee_breakdown.map((e,i)=><div key={i} className="flex items-center justify-between py-1.5 border-b border-slate-50 last:border-0 text-xs"><span className="text-slate-700 font-medium">{(e.name||'Unassigned').split('@')[0]}</span><span className="font-bold text-blue-600">{e.count}</span></div>)}
        </div>}
      </div>}

      {/* PENDING TAB */}
      {tab==='pending' && <div className="space-y-2">
        {pendingCards.length===0 && <p className="text-center text-sm text-slate-400 py-10">No pending cards</p>}
        {pendingCards.map(c=><div key={c.card_id} className="bg-white rounded-xl border border-slate-200 p-2.5 sm:p-3" data-testid={`pending-${c.card_id}`}>
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2 min-w-0">
              <div className="w-1.5 h-7 rounded-full flex-shrink-0" style={{background:STATUS_COLORS[c.status]||'#94a3b8'}}/>
              <div className="min-w-0"><div className="text-xs font-semibold text-slate-900 truncate">{c.invoice_number}</div><div className="text-[10px] text-slate-500 truncate">{c.party_name}</div></div>
            </div>
            <div className="flex items-center gap-2 flex-shrink-0">
              <span className="text-[9px] px-1.5 py-0.5 rounded-full font-bold" style={{background:(STATUS_COLORS[c.status]||'#94a3b8')+'20',color:STATUS_COLORS[c.status]}}>{c.status?.toUpperCase()}</span>
              <span className="text-[10px] text-slate-400 hidden sm:inline">@{(c.assigned_to||'none').split('@')[0]}</span>
              <button onClick={()=>setReassignCard(c.card_id)} className="text-[10px] text-blue-600 hover:underline">Reassign</button>
            </div>
          </div>
        </div>)}
      </div>}

      {/* PORTERS TAB */}
      {tab==='porters' && <div className="space-y-4">
        <div className="flex items-center justify-between"><h3 className="text-xs sm:text-sm font-semibold text-slate-700">Porter Settlement</h3>
          <button onClick={()=>setShowAddPorter(true)} className="flex items-center gap-1 text-xs bg-blue-600 text-white px-3 py-1.5 rounded-lg hover:bg-blue-700" data-testid="add-porter-btn"><Plus size={13}/>Add Porter</button></div>
        <div className="bg-white rounded-xl border border-slate-200 overflow-x-auto">
          <table className="w-full text-xs min-w-[600px]"><thead className="bg-slate-50 border-b border-slate-200"><tr>
            <th className="px-3 py-2.5 text-left font-semibold text-slate-600">Porter</th><th className="px-3 py-2.5 text-left font-semibold text-slate-600">Phone</th>
            <th className="px-3 py-2.5 text-right font-semibold text-slate-600">#</th><th className="px-3 py-2.5 text-right font-semibold text-slate-600">Charges</th>
            <th className="px-3 py-2.5 text-right font-semibold text-slate-600">Paid</th><th className="px-3 py-2.5 text-right font-semibold text-slate-600">Due</th>
            <th className="px-3 py-2.5 text-center font-semibold text-slate-600">Action</th>
          </tr></thead><tbody>
            {settlement.map((p,i)=><tr key={i} className="border-b border-slate-50 hover:bg-slate-25">
              <td className="px-3 py-2.5 font-medium text-slate-800">{p.name}</td><td className="px-3 py-2.5 text-slate-500">{p.phone||'-'}</td>
              <td className="px-3 py-2.5 text-right text-slate-600">{p.dispatch_count}</td><td className="px-3 py-2.5 text-right text-slate-600">{fmt(p.total_charges)}</td>
              <td className="px-3 py-2.5 text-right text-green-600">{fmt(p.total_paid)}</td>
              <td className="px-3 py-2.5 text-right font-bold" style={{color:p.balance_due>0?'#ef4444':'#10b981'}}>{fmt(p.balance_due)}</td>
              <td className="px-3 py-2.5 text-center">{p.balance_due>0 && <button onClick={()=>{setPayPorter(p.name);setPayAmt(String(p.balance_due));}} className="text-[10px] text-blue-600 hover:underline">Pay</button>}</td>
            </tr>)}
            {settlement.length===0 && <tr><td colSpan={7} className="px-3 py-8 text-center text-slate-400">No porters. Add one to start.</td></tr>}
          </tbody></table>
        </div>
      </div>}

      {/* EMPLOYEES TAB */}
      {tab==='employees' && <div className="space-y-3">
        <p className="text-xs text-slate-500">Create dispatch employees from the Manage Users section (Profile &gt; Employees) with role "Dispatch".</p>
        {employees.length===0 && <p className="text-sm text-slate-400 py-8 text-center">No dispatch employees yet.</p>}
        {employees.map((e,i)=><div key={i} className="bg-white rounded-xl border border-slate-200 p-3 flex items-center gap-3" data-testid={`emp-${e.username}`}>
          <div className="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center flex-shrink-0"><User size={14} className="text-blue-600"/></div>
          <div className="min-w-0"><div className="text-xs font-semibold text-slate-900 truncate">{e.name||e.username}</div><div className="text-[10px] text-slate-500 truncate">{e.username}</div></div>
          <span className="ml-auto text-[9px] bg-blue-50 text-blue-600 px-2 py-0.5 rounded-full font-bold flex-shrink-0">dispatch</span>
        </div>)}
      </div>}

      {/* REASSIGN MODAL */}
      {reassignCard && <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={()=>setReassignCard(null)}><div className="bg-white rounded-2xl shadow-2xl w-full max-w-xs p-4" onClick={e=>e.stopPropagation()}>
        <h3 className="text-sm font-bold text-slate-900 mb-3">Reassign Card</h3>
        {employees.map(e=><button key={e.username} onClick={()=>reassign(reassignCard,e.username)} className="w-full text-left px-3 py-2 text-xs bg-slate-50 hover:bg-blue-50 rounded-lg mb-1">{e.name||e.username}</button>)}
        {employees.length===0 && <p className="text-xs text-slate-400 py-4 text-center">No dispatch employees</p>}
        <button onClick={()=>setReassignCard(null)} className="mt-2 w-full px-3 py-2 text-xs bg-slate-100 text-slate-700 rounded-lg">Cancel</button>
      </div></div>}
      {/* ADD PORTER MODAL */}
      {showAddPorter && <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={()=>setShowAddPorter(false)}><div className="bg-white rounded-2xl shadow-2xl w-full max-w-xs p-4" onClick={e=>e.stopPropagation()}>
        <h3 className="text-sm font-bold text-slate-900 mb-3">Add Porter</h3>
        <input value={np.name} onChange={e=>setNp(p=>({...p,name:e.target.value}))} placeholder="Name" className="w-full px-2.5 py-1.5 text-xs border border-slate-200 rounded-lg mb-2" data-testid="np-name"/>
        <input value={np.phone} onChange={e=>setNp(p=>({...p,phone:e.target.value}))} placeholder="Phone" className="w-full px-2.5 py-1.5 text-xs border border-slate-200 rounded-lg mb-3" data-testid="np-phone"/>
        <div className="flex gap-2"><button onClick={()=>setShowAddPorter(false)} className="flex-1 px-3 py-1.5 text-xs bg-slate-100 rounded-lg">Cancel</button><button onClick={addPorter} className="flex-1 px-3 py-1.5 text-xs bg-blue-600 text-white rounded-lg" data-testid="np-save">Save</button></div>
      </div></div>}
      {/* PAY PORTER MODAL */}
      {payPorter && <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={()=>setPayPorter(null)}><div className="bg-white rounded-2xl shadow-2xl w-full max-w-xs p-4" onClick={e=>e.stopPropagation()}>
        <h3 className="text-sm font-bold text-slate-900 mb-1">Record Payment</h3><p className="text-xs text-slate-500 mb-3">{payPorter}</p>
        <input type="number" value={payAmt} onChange={e=>setPayAmt(e.target.value)} placeholder="Amount" className="w-full px-2.5 py-1.5 text-xs border border-slate-200 rounded-lg mb-2" data-testid="pay-amt"/>
        <input value={payRef} onChange={e=>setPayRef(e.target.value)} placeholder="Reference" className="w-full px-2.5 py-1.5 text-xs border border-slate-200 rounded-lg mb-3" data-testid="pay-ref"/>
        <div className="flex gap-2"><button onClick={()=>setPayPorter(null)} className="flex-1 px-3 py-1.5 text-xs bg-slate-100 rounded-lg">Cancel</button><button onClick={recordPay} className="flex-1 px-3 py-1.5 text-xs bg-green-600 text-white rounded-lg" data-testid="pay-ok">Confirm</button></div>
      </div></div>}
    </div>
  );
}

function Stat({icon:I,color,label,value}) {
  return <div className="bg-white rounded-xl border border-slate-200 p-2.5 sm:p-3"><div className="flex items-center gap-1.5 mb-1"><div className="w-5 h-5 sm:w-6 sm:h-6 rounded-md flex items-center justify-center" style={{background:color+'15'}}><I size={12} style={{color}}/></div><span className="text-[9px] sm:text-[10px] text-slate-500 font-medium">{label}</span></div><div className="text-base sm:text-lg font-bold text-slate-900">{value}</div></div>;
}
