import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import {
  Truck, Package, Clock, Users, DollarSign, Boxes, AlertTriangle,
  Plus, User, Calendar, FileDown, Edit2, Trash2, X, ChevronDown
} from 'lucide-react';
import DispatchTerminal from './DispatchTerminal';
import SalesmanOrderApp from './SalesmanOrderApp';

const API = process.env.REACT_APP_BACKEND_URL;
const fmt = n => { if(!n||n===0) return '0'; if(Math.abs(n)>=100000) return `Rs.${(n/100000).toFixed(2)}L`; if(Math.abs(n)>=1000) return `Rs.${(n/1000).toFixed(1)}K`; return `Rs.${n.toLocaleString('en-IN')}`; };
const STATUS_COLORS = { new:'#64748b', queued:'#3b82f6', processing:'#f59e0b', packed:'#8b5cf6', dispatched:'#10b981', info_shared:'#06b6d4', hold:'#ef4444' };
const toIST = iso => { if(!iso) return '-'; try { return new Date(iso).toLocaleString('en-IN', {timeZone:'Asia/Kolkata', day:'2-digit', month:'short', year:'numeric', hour:'2-digit', minute:'2-digit', hour12:true}); } catch { return iso; } };

export default function DispatchAdmin({ selectedFY, companyId, isEmployee = false }) {
  const [tab, setTab] = useState('board');
  const [summary, setSummary] = useState(null);
  const [porterSettlement, setPorterSettlement] = useState([]);
  const [transporterSettlement, setTransporterSettlement] = useState([]);
  const [pendingCards, setPendingCards] = useState([]);
  const [employees, setEmployees] = useState([]);
  const [porters, setPorters] = useState([]);
  const [transporters, setTransporters] = useState([]);
  const [loading, setLoading] = useState(true);
  const [reassignCard, setReassignCard] = useState(null);
  const [settings, setSettings] = useState({});
  const [startDate, setStartDate] = useState('');
  const [filterDate, setFilterDate] = useState(new Date().toISOString().split('T')[0]);
  const [creating, setCreating] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  // Modals
  const [showAddPorter, setShowAddPorter] = useState(false);
  const [showAddTransporter, setShowAddTransporter] = useState(false);
  const [editItem, setEditItem] = useState(null); // {type:'porter'|'transporter', id, name, phone}
  const [np, setNp] = useState({name:'',phone:''});
  const [nt, setNt] = useState({name:'',phone:''});
  const [payTarget, setPayTarget] = useState(null); // {type:'porter'|'transporter', name}
  const [payAmt, setPayAmt] = useState(''); const [payRef, setPayRef] = useState('');

  const hdr = useCallback(() => ({ Authorization: `Bearer ${localStorage.getItem('flowra_token')}`, 'X-Company-Id': companyId||'' }), [companyId]);

  const fetchAll = useCallback(async () => {
    try {
      const [sR,psR,tsR,cR,eR,seR,pR,tR] = await Promise.all([
        axios.get(`${API}/api/dispatch/summary?company_id=${companyId||''}&date=${filterDate}`, {headers:hdr()}),
        axios.get(`${API}/api/dispatch/porter-settlement`, {headers:hdr()}),
        axios.get(`${API}/api/dispatch/transporter-settlement`, {headers:hdr()}),
        axios.get(`${API}/api/dispatch/cards?status=active&company_id=${companyId||''}`, {headers:hdr()}),
        axios.get(`${API}/api/dispatch/employees`, {headers:hdr()}),
        axios.get(`${API}/api/dispatch/settings`, {headers:hdr()}),
        axios.get(`${API}/api/dispatch/porters`, {headers:hdr()}),
        axios.get(`${API}/api/dispatch/transporters`, {headers:hdr()}),
      ]);
      if(sR.data.success) setSummary(sR.data.data);
      if(psR.data.success) setPorterSettlement(psR.data.data.settlement||[]);
      if(tsR.data.success) setTransporterSettlement(tsR.data.data.settlement||[]);
      if(cR.data.success) setPendingCards((cR.data.data.cards||[]).filter(c=>!['dispatched','info_shared'].includes(c.status)));
      if(eR.data.success) setEmployees(eR.data.data.employees||[]);
      if(seR.data.success) { setSettings(seR.data.data||{}); setStartDate(seR.data.data?.start_date||''); }
      if(pR.data.success) setPorters(pR.data.data.porters||[]);
      if(tR.data.success) setTransporters(tR.data.data.transporters||[]);
    } catch(e) { console.error(e); }
    setLoading(false);
  }, [companyId, hdr, filterDate]);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  const autoCreate = async () => {
    if(!startDate) return toast.error('Select a start date first');
    setCreating(true);
    try {
      const r = await axios.post(`${API}/api/dispatch/auto-create`, {from_date: startDate}, {headers:hdr()});
      if(r.data.success) { toast.success(r.data.message); fetchAll(); setRefreshKey(k=>k+1); } else toast.error(r.data.error);
    } catch(e) { toast.error(e.response?.data?.error||'Failed'); }
    setCreating(false);
  };

  const reassign = async (cardId, to) => {
    try {
      const r = await axios.patch(`${API}/api/dispatch/cards/${cardId}/assign`, {assign_to:to}, {headers:hdr()});
      if(r.data.success) { toast.success('Reassigned'); fetchAll(); setReassignCard(null); setRefreshKey(k=>k+1); } else toast.error(r.data.error);
    } catch(e) { toast.error(e.response?.data?.error||'Failed'); }
  };

  // Porter/Transporter CRUD
  const addPorter = async () => {
    if(!np.name.trim()) return toast.error('Name required');
    try { const r=await axios.post(`${API}/api/dispatch/porters`, np, {headers:hdr()}); if(r.data.success){toast.success('Added');setNp({name:'',phone:''});setShowAddPorter(false);fetchAll();}else toast.error(r.data.error); } catch{toast.error('Failed');}
  };
  const addTransporter = async () => {
    if(!nt.name.trim()) return toast.error('Name required');
    try { const r=await axios.post(`${API}/api/dispatch/transporters`, nt, {headers:hdr()}); if(r.data.success){toast.success('Added');setNt({name:'',phone:''});setShowAddTransporter(false);fetchAll();}else toast.error(r.data.error); } catch{toast.error('Failed');}
  };
  const saveEdit = async () => {
    if(!editItem) return;
    const url = editItem.type==='porter' ? `${API}/api/dispatch/porters/${editItem.id}` : `${API}/api/dispatch/transporters/${editItem.id}`;
    try { const r=await axios.patch(url, {name:editItem.name,phone:editItem.phone}, {headers:hdr()}); if(r.data.success){toast.success('Updated');setEditItem(null);fetchAll();}else toast.error(r.data.error); } catch{toast.error('Failed');}
  };
  const deleteItem = async (type, id) => {
    if(!window.confirm(`Delete this ${type}?`)) return;
    const url = type==='porter' ? `${API}/api/dispatch/porters/${id}` : `${API}/api/dispatch/transporters/${id}`;
    try { const r=await axios.delete(url, {headers:hdr()}); if(r.data.success){toast.success('Deleted');fetchAll();}else toast.error(r.data.error); } catch{toast.error('Failed');}
  };
  const recordPay = async () => {
    if(!payTarget||!payAmt) return;
    const url = payTarget.type==='porter' ? `${API}/api/dispatch/porter-payment` : `${API}/api/dispatch/transporter-payment`;
    const nameKey = payTarget.type==='porter' ? 'porter_name' : 'transporter_name';
    try { const r=await axios.post(url, {[nameKey]:payTarget.name,amount:parseFloat(payAmt),payment_ref:payRef},{headers:hdr()}); if(r.data.success){toast.success('Recorded');setPayTarget(null);setPayAmt('');setPayRef('');fetchAll();}else toast.error(r.data.error); } catch{toast.error('Failed');}
  };
  const downloadPdf = () => {
    const url = `${API}/api/dispatch/close-of-day-pdf?date=${filterDate}&company_id=${companyId||''}`;
    const a = document.createElement('a');
    a.href = url;
    a.download = `dispatch_cod_${filterDate}.pdf`;
    // Need auth header, so use fetch
    fetch(url, {headers:hdr()}).then(r=>r.blob()).then(b=>{
      const u = URL.createObjectURL(b); a.href = u; a.click(); URL.revokeObjectURL(u);
    }).catch(()=>toast.error('PDF download failed'));
  };

  const tabs = [
    {id:'board', label:'Kanban Board'},
    {id:'online-orders', label:'Online Orders'},
    {id:'pending-billing', label:'Pending Billing'},
    {id:'overview', label:'Overview'},
    {id:'pending', label:`Pending (${pendingCards.length})`},
    {id:'porters', label:'Porters'},
    {id:'transporters', label:'Transporters'},
    // Employees tab is admin-only — dispatch employees can view their own dispatch board
    // but should not see/manage the employee roster.
    ...(isEmployee ? [] : [{id:'employees', label:'Employees'}]),
  ];

  if(loading) return <div className="flex items-center justify-center h-48"><div className="animate-spin w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full"/></div>;

  return (
    <div data-testid="dispatch-admin">
      <div className="flex flex-col gap-3 mb-4">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2">
          <div>
            <h1 className="text-lg sm:text-xl font-bold text-slate-900">Dispatch Management</h1>
            <p className="text-[11px] text-slate-500 mt-0.5">All dispatch cards are for the latest FY</p>
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            <div className="flex flex-col">
              <label className="text-[9px] text-slate-500 uppercase font-semibold mb-0.5 tracking-wider">Card creation start date</label>
              <div className="flex items-center gap-1.5 bg-slate-50 border border-slate-200 rounded-lg px-2 py-1">
                <Calendar size={13} className="text-slate-400"/>
                <input type="date" value={startDate} onChange={e=>setStartDate(e.target.value)} className="text-xs bg-transparent border-0 outline-none w-28" data-testid="start-date" title="Auto-create dispatch cards from this date forward"/>
              </div>
            </div>
            <button onClick={autoCreate} disabled={creating} className="flex items-center gap-1.5 text-xs bg-blue-600 hover:bg-blue-700 text-white px-3 py-1.5 rounded-lg disabled:opacity-50 self-end" data-testid="auto-create-btn">
              <Package size={13}/>{creating?'Creating...':'Create Cards'}
            </button>
          </div>
        </div>
        {/* Date filter - affects all tabs */}
        <div className="flex items-center gap-2">
          <span className="text-[10px] text-slate-500 font-semibold uppercase">View Date:</span>
          <input type="date" value={filterDate} onChange={e=>{setFilterDate(e.target.value);setRefreshKey(k=>k+1);}} className="text-xs border border-slate-200 rounded-lg px-2 py-1" data-testid="filter-date" title="Filter cards visible on the board"/>
        </div>
      </div>

      {!settings.start_date && <div className="mb-4 bg-amber-50 border border-amber-200 rounded-xl p-3 text-xs text-amber-800" data-testid="setup-notice">
        <strong>First-time setup:</strong> Select a start date and click "Create Cards". Only invoices from this date onward will generate dispatch cards.
      </div>}

      <div className="flex gap-1 mb-4 border-b border-slate-200 overflow-x-auto" data-testid="admin-tabs">
        {tabs.map(t=><button key={t.id} onClick={()=>setTab(t.id)} className={`px-3 sm:px-4 py-2 text-xs font-medium border-b-2 transition whitespace-nowrap ${tab===t.id?'border-blue-600 text-blue-600':'border-transparent text-slate-500 hover:text-slate-700'}`} data-testid={`tab-${t.id}`}>{t.label}</button>)}
      </div>

      {/* KANBAN */}
      {tab==='board' && <DispatchTerminal key={refreshKey} selectedFY={selectedFY} companyId={companyId} filterDate={filterDate}/>}

      {/* ONLINE ORDERS — approved/billed salesman orders */}
      {tab==='online-orders' && <OnlineOrdersTab companyId={companyId} hdr={hdr}/>}

      {/* PENDING BILLING — approved orders with items pending for billing per customer */}
      {tab==='pending-billing' && <PendingBillingTab companyId={companyId} hdr={hdr}/>}

      {/* OVERVIEW */}
      {tab==='overview' && summary && <div className="space-y-4">
        <div className="flex items-center justify-between">
          <span className="text-xs text-slate-500">Summary for <strong>{filterDate}</strong></span>
          <button onClick={downloadPdf} className="flex items-center gap-1.5 text-xs bg-slate-800 hover:bg-slate-900 text-white px-3 py-1.5 rounded-lg" data-testid="cod-pdf-btn">
            <FileDown size={13}/>Close of Day PDF
          </button>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 sm:gap-3">
          <Stat icon={Truck} color="#10b981" label="Dispatched" value={summary.dispatched_count}/>
          <Stat icon={Clock} color="#f59e0b" label="Pending" value={summary.pending_count}/>
          <Stat icon={AlertTriangle} color="#ef4444" label="On Hold" value={summary.hold_count}/>
          <Stat icon={Boxes} color="#3b82f6" label="Total Boxes" value={summary.total_boxes}/>
        </div>
        <div className="grid grid-cols-2 gap-2 sm:gap-3">
          <Stat icon={DollarSign} color="#8b5cf6" label="Transport" value={fmt(summary.total_transport_charges)}/>
          <Stat icon={Users} color="#06b6d4" label="Porter" value={fmt(summary.total_porter_charges)}/>
        </div>
        {summary.transport_breakdown?.length>0 && <div className="bg-white rounded-xl border border-slate-200 p-3"><h3 className="text-xs font-semibold text-slate-700 mb-2">Transport Breakdown</h3>
          {summary.transport_breakdown.map((t,i)=><div key={i} className="flex items-center justify-between py-1.5 border-b border-slate-50 last:border-0 text-xs"><span className="text-slate-700 truncate">{t.name}</span><span className="text-slate-500">{t.count} | {fmt(t.charges)}</span></div>)}</div>}
        {summary.employee_breakdown?.length>0 && <div className="bg-white rounded-xl border border-slate-200 p-3"><h3 className="text-xs font-semibold text-slate-700 mb-2">Employee Performance</h3>
          {summary.employee_breakdown.map((e,i)=><div key={i} className="flex items-center justify-between py-1.5 border-b border-slate-50 last:border-0 text-xs"><span className="text-slate-700">{(e.name||'Unassigned').split('@')[0]}</span><span className="font-bold text-blue-600">{e.count}</span></div>)}</div>}
      </div>}

      {/* PENDING */}
      {tab==='pending' && <div className="space-y-2">
        {pendingCards.length===0 && <p className="text-center text-sm text-slate-400 py-10">No pending cards</p>}
        {pendingCards.map(c=><div key={c.card_id} className="bg-white rounded-xl border border-slate-200 p-2.5 sm:p-3" data-testid={`pending-${c.card_id}`}>
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2 min-w-0">
              <div className="w-1.5 h-7 rounded-full flex-shrink-0" style={{background:STATUS_COLORS[c.status]||'#94a3b8'}}/>
              <div className="min-w-0"><div className="text-xs font-semibold text-slate-900 truncate">{c.invoice_number}</div>
                <div className="text-[10px] text-slate-500 truncate">{c.party_name} {c.voucher_date && <span className="text-slate-400">| {c.voucher_date}</span>}</div></div>
            </div>
            <div className="flex items-center gap-2 flex-shrink-0">
              <span className="text-[9px] px-1.5 py-0.5 rounded-full font-bold" style={{background:(STATUS_COLORS[c.status]||'#94a3b8')+'20',color:STATUS_COLORS[c.status]}}>{c.status?.toUpperCase()}</span>
              <button onClick={()=>setReassignCard(c.card_id)} className="text-[10px] text-blue-600 hover:underline">Reassign</button>
            </div>
          </div>
        </div>)}
      </div>}

      {/* PORTERS */}
      {tab==='porters' && <SettlementTab type="porter" settlement={porterSettlement} items={porters}
        onAdd={()=>setShowAddPorter(true)} onEdit={p=>setEditItem({type:'porter',id:p.porter_id,name:p.name,phone:p.phone})}
        onDelete={id=>deleteItem('porter',id)} onPay={name=>setPayTarget({type:'porter',name})} />}

      {/* TRANSPORTERS */}
      {tab==='transporters' && <SettlementTab type="transporter" settlement={transporterSettlement} items={transporters}
        onAdd={()=>setShowAddTransporter(true)} onEdit={t=>setEditItem({type:'transporter',id:t.transporter_id,name:t.name,phone:t.phone})}
        onDelete={id=>deleteItem('transporter',id)} onPay={name=>setPayTarget({type:'transporter',name})} />}

      {/* EMPLOYEES */}
      {tab==='employees' && <div className="space-y-3">
        <p className="text-xs text-slate-500">Create dispatch employees from Profile &gt; Employees with role "Dispatch".</p>
        {employees.length===0 && <p className="text-sm text-slate-400 py-8 text-center">No dispatch employees yet.</p>}
        {employees.map((e,i)=><div key={i} className="bg-white rounded-xl border border-slate-200 p-3 flex items-center gap-3">
          <div className="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center flex-shrink-0"><User size={14} className="text-blue-600"/></div>
          <div className="min-w-0"><div className="text-xs font-semibold text-slate-900 truncate">{e.name||e.username}</div><div className="text-[10px] text-slate-500 truncate">{e.username}</div></div>
          <span className="ml-auto text-[9px] bg-blue-50 text-blue-600 px-2 py-0.5 rounded-full font-bold flex-shrink-0">dispatch</span>
        </div>)}
      </div>}

      {/* MODALS */}
      {reassignCard && <Modal onClose={()=>setReassignCard(null)} title="Reassign Card">
        {employees.map(e=><button key={e.username} onClick={()=>reassign(reassignCard,e.username)} className="w-full text-left px-3 py-2 text-xs bg-slate-50 hover:bg-blue-50 rounded-lg mb-1">{e.name||e.username}</button>)}
        {employees.length===0 && <p className="text-xs text-slate-400 py-4 text-center">No dispatch employees</p>}
      </Modal>}
      {showAddPorter && <Modal onClose={()=>setShowAddPorter(false)} title="Add Porter">
        <input value={np.name} onChange={e=>setNp(p=>({...p,name:e.target.value}))} placeholder="Name" className="w-full px-2.5 py-1.5 text-xs border border-slate-200 rounded-lg mb-2" data-testid="np-name"/>
        <input value={np.phone} onChange={e=>setNp(p=>({...p,phone:e.target.value}))} placeholder="Phone" className="w-full px-2.5 py-1.5 text-xs border border-slate-200 rounded-lg mb-3" data-testid="np-phone"/>
        <button onClick={addPorter} className="w-full px-3 py-1.5 text-xs bg-blue-600 text-white rounded-lg" data-testid="np-save">Save</button>
      </Modal>}
      {showAddTransporter && <Modal onClose={()=>setShowAddTransporter(false)} title="Add Transporter">
        <input value={nt.name} onChange={e=>setNt(p=>({...p,name:e.target.value}))} placeholder="Name" className="w-full px-2.5 py-1.5 text-xs border border-slate-200 rounded-lg mb-2" data-testid="nt-name"/>
        <input value={nt.phone} onChange={e=>setNt(p=>({...p,phone:e.target.value}))} placeholder="Phone" className="w-full px-2.5 py-1.5 text-xs border border-slate-200 rounded-lg mb-3" data-testid="nt-phone"/>
        <button onClick={addTransporter} className="w-full px-3 py-1.5 text-xs bg-blue-600 text-white rounded-lg" data-testid="nt-save">Save</button>
      </Modal>}
      {editItem && <Modal onClose={()=>setEditItem(null)} title={`Edit ${editItem.type==='porter'?'Porter':'Transporter'}`}>
        <input value={editItem.name} onChange={e=>setEditItem(p=>({...p,name:e.target.value}))} placeholder="Name" className="w-full px-2.5 py-1.5 text-xs border border-slate-200 rounded-lg mb-2" data-testid="edit-name"/>
        <input value={editItem.phone} onChange={e=>setEditItem(p=>({...p,phone:e.target.value}))} placeholder="Phone" className="w-full px-2.5 py-1.5 text-xs border border-slate-200 rounded-lg mb-3" data-testid="edit-phone"/>
        <button onClick={saveEdit} className="w-full px-3 py-1.5 text-xs bg-blue-600 text-white rounded-lg" data-testid="edit-save">Save</button>
      </Modal>}
      {payTarget && <Modal onClose={()=>setPayTarget(null)} title={`Pay ${payTarget.name}`}>
        <input type="number" value={payAmt} onChange={e=>setPayAmt(e.target.value)} placeholder="Amount" className="w-full px-2.5 py-1.5 text-xs border border-slate-200 rounded-lg mb-2" data-testid="pay-amt"/>
        <input value={payRef} onChange={e=>setPayRef(e.target.value)} placeholder="Reference (cheque/UPI)" className="w-full px-2.5 py-1.5 text-xs border border-slate-200 rounded-lg mb-3" data-testid="pay-ref"/>
        <button onClick={recordPay} className="w-full px-3 py-1.5 text-xs bg-green-600 text-white rounded-lg" data-testid="pay-ok">Confirm Payment</button>
      </Modal>}
    </div>
  );
}

function Stat({icon:I,color,label,value}) {
  return <div className="bg-white rounded-xl border border-slate-200 p-2.5 sm:p-3"><div className="flex items-center gap-1.5 mb-1"><div className="w-5 h-5 sm:w-6 sm:h-6 rounded-md flex items-center justify-center" style={{background:color+'15'}}><I size={12} style={{color}}/></div><span className="text-[9px] sm:text-[10px] text-slate-500 font-medium">{label}</span></div><div className="text-base sm:text-lg font-bold text-slate-900">{value}</div></div>;
}

function Modal({onClose, title, children}) {
  return <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={onClose}>
    <div className="bg-white rounded-2xl shadow-2xl w-full max-w-xs p-4" onClick={e=>e.stopPropagation()}>
      <div className="flex items-center justify-between mb-3"><h3 className="text-sm font-bold text-slate-900">{title}</h3><button onClick={onClose}><X size={16} className="text-slate-400"/></button></div>
      {children}
    </div>
  </div>;
}

function SettlementTab({type, settlement, items, onAdd, onEdit, onDelete, onPay}) {
  const label = type==='porter'?'Porter':'Transporter';
  const idKey = type==='porter'?'porter_id':'transporter_id';
  return <div className="space-y-4">
    <div className="flex items-center justify-between"><h3 className="text-xs sm:text-sm font-semibold text-slate-700">{label} Settlement</h3>
      <button onClick={onAdd} className="flex items-center gap-1 text-xs bg-blue-600 text-white px-3 py-1.5 rounded-lg hover:bg-blue-700" data-testid={`add-${type}-btn`}><Plus size={13}/>Add {label}</button></div>
    {/* Master List with edit/delete */}
    <div className="bg-white rounded-xl border border-slate-200 p-3">
      <h4 className="text-[10px] font-semibold text-slate-500 uppercase mb-2">{label} Master List</h4>
      {items.length===0 && <p className="text-xs text-slate-400 py-2 text-center">No {type}s yet</p>}
      <div className="space-y-1">
        {items.map(it=><div key={it[idKey]} className="flex items-center justify-between py-1.5 border-b border-slate-50 last:border-0 text-xs" data-testid={`${type}-${it[idKey]}`}>
          <div><span className="font-medium text-slate-800">{it.name}</span>{it.phone && <span className="text-slate-400 ml-2">{it.phone}</span>}</div>
          <div className="flex items-center gap-1.5">
            <button onClick={()=>onEdit(it)} className="p-1 hover:bg-slate-100 rounded" title="Edit" data-testid={`edit-${type}-${it[idKey]}`}><Edit2 size={12} className="text-slate-400"/></button>
            <button onClick={()=>onDelete(it[idKey])} className="p-1 hover:bg-red-50 rounded" title="Delete" data-testid={`del-${type}-${it[idKey]}`}><Trash2 size={12} className="text-red-400"/></button>
          </div>
        </div>)}
      </div>
    </div>
    {/* Settlement Table */}
    <div className="bg-white rounded-xl border border-slate-200 overflow-x-auto">
      <table className="w-full text-xs min-w-[550px]"><thead className="bg-slate-50 border-b border-slate-200"><tr>
        <th className="px-3 py-2.5 text-left font-semibold text-slate-600">{label}</th>
        <th className="px-3 py-2.5 text-right font-semibold text-slate-600">#</th>
        <th className="px-3 py-2.5 text-right font-semibold text-slate-600">Charges</th>
        <th className="px-3 py-2.5 text-right font-semibold text-slate-600">Paid</th>
        <th className="px-3 py-2.5 text-right font-semibold text-slate-600">Due</th>
        <th className="px-3 py-2.5 text-center font-semibold text-slate-600">Action</th>
      </tr></thead><tbody>
        {settlement.map((p,i)=><tr key={i} className="border-b border-slate-50">
          <td className="px-3 py-2.5 font-medium text-slate-800">{p.name}</td>
          <td className="px-3 py-2.5 text-right text-slate-600">{p.dispatch_count}</td>
          <td className="px-3 py-2.5 text-right text-slate-600">{fmt(p.total_charges)}</td>
          <td className="px-3 py-2.5 text-right text-green-600">{fmt(p.total_paid)}</td>
          <td className="px-3 py-2.5 text-right font-bold" style={{color:p.balance_due>0?'#ef4444':'#10b981'}}>{fmt(p.balance_due)}</td>
          <td className="px-3 py-2.5 text-center">
            <button onClick={()=>onPay(p.name)} className="text-[10px] text-blue-600 hover:underline" data-testid={`pay-${type}-${p.name}`}>Record Payment</button>
          </td>
        </tr>)}
        {settlement.length===0 && <tr><td colSpan={6} className="px-3 py-6 text-center text-slate-400">No settlement data</td></tr>}
      </tbody></table>
    </div>
  </div>;
}

function OnlineOrdersTab({ companyId, hdr }) {
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selOrder, setSelOrder] = useState(null);
  useEffect(() => {
    axios.get(`${API}/api/salesman-orders/orders?company_id=${companyId||''}&limit=100`, {headers:hdr()})
      .then(r => {
        if(r.data.success) {
          const filtered = (r.data.data.orders||[]).filter(o=>['approved','billed','hold'].includes(o.status));
          // Multi-sort:
          //   1. Status priority — Pending (approved/hold) first, Billed last
          //   2. Within each group → created_at DESC (newest first)
          const statusRank = s => (s === 'billed' ? 1 : 0);
          filtered.sort((a, b) => {
            const sr = statusRank(a.status) - statusRank(b.status);
            if (sr !== 0) return sr;
            return String(b.created_at||'').localeCompare(String(a.created_at||''));
          });
          setOrders(filtered);
        }
      })
      .finally(()=>setLoading(false));
  }, [companyId, hdr]);
  const toIST = iso => { if(!iso) return '-'; try { return new Date(iso).toLocaleString('en-IN', {timeZone:'Asia/Kolkata',day:'2-digit',month:'short',hour:'2-digit',minute:'2-digit',hour12:true}); } catch { return iso; } };
  const STATUS_C = { approved:'#3b82f6', billed:'#10b981', hold:'#8b5cf6' };
  if(loading) return <div className="flex items-center justify-center h-24"><div className="animate-spin w-5 h-5 border-2 border-blue-500 border-t-transparent rounded-full"/></div>;
  return <div className="space-y-2" data-testid="online-orders-tab">
    <p className="text-xs text-slate-500 mb-2">Approved, billed, or on-hold salesman orders. Click any card to see line-item details.</p>
    {orders.length===0 && <p className="text-center text-sm text-slate-400 py-10">No online orders</p>}
    {orders.map(o=><button key={o.order_id} onClick={()=>setSelOrder(o)} className="w-full text-left bg-white rounded-xl border border-slate-200 p-3 hover:border-blue-300 hover:shadow-sm transition" data-testid={`online-order-${o.order_id}`}>
      <div className="flex items-center justify-between gap-2">
        <div className="min-w-0">
          <div className="flex items-center gap-2"><span className="text-xs font-mono text-slate-400">{o.order_id}</span>
            <span className="text-[9px] px-1.5 py-0.5 rounded-full font-bold" style={{background:(STATUS_C[o.status]||'#94a3b8')+'20',color:STATUS_C[o.status]||'#94a3b8'}}>{o.status?.toUpperCase()}</span></div>
          <div className="text-sm font-semibold text-slate-900 truncate">{o.customer_name}</div>
          <div className="text-[10px] text-slate-500">by {o.salesman} | {toIST(o.created_at)} | {(o.items||[]).length} item(s)</div>
        </div>
        <div className="text-right flex-shrink-0">
          <div className="text-sm font-bold text-slate-900">Rs.{fmt(o.total_amount)}</div>
          {o.invoice_number && <div className="text-[10px] text-green-600 font-semibold">Inv: {o.invoice_number}</div>}
        </div>
      </div>
    </button>)}
    {selOrder && <OnlineOrderDetailModal order={selOrder} onClose={()=>setSelOrder(null)}/>}
  </div>;
}

function OnlineOrderDetailModal({ order, onClose }) {
  const o = order;
  const toIST = iso => { if(!iso) return '-'; try { return new Date(iso).toLocaleString('en-IN', {timeZone:'Asia/Kolkata',day:'2-digit',month:'short',year:'numeric',hour:'2-digit',minute:'2-digit',hour12:true}); } catch { return iso; } };
  return (
    <div className="fixed inset-0 bg-black/40 z-50 flex items-end sm:items-center justify-center p-0 sm:p-4" onClick={onClose} data-testid="online-order-detail-modal">
      <div className="bg-white w-full sm:max-w-lg rounded-t-2xl sm:rounded-2xl max-h-[92vh] overflow-hidden flex flex-col" onClick={e=>e.stopPropagation()}>
        <div className="flex items-center justify-between px-4 py-3 border-b border-slate-100">
          <div className="min-w-0">
            <div className="flex items-center gap-2 mb-0.5"><span className="text-[10px] font-mono text-slate-400">{o.order_id}</span>
              <span className="text-[9px] px-1.5 py-0.5 rounded-full font-bold bg-blue-50 text-blue-600">{o.status?.toUpperCase()}</span></div>
            <h3 className="text-sm font-semibold text-slate-900 truncate">{o.customer_name}</h3>
          </div>
          <button onClick={onClose} className="p-1.5 hover:bg-slate-100 rounded-lg" data-testid="close-order-modal"><X size={16} className="text-slate-500"/></button>
        </div>
        <div className="overflow-y-auto px-4 py-3 space-y-3 flex-1">
          <div className="grid grid-cols-2 gap-2 text-[11px]">
            <div><span className="text-slate-500">Salesman:</span> <strong>{o.salesman}</strong></div>
            <div><span className="text-slate-500">Created:</span> <strong>{toIST(o.created_at)}</strong></div>
            <div><span className="text-slate-500">Total:</span> <strong className="text-blue-600">Rs.{fmt(o.total_amount)}</strong></div>
            {o.invoice_number && <div><span className="text-slate-500">Invoice:</span> <strong className="text-green-600">{o.invoice_number}</strong></div>}
          </div>
          <div className="border border-slate-200 rounded-lg overflow-hidden">
            <div className="px-3 py-1.5 bg-slate-50 border-b border-slate-200 text-[10px] font-semibold uppercase text-slate-600">Items ({(o.items||[]).length})</div>
            <div className="divide-y divide-slate-100">
              {(o.items||[]).map((it, i) => (
                <div key={i} className="px-3 py-2 flex items-start justify-between gap-2 text-xs">
                  <div className="min-w-0 flex-1">
                    <div className="font-medium text-slate-800 truncate">{it.item_name}</div>
                    {it.part_number && <div className="text-[9px] text-slate-400 font-mono">P/N: {it.part_number}</div>}
                    {it.remark && <div className="text-[10px] text-slate-500 italic">{it.remark}</div>}
                  </div>
                  <div className="text-right flex-shrink-0">
                    <div>x{it.quantity} @ Rs.{it.price}</div>
                    <div className="text-slate-700 font-semibold">Rs.{fmt(it.amount)}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
          {o.notes && <div className="bg-amber-50 border border-amber-100 rounded-lg p-2 text-[11px] text-amber-800"><strong>Salesman note:</strong> {o.notes}</div>}
          {o.admin_notes && <div className="bg-blue-50 border border-blue-100 rounded-lg p-2 text-[11px] text-blue-800"><strong>Admin note:</strong> {o.admin_notes}</div>}
        </div>
      </div>
    </div>
  );
}

function PendingBillingTab({ companyId, hdr }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState({});
  useEffect(() => {
    axios.get(`${API}/api/salesman-orders/pending-billing?company_id=${companyId||''}`, {headers:hdr()})
      .then(r => { if(r.data.success) setData(r.data.data); })
      .finally(()=>setLoading(false));
  }, [companyId, hdr]);

  if(loading) return <div className="flex items-center justify-center h-24"><div className="animate-spin w-5 h-5 border-2 border-blue-500 border-t-transparent rounded-full"/></div>;
  if(!data) return null;

  return <div className="space-y-4" data-testid="pending-billing-tab">
    <div className="flex items-center justify-between">
      <div><p className="text-xs text-slate-500">{data.pending_count} approved orders pending billing</p></div>
    </div>

    {/* Pending billing by customer */}
    {data.pending?.length > 0 && <div>
      <h3 className="text-xs font-semibold text-slate-700 mb-2">Items Pending for Billing (by Customer)</h3>
      <div className="space-y-2">
        {data.pending.map((c, ci) => (
          <div key={ci} className="bg-white rounded-xl border border-slate-200 overflow-hidden" data-testid={`pending-cust-${ci}`}>
            <button onClick={() => setExpanded(e => ({...e, [ci]: !e[ci]}))} className="w-full text-left p-3 flex items-center justify-between hover:bg-slate-50 transition">
              <div>
                <div className="text-sm font-semibold text-slate-900">{c.customer_name}</div>
                <div className="text-[10px] text-slate-500">{c.order_count} orders | {c.items.length} items</div>
              </div>
              <div className="text-right">
                <div className="text-sm font-bold text-amber-600">Rs.{fmt(c.total_amount)}</div>
                <ChevronDown size={14} className={`text-slate-400 transition ${expanded[ci] ? 'rotate-180' : ''}`}/>
              </div>
            </button>
            {expanded[ci] && (
              <div className="border-t border-slate-100 p-3">
                <table className="w-full text-xs">
                  <thead><tr className="text-[10px] text-slate-500 border-b border-slate-100">
                    <th className="text-left py-1.5 font-semibold">Item</th>
                    <th className="text-right py-1.5 font-semibold">Total Qty</th>
                    <th className="text-right py-1.5 font-semibold">Price</th>
                    <th className="text-right py-1.5 font-semibold">Amount</th>
                  </tr></thead>
                  <tbody>
                    {c.items.map((it, ii) => (
                      <tr key={ii} className="border-b border-slate-50">
                        <td className="py-1.5 text-slate-800">{it.item_name}</td>
                        <td className="py-1.5 text-right font-medium">{it.total_qty}</td>
                        <td className="py-1.5 text-right text-slate-500">Rs.{it.price}</td>
                        <td className="py-1.5 text-right font-medium">Rs.{fmt(it.total_qty * it.price)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>}

    {data.pending?.length === 0 && <p className="text-center text-sm text-slate-400 py-6">No orders pending for billing</p>}

    {/* Billed verification */}
    {data.verified?.length > 0 && <div>
      <h3 className="text-xs font-semibold text-slate-700 mb-2">Billed Order Verification (Order vs Tally Invoice)</h3>
      <div className="space-y-1.5">
        {data.verified.map((v, vi) => (
          <div key={vi} className={`bg-white rounded-lg border p-2.5 text-xs ${v.match_status === 'matched' ? 'border-green-200' : v.match_status === 'discrepancy' ? 'border-amber-200' : 'border-slate-200'}`} data-testid={`verified-${vi}`}>
            <div className="flex items-center justify-between">
              <div>
                <span className="font-mono text-slate-400">{v.order_id}</span>
                <span className="text-slate-600 ml-2">{v.customer_name}</span>
                <span className="text-slate-400 ml-2">Inv: {v.invoice_number}</span>
              </div>
              <span className={`text-[9px] px-1.5 py-0.5 rounded-full font-bold ${
                v.match_status === 'matched' ? 'bg-green-100 text-green-700' :
                v.match_status === 'discrepancy' ? 'bg-amber-100 text-amber-700' :
                'bg-slate-100 text-slate-500'
              }`}>{v.match_status === 'matched' ? 'MATCHED' : v.match_status === 'discrepancy' ? 'DISCREPANCY' : 'NOT SYNCED'}</span>
            </div>
            {v.discrepancies?.length > 0 && (
              <div className="mt-1.5 bg-amber-50 rounded p-2">
                {v.discrepancies.map((d, di) => (
                  <div key={di} className="text-[10px] text-amber-800">
                    {d.item_name}: Ordered {d.ordered} → Billed {d.billed} ({d.diff > 0 ? '+' : ''}{d.diff})
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>}
  </div>;
}
