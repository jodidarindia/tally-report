import React, { useState, useEffect, useCallback, useRef } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import {
  Package, Truck, Clock, CheckCircle2, AlertTriangle, Plus, Search,
  Camera, FileText, UploadCloud, X, User, MapPin, Boxes, Hash,
  MessageSquare, Pause, Play, History, ArrowRight, ChevronDown,
  Ban, FileWarning, Calendar,
} from 'lucide-react';
import { fuzzyMatchAny } from '../utils/fuzzySearch';

const API = process.env.REACT_APP_BACKEND_URL;
const STATUS_CFG = {
  new:         { label: 'New',        color: '#64748b', bg: '#f1f5f9' },
  queued:      { label: 'Queued',     color: '#3b82f6', bg: '#eff6ff' },
  processing:  { label: 'Processing', color: '#f59e0b', bg: '#fffbeb' },
  packed:      { label: 'Packed',     color: '#8b5cf6', bg: '#f5f3ff' },
  dispatched:  { label: 'Dispatched', color: '#10b981', bg: '#ecfdf5' },
  info_shared: { label: 'Shared',     color: '#06b6d4', bg: '#ecfeff' },
  hold:        { label: 'Hold',       color: '#ef4444', bg: '#fef2f2' },
  cancelled:   { label: 'Cancelled',  color: '#94a3b8', bg: '#f8fafc' },
};
const LANES = ['new','queued','processing','packed','dispatched'];
const CANCELLABLE = new Set(['new','queued','processing','packed']);
const CANCEL_REASON_LABELS = {
  customer_request:   'Customer requested',
  payment_issue:      'Payment issue',
  stock_unavailable:  'Stock unavailable',
  duplicate:          'Duplicate invoice',
  invoice_modified:   'Tally invoice modified',
  other:              'Other',
};
const fmt = n => { if(!n) return '0'; if(Math.abs(n)>=100000) return `${(n/100000).toFixed(2)}L`; if(Math.abs(n)>=1000) return `${(n/1000).toFixed(1)}K`; return n.toLocaleString('en-IN'); };
const elapsed = iso => { if(!iso) return ''; const m=(Date.now()-new Date(iso).getTime())/60000; if(m<60) return `${Math.round(m)}m`; if(m<1440) return `${Math.round(m/60)}h`; return `${Math.round(m/1440)}d`; };
// "2026-04-15" -> "15 Apr". Falls back to the original string if parsing fails.
const fmtInvDate = (s) => { if(!s) return ''; try { const [y,m,d]=String(s).slice(0,10).split('-'); const mo=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][parseInt(m,10)-1]; return mo ? `${parseInt(d,10)} ${mo}` : s; } catch { return s; } };
const toIST = iso => { if(!iso) return '-'; try { return new Date(iso).toLocaleString('en-IN', {timeZone:'Asia/Kolkata', day:'2-digit', month:'short', hour:'2-digit', minute:'2-digit', hour12:true}); } catch { return iso; } };

export default function DispatchTerminal({ selectedFY, companyId, filterDate }) {
  const [cards, setCards] = useState([]);
  const [porters, setPorters] = useState([]);
  const [transporters, setTransporters] = useState([]);
  const [sel, setSel] = useState(null);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [showManual, setShowManual] = useState(false);
  const [view, setView] = useState('board'); // board | history
  const [hist, setHist] = useState([]); const [histTotal, setHistTotal] = useState(0); const [histPage, setHistPage] = useState(1); const [histQ, setHistQ] = useState('');
  const [histSel, setHistSel] = useState(null); // separate selected card for history view
  const [histInclude, setHistInclude] = useState('completed'); // completed | cancelled | all

  const hdr = useCallback(() => ({ Authorization: `Bearer ${localStorage.getItem('flowra_token')}`, 'X-Company-Id': companyId||'' }), [companyId]);

  const load = useCallback(async () => {
    try {
      const [cr, pr, tr] = await Promise.all([
        axios.get(`${API}/api/dispatch/cards?status=active&company_id=${companyId||''}`, {headers:hdr()}),
        axios.get(`${API}/api/dispatch/porters`, {headers:hdr()}),
        axios.get(`${API}/api/dispatch/transporters`, {headers:hdr()}),
      ]);
      if(cr.data.success) setCards(cr.data.data.cards||[]);
      if(pr.data.success) setPorters(pr.data.data.porters||[]);
      if(tr.data.success) setTransporters(tr.data.data.transporters||[]);
    } catch(e) { console.error(e); }
    setLoading(false);
  }, [companyId, hdr]);

  const loadHist = useCallback(async (pg=1, q='', include='completed') => {
    try {
      const r = await axios.get(`${API}/api/dispatch/history?page=${pg}&limit=30&search=${encodeURIComponent(q)}&include=${include}&company_id=${companyId||''}`, {headers:hdr()});
      if(r.data.success) { setHist(r.data.data.cards||[]); setHistTotal(r.data.data.total||0); setHistPage(pg); }
    } catch{}
  }, [companyId, hdr]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { if(view==='history') loadHist(1, histQ, histInclude); }, [view, loadHist, histQ, histInclude]);
  useEffect(() => { const iv=setInterval(load, 30000); return ()=>clearInterval(iv); }, [load]);

  const moveStatus = async (id, status, extra={}) => {
    try {
      const r = await axios.patch(`${API}/api/dispatch/cards/${id}/status`, {status,...extra}, {headers:hdr()});
      if(r.data.success) { toast.success(r.data.message); load(); setSel(null); } else toast.error(r.data.error);
    } catch(e) { toast.error(e.response?.data?.error||'Failed'); }
  };
  const cancelCard = async (id, reason, notes) => {
    try {
      const r = await axios.post(`${API}/api/dispatch/cards/${id}/cancel`, {reason, notes}, {headers:hdr()});
      if(r.data.success) { toast.success('Card cancelled'); load(); setSel(null); }
      else toast.error(r.data.error);
    } catch(e) { toast.error(e.response?.data?.error||'Cancel failed'); }
  };
  const saveCard = async (id, data) => {
    try { const r = await axios.patch(`${API}/api/dispatch/cards/${id}`, data, {headers:hdr()}); if(r.data.success) { toast.success('Saved'); load(); } else toast.error(r.data.error); } catch{ toast.error('Save failed'); }
  };
  const uploadDoc = async (id, type, file) => {
    const fd=new FormData(); fd.append('file', file);
    try { const r = await axios.post(`${API}/api/dispatch/cards/${id}/upload/${type}`, fd, {headers:{...hdr(),'Content-Type':'multipart/form-data'}}); if(r.data.success) { toast.success('Uploaded to Google Drive'); load(); return r.data.data.drive_view_link || r.data.data.url; } else toast.error(r.data.error || 'Upload failed'); } catch(e){ toast.error(e.response?.data?.error || 'Upload failed'); } return null;
  };
  const createManual = async d => {
    try { const r = await axios.post(`${API}/api/dispatch/cards`, d, {headers:hdr()}); if(r.data.success) { toast.success('Card created'); load(); setShowManual(false); } else toast.error(r.data.error); } catch{ toast.error('Failed'); }
  };
  const addPorter = async (name, phone) => {
    try { const r = await axios.post(`${API}/api/dispatch/porters`, {name, phone}, {headers:hdr()}); if(r.data.success) { toast.success('Porter added'); load(); return r.data.data.name; } else toast.error(r.data.error); } catch{ toast.error('Failed'); } return null;
  };
  const addTransporter = async (name, phone) => {
    try { const r = await axios.post(`${API}/api/dispatch/transporters`, {name, phone}, {headers:hdr()}); if(r.data.success) { toast.success('Transporter added'); load(); return r.data.data.name; } else toast.error(r.data.error); } catch{ toast.error('Failed'); } return null;
  };

  const filtered = search ? cards.filter(c => fuzzyMatchAny(search, [c.party_name, c.invoice_number, c.card_id, c.lr_number, c.transport_name])) : cards;

  // ── HISTORY VIEW ──
  if (view === 'history') return (
    <div className="px-1" data-testid="dispatch-history">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between mb-4 gap-2">
        <div><h1 className="text-lg sm:text-xl font-bold text-slate-900">Dispatch History</h1><p className="text-xs text-slate-500">{histTotal} completed</p></div>
        <button onClick={()=>setView('board')} className="text-xs bg-slate-100 hover:bg-slate-200 text-slate-700 px-3 py-1.5 rounded-lg" data-testid="back-to-board">Back to Board</button>
      </div>
      <div className="flex flex-col sm:flex-row items-start sm:items-center gap-2 mb-3">
        <div className="relative max-w-md flex-1 w-full">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"/>
          <input value={histQ} onChange={e=>{setHistQ(e.target.value);loadHist(1,e.target.value,histInclude);}} placeholder="Search invoice, party, LR..." className="w-full pl-9 pr-3 py-2 text-sm border border-slate-200 rounded-lg" data-testid="history-search"/>
        </div>
        <div className="inline-flex bg-slate-100 rounded-lg p-0.5 text-xs" role="tablist" data-testid="history-filter-tabs">
          {[['completed','Completed'],['cancelled','Cancelled'],['all','All']].map(([k,l]) => (
            <button key={k} onClick={()=>{setHistInclude(k);loadHist(1,histQ,k);}} className={`px-3 py-1.5 rounded-md font-medium transition ${histInclude===k ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500 hover:text-slate-700'}`} data-testid={`history-filter-${k}`}>{l}</button>
          ))}
        </div>
      </div>
      <div className="space-y-2">
        {hist.map(c=>{
          const isCancel = c.status === 'cancelled';
          return (
          <div key={c.card_id} className={`bg-white border rounded-xl p-3 sm:p-4 cursor-pointer hover:border-slate-300 ${isCancel ? 'border-slate-200 opacity-75' : 'border-slate-200'}`} onClick={()=>setHistSel(c)} data-testid={`hist-${c.card_id}`}>
            <div className="flex items-center justify-between gap-2">
              <div className="min-w-0">
                <div className={`text-sm font-semibold text-slate-900 truncate ${isCancel ? 'line-through' : ''}`}>{c.invoice_number}</div>
                <div className="text-xs text-slate-500 truncate">{c.party_name}</div>
              </div>
              <div className="text-right flex-shrink-0">
                {isCancel
                  ? <div className="text-[10px] font-bold text-slate-500 inline-flex items-center gap-1"><Ban size={10}/>CANCELLED</div>
                  : <div className="text-xs text-slate-500">{c.voucher_date||c.created_at?.split('T')[0]}</div>}
                <div className="text-[10px] text-slate-400">LR: {c.lr_number||'-'}</div>
              </div>
            </div>
            <div className="flex flex-wrap gap-x-4 gap-y-1 mt-1.5 text-[10px] text-slate-500">
              {isCancel
                ? <span className="text-slate-600 italic">Reason: {CANCEL_REASON_LABELS[c.cancel_reason]||c.cancel_reason||'Unspecified'}{c.cancelled_by ? ` · by ${c.cancelled_by}` : ''}{c.cancelled_at ? ` · ${toIST(c.cancelled_at)}` : ''}</span>
                : <>
                    <span>Boxes: {c.total_boxes}</span><span>Transport: {c.transport_name||'-'}</span><span>Porter: {c.porter_name||'-'}</span>
                    {c.documents && Object.keys(c.documents).length>0 && <span className="text-green-600">{Object.keys(c.documents).length} docs</span>}
                  </>}
            </div>
          </div>);
        })}
        {hist.length===0 && <p className="text-center text-sm text-slate-400 py-10">No {histInclude==='cancelled'?'cancelled cards':histInclude==='all'?'history':'dispatches'} found</p>}
      </div>
      {histTotal>30 && <div className="flex justify-center gap-2 mt-4"><button disabled={histPage<=1} onClick={()=>loadHist(histPage-1,histQ,histInclude)} className="px-3 py-1 text-xs bg-slate-100 rounded disabled:opacity-40">Prev</button><span className="text-xs text-slate-500 py-1">Page {histPage}</span><button disabled={histPage*30>=histTotal} onClick={()=>loadHist(histPage+1,histQ,histInclude)} className="px-3 py-1 text-xs bg-slate-100 rounded disabled:opacity-40">Next</button></div>}
      {/* History card detail (read-only) */}
      {histSel && <HistoryDetailModal card={histSel} onClose={()=>setHistSel(null)}/>}
    </div>
  );

  // ── KANBAN BOARD ──
  return (
    <div className="px-1" data-testid="dispatch-terminal">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 mb-4">
        <div><h1 className="text-lg sm:text-xl font-bold text-slate-900">Dispatch Terminal</h1><p className="text-xs text-slate-500">{cards.length} active cards</p></div>
        <div className="flex items-center gap-2 flex-wrap">
          <div className="relative"><Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400"/>
            <input value={search} onChange={e=>setSearch(e.target.value)} placeholder="Search..." className="pl-8 pr-3 py-1.5 text-xs border border-slate-200 rounded-lg w-36 sm:w-44" data-testid="dispatch-search"/></div>
          <button onClick={()=>setView('history')} className="flex items-center gap-1 text-xs bg-slate-100 hover:bg-slate-200 text-slate-700 px-3 py-1.5 rounded-lg" data-testid="history-btn"><History size={13}/>History</button>
          <button onClick={()=>setShowManual(true)} className="flex items-center gap-1 text-xs bg-blue-600 hover:bg-blue-700 text-white px-3 py-1.5 rounded-lg" data-testid="manual-btn"><Plus size={13}/>Manual Card</button>
        </div>
      </div>

      {loading ? <div className="flex items-center justify-center h-48"><div className="animate-spin w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full"/></div> : (
        <div className="flex gap-2 sm:gap-3 overflow-x-auto pb-4 -mx-1 px-1" data-testid="kanban-board">
          {LANES.map(status => {
            const cfg = STATUS_CFG[status];
            // Active cards in this lane + cancelled cards whose pre-cancel
            // lane was this one (shown with strikethrough until end-of-day —
            // backend already filters out older cancelled cards).
            // v9.8.27: backend now sorts by (voucher_date, voucher_id,
            // created_at) DESC for every lane, so no client-side resort
            // needed — the order is identical and predictable across lanes.
            const lane = filtered.filter(c =>
              c.status === status
              || (c.status === 'cancelled' && (c.cancelled_from_status || 'new') === status)
            );
            return (
              <div key={status} className="min-w-[220px] sm:min-w-[260px] w-[220px] sm:w-[260px] flex-shrink-0 rounded-xl border border-slate-200 flex flex-col" style={{background: cfg.bg+'60'}} data-testid={`lane-${status}`}>
                <div className="p-2.5 sm:p-3 border-b flex items-center gap-2" style={{borderColor: cfg.color+'30'}}>
                  <div className="w-2.5 h-2.5 rounded-full" style={{background: cfg.color}}/>
                  <span className="text-xs font-bold" style={{color: cfg.color}}>{cfg.label}</span>
                  <span className="ml-auto text-[10px] font-bold px-1.5 py-0.5 rounded-full" style={{background: cfg.color+'20', color: cfg.color}}>{lane.length}</span>
                </div>
                <div className="flex-1 overflow-y-auto p-1.5 sm:p-2 space-y-1.5 max-h-[60vh] sm:max-h-[68vh]">
                  {lane.map(card => {
                    const isCancel = card.status === 'cancelled';
                    const changed = card.invoice_changed_flag;
                    const missing = card.invoice_missing_flag;
                    return (
                    <div key={card.card_id} onClick={()=>setSel(card)} className={`bg-white rounded-lg border p-2 sm:p-2.5 cursor-pointer hover:shadow-md hover:border-blue-300 transition-all ${isCancel ? 'border-slate-200 opacity-60 line-through' : (missing ? 'border-red-300 ring-1 ring-red-100' : changed ? 'border-amber-300 ring-1 ring-amber-100' : 'border-slate-200/80')}`} data-testid={`card-${card.card_id}`}>
                      <div className="flex items-center justify-between mb-0.5">
                        <span className="text-[9px] font-mono text-slate-400 truncate">{card.card_id}</span>
                        <div className="flex items-center gap-1 flex-shrink-0">
                          {missing && <span className="text-[8px] bg-red-100 text-red-700 px-1 rounded font-bold flex items-center gap-0.5" title="Tally invoice no longer exists"><FileWarning size={9}/>MISSING</span>}
                          {changed && !missing && <span className="text-[8px] bg-amber-100 text-amber-700 px-1 rounded font-bold flex items-center gap-0.5" title="Tally invoice was modified after sync"><AlertTriangle size={9}/>CHANGED</span>}
                          {isCancel && <span className="text-[8px] bg-slate-200 text-slate-600 px-1 rounded font-bold flex items-center gap-0.5"><Ban size={9}/>CANCELLED</span>}
                          {card.card_type==='manual' && <span className="text-[8px] bg-amber-100 text-amber-700 px-1 rounded font-bold">MAN</span>}
                        </div>
                      </div>
                      <div className="text-[11px] sm:text-xs font-semibold text-slate-800 truncate">{card.party_name||'Unknown'}</div>
                      <div className="text-[10px] text-slate-500 truncate flex items-center justify-between gap-1">
                        <span className="truncate">Inv: {card.invoice_number}</span>
                        {card.voucher_date && <span className="text-slate-400 flex items-center gap-0.5 flex-shrink-0" data-testid={`card-invoice-date-${card.card_id}`}><Calendar size={9}/>{fmtInvDate(card.voucher_date)}</span>}
                      </div>
                      {card.total_amount>0 && <div className="text-[10px] font-medium text-slate-600 mt-0.5">Rs.{fmt(card.total_amount)}</div>}
                      {isCancel && card.cancel_reason && <div className="text-[9px] text-slate-500 italic mt-0.5 no-underline" style={{textDecoration:'none'}}>{CANCEL_REASON_LABELS[card.cancel_reason]||card.cancel_reason}</div>}
                      <div className="flex items-center justify-between mt-1">
                        <span
                          className={`text-[9px] truncate ${card.assigned_to ? 'text-slate-400' : 'text-amber-600 font-medium'}`}
                          title={card.assigned_to
                            ? `Assigned to dispatch employee ${card.assigned_to}`
                            : 'No dispatch employee assigned — open the card to assign one'}
                        >
                          {card.assigned_to ? `@${card.assigned_to.split('@')[0]}` : 'No employee assigned'}
                        </span>
                        <span className="text-[9px] text-slate-400 flex items-center gap-0.5"><Clock size={9}/>{elapsed(card.status_history?.[card.status_history.length-1]?.at)}</span>
                      </div>
                    </div>
                    );
                  })}
                  {lane.length===0 && <p className="text-center text-[10px] text-slate-300 py-8">No cards</p>}
                </div>
              </div>
            );
          })}
          {/* Hold lane */}
          {(()=>{ const h=filtered.filter(c=>c.status==='hold'); if(!h.length) return null; return (
            <div className="min-w-[220px] sm:min-w-[260px] w-[220px] sm:w-[260px] flex-shrink-0 rounded-xl border border-red-200 flex flex-col" style={{background:'#fef2f2'}} data-testid="lane-hold">
              <div className="p-2.5 sm:p-3 border-b border-red-200 flex items-center gap-2"><div className="w-2.5 h-2.5 rounded-full bg-red-500"/><span className="text-xs font-bold text-red-600">Hold</span><span className="ml-auto text-[10px] font-bold bg-red-100 text-red-600 px-1.5 py-0.5 rounded-full">{h.length}</span></div>
              <div className="flex-1 overflow-y-auto p-1.5 sm:p-2 space-y-1.5 max-h-[60vh] sm:max-h-[68vh]">
                {h.map(card=>(<div key={card.card_id} onClick={()=>setSel(card)} className="bg-white rounded-lg border border-red-200 p-2 sm:p-2.5 cursor-pointer hover:shadow-md transition-all" data-testid={`card-${card.card_id}`}>
                  <div className="text-[11px] font-semibold text-slate-800 truncate">{card.party_name}</div><div className="text-[10px] text-slate-500">Inv: {card.invoice_number}</div>
                  <div className="text-[10px] text-red-500 mt-1">{card.status_history?.slice().reverse().find(h=>h.reason)?.reason||'On hold'}</div></div>))}
              </div>
            </div>); })()}
        </div>
      )}

      {sel && <CardModal card={sel} porters={porters} transporters={transporters} onClose={()=>{setSel(null);load();}} onMove={moveStatus} onCancel={cancelCard} onSave={saveCard} onUpload={uploadDoc} onAddPorter={addPorter} onAddTransporter={addTransporter}/>}
      {showManual && <ManualModal onClose={()=>setShowManual(false)} onCreate={createManual}/>}
    </div>
  );
}

/* ═══ Card Detail Modal ═══ */
function CardModal({ card, porters, transporters, onClose, onMove, onCancel, onSave, onUpload, onAddPorter, onAddTransporter }) {
  const [boxes, setBoxes] = useState(card.total_boxes||0);
  const [transport, setTransport] = useState(card.transport_name||'');
  const [tCharges, setTCharges] = useState(card.transport_charges||0);
  const [porter, setPorter] = useState(card.porter_name||'');
  const [pCharges, setPCharges] = useState(card.porter_charges||0);
  const [lr, setLr] = useState(card.lr_number||'');
  const [city, setCity] = useState(card.destination_city||'');
  const [notes, setNotes] = useState(card.notes||'');
  const [phys, setPhys] = useState(card.physical_check||false);
  const [saving, setSaving] = useState(false);
  const [showNewPorter, setShowNewPorter] = useState(false);
  const [showNewTransporter, setShowNewTransporter] = useState(false);
  const [npName, setNpName] = useState(''); const [npPhone, setNpPhone] = useState('');
  const [ntName, setNtName] = useState(''); const [ntPhone, setNtPhone] = useState('');
  const [showCancel, setShowCancel] = useState(false);

  const cfg = STATUS_CFG[card.status]||STATUS_CFG.new;
  const isCancelled = card.status === 'cancelled';
  const canCancel = CANCELLABLE.has(card.status);
  const next = isCancelled ? null : {new:'queued',queued:'processing',processing:'packed',packed:'dispatched',dispatched:'info_shared'}[card.status];

  const save = async () => {
    setSaving(true);
    await onSave(card.card_id, { total_boxes:parseInt(boxes)||0, transport_name:transport, transport_charges:parseFloat(tCharges)||0, porter_name:porter, porter_charges:parseFloat(pCharges)||0, lr_number:lr, destination_city:city, notes, physical_check:phys });
    setSaving(false);
  };
  const handleFile = async (type, e) => { const f=e.target.files?.[0]; if(f) await onUpload(card.card_id, type, f); };

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/40 p-0 sm:p-4" onClick={onClose} data-testid="card-modal">
      <div className="bg-white rounded-t-2xl sm:rounded-2xl shadow-2xl w-full sm:max-w-2xl max-h-[92vh] sm:max-h-[90vh] overflow-y-auto" onClick={e=>e.stopPropagation()}>
        <div className="p-3 sm:p-4 border-b border-slate-100 flex items-center justify-between sticky top-0 bg-white rounded-t-2xl z-10">
          <div className="flex items-center gap-2 min-w-0">
            <div className="w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0" style={{background:cfg.bg}}>
              <div className="w-2.5 h-2.5 rounded-full" style={{background:cfg.color}}/></div>
            <div className="min-w-0"><div className="text-sm font-bold text-slate-900 truncate">{card.invoice_number}</div>
              <div className="text-[10px] text-slate-500">{card.card_id} <span className="font-semibold" style={{color:cfg.color}}>{cfg.label}</span></div></div>
          </div>
          <button onClick={onClose} className="p-1.5 hover:bg-slate-100 rounded-lg"><X size={18} className="text-slate-400"/></button>
        </div>
        <div className="p-3 sm:p-4 space-y-3">
          {/* Invoice change banner — Option B (flag-only, manual reconcile) */}
          {card.invoice_missing_flag && !isCancelled && (
            <div className="flex items-start gap-2 bg-red-50 border border-red-200 rounded-lg p-2.5" data-testid="banner-invoice-missing">
              <FileWarning size={14} className="text-red-600 flex-shrink-0 mt-0.5"/>
              <div className="text-[11px] text-red-800 leading-tight">
                <strong>Tally invoice deleted.</strong> The source invoice no longer exists in Tally
                {card.invoice_change_detected_at ? ` (detected ${toIST(card.invoice_change_detected_at)})` : ''}.
                Verify with accounts before proceeding — you may want to cancel this card.
              </div>
            </div>
          )}
          {card.invoice_changed_flag && !card.invoice_missing_flag && !isCancelled && (
            <div className="flex items-start gap-2 bg-amber-50 border border-amber-200 rounded-lg p-2.5" data-testid="banner-invoice-changed">
              <AlertTriangle size={14} className="text-amber-600 flex-shrink-0 mt-0.5"/>
              <div className="text-[11px] text-amber-800 leading-tight">
                <strong>Tally invoice modified after sync.</strong>
                {Array.isArray(card.detected_changes) && card.detected_changes.length > 0 && (
                  <span> Changes: {card.detected_changes.map(d => d.field).join(', ')}.</span>
                )}
                {' '}Items / total above show the original snapshot — refresh in Tally and reconcile manually.
              </div>
            </div>
          )}
          {card.post_dispatch_invoice_changed && (
            <div className="flex items-start gap-2 bg-red-50 border border-red-200 rounded-lg p-2.5" data-testid="banner-post-dispatch-changed">
              <AlertTriangle size={14} className="text-red-600 flex-shrink-0 mt-0.5"/>
              <div className="text-[11px] text-red-800 leading-tight">
                <strong>Tally invoice was modified AFTER dispatch.</strong> Goods have already shipped — escalate to accounts immediately.
              </div>
            </div>
          )}
          {isCancelled && (
            <div className="flex items-start gap-2 bg-slate-100 border border-slate-300 rounded-lg p-2.5" data-testid="banner-cancelled">
              <Ban size={14} className="text-slate-600 flex-shrink-0 mt-0.5"/>
              <div className="text-[11px] text-slate-700 leading-tight">
                <strong>Card cancelled</strong>{card.cancelled_at ? ` ${toIST(card.cancelled_at)}` : ''}{card.cancelled_by ? ` by ${card.cancelled_by}` : ''}.
                {' '}Reason: <strong>{CANCEL_REASON_LABELS[card.cancel_reason] || card.cancel_reason || 'Unspecified'}</strong>.
                {card.cancel_notes && <div className="mt-1 italic">"{card.cancel_notes}"</div>}
              </div>
            </div>
          )}
          {/* Party + Amount */}
          <div className="grid grid-cols-2 gap-2">
            <div className="bg-slate-50 rounded-lg p-2.5"><div className="text-[9px] text-slate-400 uppercase font-semibold">Party</div><div className="text-xs sm:text-sm font-semibold text-slate-900 truncate">{card.party_name||'-'}</div></div>
            <div className="bg-slate-50 rounded-lg p-2.5"><div className="text-[9px] text-slate-400 uppercase font-semibold">Amount</div><div className="text-xs sm:text-sm font-semibold text-slate-900">Rs.{fmt(card.total_amount)}</div></div>
          </div>
          {/* Items */}
          {card.items?.length>0 && <div className="border border-slate-200 rounded-lg"><div className="p-2 bg-slate-50 text-[9px] font-semibold text-slate-600 uppercase border-b">Items ({card.items.length})</div>
            <div className="max-h-24 overflow-y-auto">{card.items.map((it,i)=><div key={i} className="px-2.5 py-1 text-[11px] text-slate-700 border-b border-slate-50 flex justify-between"><span className="truncate mr-2">{it.item||it.item_name||'-'}</span><span className="text-slate-500 flex-shrink-0">x{it.quantity||0}</span></div>)}</div></div>}

          {/* Fields */}
          <div className="grid grid-cols-2 gap-2">
            <Inp icon={<Boxes size={12}/>} label="Total Boxes" value={boxes} set={setBoxes} type="number" tid="f-boxes"/>
            <Inp icon={<MapPin size={12}/>} label="Destination City" value={city} set={setCity} tid="f-city"/>
          </div>
          {/* Transport dropdown + add */}
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="text-[9px] font-semibold text-slate-500 uppercase flex items-center gap-1 mb-1"><Truck size={11}/>Transport</label>
              <div className="flex gap-1">
                <select value={transport} onChange={e=>setTransport(e.target.value)} className="flex-1 px-2 py-1.5 text-xs border border-slate-200 rounded-lg" data-testid="f-transport">
                  <option value="">Select</option>
                  {transporters.filter(t=>t.is_active).map(t=><option key={t.transporter_id} value={t.name}>{t.name}</option>)}
                </select>
                <button onClick={()=>setShowNewTransporter(true)} className="px-2 py-1 text-xs bg-slate-100 hover:bg-slate-200 rounded-lg" title="Add new"><Plus size={13}/></button>
              </div>
            </div>
            <Inp icon={<Hash size={12}/>} label="Transport Charges" value={tCharges} set={setTCharges} type="number" tid="f-tcharges"/>
          </div>
          {/* Porter dropdown + add */}
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="text-[9px] font-semibold text-slate-500 uppercase flex items-center gap-1 mb-1"><User size={11}/>Porter</label>
              <div className="flex gap-1">
                <select value={porter} onChange={e=>setPorter(e.target.value)} className="flex-1 px-2 py-1.5 text-xs border border-slate-200 rounded-lg" data-testid="f-porter">
                  <option value="">Select</option>
                  {porters.filter(p=>p.is_active).map(p=><option key={p.porter_id} value={p.name}>{p.name}</option>)}
                </select>
                <button onClick={()=>setShowNewPorter(true)} className="px-2 py-1 text-xs bg-slate-100 hover:bg-slate-200 rounded-lg" title="Add new"><Plus size={13}/></button>
              </div>
            </div>
            <Inp icon={<Hash size={12}/>} label="Porter Charges" value={pCharges} set={setPCharges} type="number" tid="f-pcharges"/>
          </div>
          {/* LR */}
          <Inp icon={<FileText size={12}/>} label="LR / Transport Receipt No." value={lr} set={setLr} tid="f-lr" full/>
          {/* Notes */}
          <div><label className="text-[9px] font-semibold text-slate-500 uppercase mb-1 block">Notes</label>
            <textarea value={notes} onChange={e=>setNotes(e.target.value)} rows={2} className="w-full px-2.5 py-1.5 text-xs border border-slate-200 rounded-lg resize-none" data-testid="f-notes"/></div>
          {/* Docs */}
          <div className="border border-slate-200 rounded-lg p-2.5"><div className="text-[9px] font-semibold text-slate-500 uppercase mb-2">Documents</div>
            <div className="grid grid-cols-3 gap-2">
              <DocSlot label="Invoice Doc" type="invoice_doc" doc={card.documents?.invoice_doc} onUpload={handleFile}/>
              <DocSlot label="Sales Order" type="sales_order" doc={card.documents?.sales_order} onUpload={handleFile}/>
              <DocSlot label="LR Receipt" type="lr_receipt" doc={card.documents?.lr_receipt} onUpload={handleFile}/>
            </div>
          </div>
          {/* Physical check */}
          <label className="flex items-start gap-2 bg-amber-50 border border-amber-200 rounded-lg p-2.5 cursor-pointer" data-testid="f-phys">
            <input type="checkbox" checked={phys} onChange={e=>setPhys(e.target.checked)} className="w-4 h-4 mt-0.5 text-amber-600 rounded"/>
            <span className="text-[11px] text-amber-800 font-medium leading-tight">I confirm all items in the bill are physically verified and present</span>
          </label>
          {/* Timeline */}
          {card.status_history?.length>0 && <div className="border border-slate-200 rounded-lg p-2.5"><div className="text-[9px] font-semibold text-slate-500 uppercase mb-1.5">Timeline</div>
            <div className="space-y-0.5">{card.status_history.map((h,i)=><div key={i} className="flex items-center gap-1.5 text-[10px]">
              <span className="w-1.5 h-1.5 rounded-full flex-shrink-0" style={{background:STATUS_CFG[h.status]?.color||'#94a3b8'}}/><span className="font-medium text-slate-700">{STATUS_CFG[h.status]?.label||h.status}</span><span className="text-slate-400">{toIST(h.at)}</span><span className="text-slate-400">by {h.by}</span>{h.reason && <span className="text-red-500">({h.reason})</span>}</div>)}</div></div>}
        </div>
        {/* Actions */}
        <div className="p-3 sm:p-4 border-t border-slate-100 flex flex-wrap items-center gap-2 sticky bottom-0 bg-white rounded-b-2xl">
          {!isCancelled && <button onClick={save} disabled={saving} className="px-3 sm:px-4 py-2 text-xs bg-slate-800 text-white rounded-lg hover:bg-slate-900 disabled:opacity-50" data-testid="btn-save">{saving?'Saving...':'Save'}</button>}
          {!isCancelled && card.status!=='hold'&&card.status!=='info_shared' && <button onClick={()=>onMove(card.card_id,'hold',{hold_reason:prompt('Hold reason?')||'Unspecified'})} className="px-3 py-2 text-xs bg-red-50 text-red-600 rounded-lg hover:bg-red-100 flex items-center gap-1" data-testid="btn-hold"><Pause size={12}/>Hold</button>}
          {!isCancelled && card.status==='hold' && <button onClick={()=>onMove(card.card_id,'processing')} className="px-3 py-2 text-xs bg-amber-50 text-amber-700 rounded-lg hover:bg-amber-100 flex items-center gap-1" data-testid="btn-resume"><Play size={12}/>Resume</button>}
          {canCancel && <button onClick={()=>setShowCancel(true)} className="px-3 py-2 text-xs bg-slate-100 text-slate-700 hover:bg-slate-200 rounded-lg flex items-center gap-1" data-testid="btn-cancel"><Ban size={12}/>Cancel Card</button>}
          {next && !isCancelled && <button onClick={async()=>{await save();onMove(card.card_id,next);}} className="ml-auto px-3 sm:px-4 py-2 text-xs bg-blue-600 text-white rounded-lg hover:bg-blue-700 flex items-center gap-1" data-testid="btn-next">{STATUS_CFG[next]?.label}<ArrowRight size={13}/></button>}
          {isCancelled && <button onClick={onClose} className="ml-auto px-3 sm:px-4 py-2 text-xs bg-slate-100 text-slate-700 rounded-lg hover:bg-slate-200" data-testid="btn-close-cancelled">Close</button>}
        </div>
        {/* Inline add porter */}
        {showNewPorter && <InlineAdd title="Add Porter" n={npName} sn={setNpName} p={npPhone} sp={setNpPhone} onSave={async()=>{const r=await onAddPorter(npName,npPhone);if(r){setPorter(r);setShowNewPorter(false);setNpName('');setNpPhone('');}}} onClose={()=>setShowNewPorter(false)}/>}
        {showNewTransporter && <InlineAdd title="Add Transporter" n={ntName} sn={setNtName} p={ntPhone} sp={setNtPhone} onSave={async()=>{const r=await onAddTransporter(ntName,ntPhone);if(r){setTransport(r);setShowNewTransporter(false);setNtName('');setNtPhone('');}}} onClose={()=>setShowNewTransporter(false)}/>}
        {showCancel && <CancelModal cardId={card.card_id} invoiceNumber={card.invoice_number} onClose={()=>setShowCancel(false)} onConfirm={async(reason, notes) => { await onCancel(card.card_id, reason, notes); setShowCancel(false); }}/>}
      </div>
    </div>
  );
}

function Inp({icon,label,value,set,type='text',tid,full}) {
  return <div className={full?'col-span-2':''}><label className="text-[9px] font-semibold text-slate-500 uppercase flex items-center gap-1 mb-1">{icon}{label}</label><input type={type} value={value} onChange={e=>set(e.target.value)} className="w-full px-2 py-1.5 text-xs border border-slate-200 rounded-lg" data-testid={tid}/></div>;
}
function DocSlot({label,type,doc,onUpload}) {
  const ref=useRef();
  return <div className="text-center" data-testid={`doc-${type}`}><div className="text-[9px] text-slate-500 mb-1">{label}</div>
    {doc ? <a href={doc.drive_view_link || `${API}${doc.url}`} target="_blank" rel="noreferrer" className="block p-2 bg-green-50 border border-green-200 rounded-lg text-[9px] text-green-700 hover:bg-green-100"><CheckCircle2 size={14} className="mx-auto mb-0.5"/>Uploaded</a>
    : <button onClick={()=>ref.current?.click()} className="block w-full p-2 bg-slate-50 border border-dashed border-slate-300 rounded-lg text-[9px] text-slate-400 hover:border-blue-400 hover:text-blue-500"><UploadCloud size={14} className="mx-auto mb-0.5"/>Upload</button>}
    <input ref={ref} type="file" accept="image/*,.pdf" className="hidden" onChange={e=>onUpload(type,e)}/></div>;
}
function InlineAdd({title,n,sn,p,sp,onSave,onClose}) {
  return <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/30 p-4" onClick={onClose}><div className="bg-white rounded-xl shadow-xl w-full max-w-xs p-4" onClick={e=>e.stopPropagation()}>
    <h4 className="text-xs font-bold text-slate-900 mb-3">{title}</h4>
    <input value={n} onChange={e=>sn(e.target.value)} placeholder="Name" className="w-full px-2.5 py-1.5 text-xs border border-slate-200 rounded-lg mb-2"/>
    <input value={p} onChange={e=>sp(e.target.value)} placeholder="Phone (optional)" className="w-full px-2.5 py-1.5 text-xs border border-slate-200 rounded-lg mb-3"/>
    <div className="flex gap-2"><button onClick={onClose} className="flex-1 px-3 py-1.5 text-xs bg-slate-100 rounded-lg">Cancel</button><button onClick={onSave} className="flex-1 px-3 py-1.5 text-xs bg-blue-600 text-white rounded-lg">Save</button></div>
  </div></div>;
}
function CancelModal({ cardId, invoiceNumber, onClose, onConfirm }) {
  const [reason, setReason] = useState('customer_request');
  const [notes, setNotes] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const submit = async () => {
    setSubmitting(true);
    try { await onConfirm(reason, notes.trim()); }
    finally { setSubmitting(false); }
  };
  return (
    <div className="fixed inset-0 z-[60] flex items-end sm:items-center justify-center bg-black/40 p-0 sm:p-4" onClick={onClose} data-testid="cancel-modal">
      <div className="bg-white rounded-t-2xl sm:rounded-2xl shadow-2xl w-full sm:max-w-md p-4 sm:p-5" onClick={e => e.stopPropagation()}>
        <div className="flex items-start gap-2 mb-3">
          <div className="w-8 h-8 rounded-full bg-red-50 flex items-center justify-center flex-shrink-0"><Ban size={16} className="text-red-600"/></div>
          <div className="min-w-0">
            <h3 className="text-sm font-bold text-slate-900">Cancel Dispatch Card</h3>
            <p className="text-[11px] text-slate-500 truncate">{invoiceNumber} · {cardId}</p>
          </div>
        </div>
        <p className="text-[11px] text-slate-600 bg-amber-50 border border-amber-100 rounded-lg p-2 mb-3 leading-snug">
          This action is <strong>terminal</strong> — cancelled cards cannot be reopened. They will appear with a strikethrough on the board until end-of-day, then move to History.
        </p>
        <label className="text-[10px] font-semibold text-slate-500 uppercase block mb-1">Reason</label>
        <select value={reason} onChange={e => setReason(e.target.value)} className="w-full px-2.5 py-1.5 text-xs border border-slate-200 rounded-lg mb-3" data-testid="cancel-reason">
          {Object.entries(CANCEL_REASON_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
        <label className="text-[10px] font-semibold text-slate-500 uppercase block mb-1">Notes (optional)</label>
        <textarea value={notes} onChange={e => setNotes(e.target.value)} rows={3} placeholder="Add any context — customer ref, payment status, etc." className="w-full px-2.5 py-1.5 text-xs border border-slate-200 rounded-lg resize-none mb-3" data-testid="cancel-notes"/>
        <div className="flex gap-2">
          <button onClick={onClose} disabled={submitting} className="flex-1 px-3 py-2 text-xs bg-slate-100 text-slate-700 rounded-lg hover:bg-slate-200 disabled:opacity-50" data-testid="cancel-modal-back">Back</button>
          <button onClick={submit} disabled={submitting} className="flex-1 px-3 py-2 text-xs bg-red-600 text-white rounded-lg hover:bg-red-700 flex items-center justify-center gap-1 disabled:opacity-50" data-testid="cancel-modal-confirm">
            {submitting ? 'Cancelling...' : (<><Ban size={12}/>Confirm Cancel</>)}
          </button>
        </div>
      </div>
    </div>
  );
}

function ManualModal({onClose,onCreate}) {
  const [reason,setReason]=useState('sample'); const [party,setParty]=useState(''); const [city,setCity]=useState(''); const [notes,setNotes]=useState('');
  return <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/40 p-0 sm:p-4" onClick={onClose} data-testid="manual-modal"><div className="bg-white rounded-t-2xl sm:rounded-2xl shadow-2xl w-full sm:max-w-md p-4 sm:p-5" onClick={e=>e.stopPropagation()}>
    <h3 className="text-sm font-bold text-slate-900 mb-3">Create Manual Dispatch Card</h3>
    <div className="space-y-2.5">
      <div><label className="text-[9px] font-semibold text-slate-500 uppercase mb-1 block">Reason</label><select value={reason} onChange={e=>setReason(e.target.value)} className="w-full px-2.5 py-1.5 text-xs border border-slate-200 rounded-lg" data-testid="m-reason"><option value="sample">Sample</option><option value="return">Return</option><option value="replacement">Replacement</option><option value="internal_transfer">Internal Transfer</option><option value="other">Other</option></select></div>
      <Inp icon={<User size={12}/>} label="Party Name" value={party} set={setParty} tid="m-party" full/>
      <Inp icon={<MapPin size={12}/>} label="Destination City" value={city} set={setCity} tid="m-city" full/>
      <div><label className="text-[9px] font-semibold text-slate-500 uppercase mb-1 block">Notes</label><textarea value={notes} onChange={e=>setNotes(e.target.value)} rows={2} className="w-full px-2.5 py-1.5 text-xs border border-slate-200 rounded-lg resize-none" data-testid="m-notes"/></div>
    </div>
    <div className="flex gap-2 mt-4"><button onClick={onClose} className="flex-1 px-3 py-2 text-xs bg-slate-100 text-slate-700 rounded-lg">Cancel</button><button onClick={()=>onCreate({reason,party_name:party,destination_city:city,notes})} className="flex-1 px-3 py-2 text-xs bg-blue-600 text-white rounded-lg" data-testid="m-create">Create</button></div>
  </div></div>;
}

/* ═══ History Detail Modal (read-only) ═══ */
function HistoryDetailModal({ card, onClose }) {
  const cfg = STATUS_CFG[card.status] || STATUS_CFG.dispatched;
  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/40 p-0 sm:p-4" onClick={onClose} data-testid="history-detail-modal">
      <div className="bg-white rounded-t-2xl sm:rounded-2xl shadow-2xl w-full sm:max-w-2xl max-h-[92vh] sm:max-h-[90vh] overflow-y-auto" onClick={e=>e.stopPropagation()}>
        <div className="p-3 sm:p-4 border-b border-slate-100 flex items-center justify-between sticky top-0 bg-white rounded-t-2xl z-10">
          <div className="flex items-center gap-2 min-w-0">
            <div className="w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0" style={{background:cfg.bg}}>
              <CheckCircle2 size={14} style={{color:cfg.color}}/></div>
            <div className="min-w-0"><div className="text-sm font-bold text-slate-900 truncate">{card.invoice_number}</div>
              <div className="text-[10px] text-slate-500">{card.card_id} <span className="font-semibold text-green-600">COMPLETED</span></div></div>
          </div>
          <button onClick={onClose} className="p-1.5 hover:bg-slate-100 rounded-lg"><X size={18} className="text-slate-400"/></button>
        </div>
        <div className="p-3 sm:p-4 space-y-3">
          <div className="grid grid-cols-2 gap-2">
            <div className="bg-slate-50 rounded-lg p-2.5"><div className="text-[9px] text-slate-400 uppercase font-semibold">Party</div><div className="text-xs font-semibold text-slate-900 truncate">{card.party_name||'-'}</div></div>
            <div className="bg-slate-50 rounded-lg p-2.5"><div className="text-[9px] text-slate-400 uppercase font-semibold">Amount</div><div className="text-xs font-semibold text-slate-900">Rs.{fmt(card.total_amount)}</div></div>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 text-xs">
            <div><span className="text-[9px] text-slate-400 uppercase font-semibold block">Boxes</span><span className="font-medium">{card.total_boxes||0}</span></div>
            <div><span className="text-[9px] text-slate-400 uppercase font-semibold block">Transport</span><span className="font-medium">{card.transport_name||'-'}</span></div>
            <div><span className="text-[9px] text-slate-400 uppercase font-semibold block">Transport Charges</span><span className="font-medium">Rs.{fmt(card.transport_charges)}</span></div>
            <div><span className="text-[9px] text-slate-400 uppercase font-semibold block">Porter</span><span className="font-medium">{card.porter_name||'-'}</span></div>
            <div><span className="text-[9px] text-slate-400 uppercase font-semibold block">Porter Charges</span><span className="font-medium">Rs.{fmt(card.porter_charges)}</span></div>
            <div><span className="text-[9px] text-slate-400 uppercase font-semibold block">LR Number</span><span className="font-medium text-blue-700">{card.lr_number||'-'}</span></div>
            <div><span className="text-[9px] text-slate-400 uppercase font-semibold block">Destination</span><span className="font-medium">{card.destination_city||'-'}</span></div>
            <div><span className="text-[9px] text-slate-400 uppercase font-semibold block">Assigned To</span><span className="font-medium">{card.assigned_to||'-'}</span></div>
          </div>
          {card.notes && <div><span className="text-[9px] text-slate-400 uppercase font-semibold block mb-1">Notes</span><p className="text-xs text-slate-600 bg-slate-50 rounded-lg p-2">{card.notes}</p></div>}
          {/* Documents */}
          {card.documents && Object.keys(card.documents).length>0 && <div className="border border-slate-200 rounded-lg p-2.5">
            <div className="text-[9px] font-semibold text-slate-500 uppercase mb-2">Documents</div>
            <div className="grid grid-cols-3 gap-2">
              {['invoice_doc','sales_order','lr_receipt'].map(dt=>{
                const doc = card.documents[dt];
                return <div key={dt} className="text-center"><div className="text-[9px] text-slate-500 mb-1">{dt==='invoice_doc'?'Invoice':dt==='sales_order'?'Sales Order':'LR Receipt'}</div>
                  {doc ? <a href={doc.drive_view_link || `${API}${doc.url}`} target="_blank" rel="noreferrer" className="block p-2 bg-green-50 border border-green-200 rounded-lg text-[9px] text-green-700 hover:bg-green-100"><CheckCircle2 size={14} className="mx-auto mb-0.5"/>View</a>
                  : <div className="p-2 bg-slate-50 border border-slate-200 rounded-lg text-[9px] text-slate-400">Not uploaded</div>}
                </div>;
              })}
            </div>
          </div>}
          {/* Items */}
          {card.items?.length>0 && <div className="border border-slate-200 rounded-lg"><div className="p-2 bg-slate-50 text-[9px] font-semibold text-slate-600 uppercase border-b">Items ({card.items.length})</div>
            <div className="max-h-24 overflow-y-auto">{card.items.map((it,i)=><div key={i} className="px-2.5 py-1 text-[11px] text-slate-700 border-b border-slate-50 flex justify-between"><span className="truncate mr-2">{it.item||it.item_name||'-'}</span><span className="text-slate-500 flex-shrink-0">x{it.quantity||0}</span></div>)}</div></div>}
          {/* Timeline */}
          {card.status_history?.length>0 && <div className="border border-slate-200 rounded-lg p-2.5"><div className="text-[9px] font-semibold text-slate-500 uppercase mb-1.5">Timeline</div>
            <div className="space-y-0.5">{card.status_history.map((h,i)=><div key={i} className="flex items-center gap-1.5 text-[10px]">
              <span className="w-1.5 h-1.5 rounded-full flex-shrink-0" style={{background:STATUS_CFG[h.status]?.color||'#94a3b8'}}/><span className="font-medium text-slate-700">{STATUS_CFG[h.status]?.label||h.status}</span><span className="text-slate-400">{toIST(h.at)}</span><span className="text-slate-400">by {h.by}</span>{h.reason && <span className="text-red-500">({h.reason})</span>}</div>)}</div></div>}
        </div>
        <div className="p-3 border-t border-slate-100 sticky bottom-0 bg-white rounded-b-2xl">
          <button onClick={onClose} className="w-full px-4 py-2 text-xs bg-slate-100 text-slate-700 rounded-lg hover:bg-slate-200">Close</button>
        </div>
      </div>
    </div>
  );
}
