import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import {
  Package, Truck, Clock, CheckCircle2, AlertTriangle, Plus, Search,
  ChevronRight, Camera, FileText, UploadCloud, X, User, MapPin,
  Boxes, Hash, MessageSquare, Pause, Play, History, ArrowRight
} from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL;

const STATUS_CFG = {
  new:          { label: 'New',         color: '#64748b', bg: '#f1f5f9', icon: Package },
  queued:       { label: 'Queued',      color: '#3b82f6', bg: '#eff6ff', icon: Clock },
  processing:   { label: 'Processing',  color: '#f59e0b', bg: '#fffbeb', icon: Play },
  packed:       { label: 'Packed',      color: '#8b5cf6', bg: '#f5f3ff', icon: Boxes },
  dispatched:   { label: 'Dispatched',  color: '#10b981', bg: '#ecfdf5', icon: Truck },
  info_shared:  { label: 'Info Shared', color: '#06b6d4', bg: '#ecfeff', icon: CheckCircle2 },
  hold:         { label: 'On Hold',     color: '#ef4444', bg: '#fef2f2', icon: AlertTriangle },
};

const LANES = ['new', 'queued', 'processing', 'packed', 'dispatched'];

const fmt = (n) => {
  if (!n || n === 0) return '0';
  if (Math.abs(n) >= 100000) return `${(n / 100000).toFixed(2)}L`;
  if (Math.abs(n) >= 1000) return `${(n / 1000).toFixed(1)}K`;
  return n.toLocaleString('en-IN');
};

const timeSince = (iso) => {
  if (!iso) return '';
  const diff = (Date.now() - new Date(iso).getTime()) / 60000;
  if (diff < 60) return `${Math.round(diff)}m`;
  if (diff < 1440) return `${Math.round(diff / 60)}h`;
  return `${Math.round(diff / 1440)}d`;
};

export default function DispatchTerminal({ selectedFY, companyId }) {
  const [cards, setCards] = useState([]);
  const [porters, setPorters] = useState([]);
  const [employees, setEmployees] = useState([]);
  const [selectedCard, setSelectedCard] = useState(null);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [showManual, setShowManual] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [historyCards, setHistoryCards] = useState([]);
  const [historySearch, setHistorySearch] = useState('');
  const [historyPage, setHistoryPage] = useState(1);
  const [historyTotal, setHistoryTotal] = useState(0);

  const headers = useCallback(() => {
    const token = localStorage.getItem('flowra_token');
    return {
      Authorization: `Bearer ${token}`,
      'X-Company-Id': companyId || '',
    };
  }, [companyId]);

  const fetchCards = useCallback(async () => {
    try {
      const r = await axios.get(`${API}/api/dispatch/cards?status=active&company_id=${companyId || ''}`, { headers: headers() });
      if (r.data.success) setCards(r.data.data.cards || []);
    } catch (e) { console.error(e); }
    setLoading(false);
  }, [companyId, headers]);

  const fetchPorters = useCallback(async () => {
    try {
      const r = await axios.get(`${API}/api/dispatch/porters`, { headers: headers() });
      if (r.data.success) setPorters(r.data.data.porters || []);
    } catch {}
  }, [headers]);

  const fetchEmployees = useCallback(async () => {
    try {
      const r = await axios.get(`${API}/api/dispatch/employees`, { headers: headers() });
      if (r.data.success) setEmployees(r.data.data.employees || []);
    } catch {}
  }, [headers]);

  const fetchHistory = useCallback(async (pg = 1, q = '') => {
    try {
      const r = await axios.get(`${API}/api/dispatch/history?page=${pg}&limit=30&search=${encodeURIComponent(q)}&company_id=${companyId || ''}`, { headers: headers() });
      if (r.data.success) {
        setHistoryCards(r.data.data.cards || []);
        setHistoryTotal(r.data.data.total || 0);
        setHistoryPage(pg);
      }
    } catch {}
  }, [companyId, headers]);

  useEffect(() => { fetchCards(); fetchPorters(); fetchEmployees(); }, [fetchCards, fetchPorters, fetchEmployees]);
  useEffect(() => { if (showHistory) fetchHistory(1, historySearch); }, [showHistory, fetchHistory, historySearch]);

  // Auto-refresh every 30 seconds
  useEffect(() => {
    const iv = setInterval(fetchCards, 30000);
    return () => clearInterval(iv);
  }, [fetchCards]);

  const updateStatus = async (cardId, status, extra = {}) => {
    try {
      const r = await axios.patch(`${API}/api/dispatch/cards/${cardId}/status`, { status, ...extra }, { headers: headers() });
      if (r.data.success) { toast.success(r.data.message); fetchCards(); setSelectedCard(null); }
      else toast.error(r.data.error);
    } catch (e) { toast.error(e.response?.data?.error || 'Failed'); }
  };

  const updateCard = async (cardId, data) => {
    try {
      const r = await axios.patch(`${API}/api/dispatch/cards/${cardId}`, data, { headers: headers() });
      if (r.data.success) { toast.success('Updated'); fetchCards(); }
      else toast.error(r.data.error);
    } catch (e) { toast.error('Update failed'); }
  };

  const uploadDoc = async (cardId, docType, file) => {
    const fd = new FormData();
    fd.append('file', file);
    try {
      const r = await axios.post(`${API}/api/dispatch/cards/${cardId}/upload/${docType}`, fd, {
        headers: { ...headers(), 'Content-Type': 'multipart/form-data' },
      });
      if (r.data.success) { toast.success(`${docType} uploaded`); fetchCards(); return r.data.data.url; }
      else toast.error(r.data.error);
    } catch (e) { toast.error('Upload failed'); }
    return null;
  };

  const createManual = async (data) => {
    try {
      const r = await axios.post(`${API}/api/dispatch/cards`, data, { headers: headers() });
      if (r.data.success) { toast.success('Manual card created'); fetchCards(); setShowManual(false); }
      else toast.error(r.data.error);
    } catch (e) { toast.error('Create failed'); }
  };

  const filtered = search
    ? cards.filter(c => (c.party_name || '').toLowerCase().includes(search.toLowerCase()) ||
                        (c.invoice_number || '').toLowerCase().includes(search.toLowerCase()) ||
                        (c.card_id || '').toLowerCase().includes(search.toLowerCase()))
    : cards;

  if (showHistory) {
    return (
      <div className="min-h-[80vh]" data-testid="dispatch-history">
        <div className="flex items-center justify-between mb-5">
          <div>
            <h1 className="text-xl font-bold text-slate-900">Dispatch History</h1>
            <p className="text-xs text-slate-500 mt-0.5">{historyTotal} completed dispatches</p>
          </div>
          <button onClick={() => setShowHistory(false)} className="text-xs bg-slate-100 hover:bg-slate-200 text-slate-700 px-3 py-1.5 rounded-lg transition" data-testid="dispatch-history-back">Back to Board</button>
        </div>
        <div className="relative mb-4 max-w-md">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input value={historySearch} onChange={e => { setHistorySearch(e.target.value); fetchHistory(1, e.target.value); }}
            placeholder="Search invoice, party, LR number..." className="w-full pl-9 pr-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-blue-500" data-testid="dispatch-history-search" />
        </div>
        <div className="space-y-2">
          {historyCards.map(c => (
            <div key={c.card_id} className="bg-white border border-slate-200 rounded-xl p-4 hover:border-slate-300 transition cursor-pointer" onClick={() => setSelectedCard(c)} data-testid={`history-card-${c.card_id}`}>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ background: STATUS_CFG[c.status]?.bg }}><Truck size={16} style={{ color: STATUS_CFG[c.status]?.color }} /></div>
                  <div>
                    <div className="text-sm font-semibold text-slate-900">{c.invoice_number}</div>
                    <div className="text-xs text-slate-500">{c.party_name}</div>
                  </div>
                </div>
                <div className="text-right">
                  <div className="text-xs text-slate-500">{c.voucher_date || c.created_at?.split('T')[0]}</div>
                  <div className="text-xs text-slate-400">LR: {c.lr_number || '-'}</div>
                </div>
              </div>
              <div className="flex gap-4 mt-2 text-xs text-slate-500">
                <span>Boxes: {c.total_boxes}</span>
                <span>Transport: {c.transport_name || '-'}</span>
                <span>Porter: {c.porter_name || '-'}</span>
                {c.documents && Object.keys(c.documents).length > 0 && <span className="text-green-600">{Object.keys(c.documents).length} docs</span>}
              </div>
            </div>
          ))}
          {historyCards.length === 0 && <p className="text-center text-sm text-slate-400 py-10">No completed dispatches found</p>}
        </div>
        {historyTotal > 30 && (
          <div className="flex justify-center gap-2 mt-4">
            <button disabled={historyPage <= 1} onClick={() => fetchHistory(historyPage - 1, historySearch)} className="px-3 py-1 text-xs bg-slate-100 rounded disabled:opacity-40">Prev</button>
            <span className="text-xs text-slate-500 py-1">Page {historyPage}</span>
            <button disabled={historyPage * 30 >= historyTotal} onClick={() => fetchHistory(historyPage + 1, historySearch)} className="px-3 py-1 text-xs bg-slate-100 rounded disabled:opacity-40">Next</button>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="min-h-[80vh]" data-testid="dispatch-terminal">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 mb-5">
        <div>
          <h1 className="text-xl font-bold text-slate-900">Dispatch Terminal</h1>
          <p className="text-xs text-slate-500 mt-0.5">{cards.length} active cards</p>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <div className="relative">
            <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400" />
            <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search..." className="pl-8 pr-3 py-1.5 text-xs border border-slate-200 rounded-lg w-44 focus:outline-none focus:ring-1 focus:ring-blue-500" data-testid="dispatch-search" />
          </div>
          <button onClick={() => setShowHistory(true)} className="flex items-center gap-1 text-xs bg-slate-100 hover:bg-slate-200 text-slate-700 px-3 py-1.5 rounded-lg transition" data-testid="dispatch-history-btn">
            <History size={13} /> History
          </button>
          <button onClick={() => setShowManual(true)} className="flex items-center gap-1 text-xs bg-blue-600 hover:bg-blue-700 text-white px-3 py-1.5 rounded-lg transition" data-testid="dispatch-manual-btn">
            <Plus size={13} /> Manual Card
          </button>
        </div>
      </div>

      {/* Kanban Lanes */}
      {loading ? (
        <div className="flex items-center justify-center h-48"><div className="animate-spin w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full" /></div>
      ) : (
        <div className="flex gap-3 overflow-x-auto pb-4" data-testid="dispatch-kanban">
          {LANES.map(status => {
            const cfg = STATUS_CFG[status];
            const Icon = cfg.icon;
            const lane = filtered.filter(c => c.status === status);
            return (
              <div key={status} className="min-w-[260px] w-[260px] flex-shrink-0 bg-slate-50 rounded-xl border border-slate-200 flex flex-col max-h-[70vh]" data-testid={`lane-${status}`}>
                <div className="p-3 border-b border-slate-200 flex items-center gap-2">
                  <div className="w-6 h-6 rounded-md flex items-center justify-center" style={{ background: cfg.bg }}><Icon size={13} style={{ color: cfg.color }} /></div>
                  <span className="text-xs font-semibold text-slate-700">{cfg.label}</span>
                  <span className="ml-auto text-[10px] font-bold px-1.5 py-0.5 rounded-full" style={{ background: cfg.bg, color: cfg.color }}>{lane.length}</span>
                </div>
                <div className="flex-1 overflow-y-auto p-2 space-y-2">
                  {lane.map(card => (
                    <div key={card.card_id} onClick={() => setSelectedCard(card)}
                      className="bg-white rounded-lg border border-slate-200 p-2.5 cursor-pointer hover:border-blue-300 hover:shadow-sm transition" data-testid={`card-${card.card_id}`}>
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-[10px] font-mono text-slate-400">{card.card_id}</span>
                        {card.card_type === 'manual' && <span className="text-[9px] bg-amber-100 text-amber-700 px-1 rounded">MANUAL</span>}
                      </div>
                      <div className="text-xs font-semibold text-slate-800 truncate">{card.party_name || 'Unknown Party'}</div>
                      <div className="text-[10px] text-slate-500 mt-0.5">Inv: {card.invoice_number}</div>
                      {card.total_amount > 0 && <div className="text-[10px] text-slate-500">Rs.{fmt(card.total_amount)}</div>}
                      <div className="flex items-center justify-between mt-1.5">
                        <span className="text-[10px] text-slate-400">{card.assigned_to ? `@${card.assigned_to.split('@')[0]}` : 'Unassigned'}</span>
                        <span className="text-[10px] text-slate-400" title="Time in status">{timeSince(card.status_history?.[card.status_history.length - 1]?.at)}</span>
                      </div>
                    </div>
                  ))}
                  {lane.length === 0 && <p className="text-center text-[10px] text-slate-300 py-6">Empty</p>}
                </div>
              </div>
            );
          })}
          {/* Hold lane */}
          {(() => {
            const holdCards = filtered.filter(c => c.status === 'hold');
            if (holdCards.length === 0) return null;
            const cfg = STATUS_CFG.hold;
            const Icon = cfg.icon;
            return (
              <div className="min-w-[260px] w-[260px] flex-shrink-0 bg-red-50/50 rounded-xl border border-red-200 flex flex-col max-h-[70vh]" data-testid="lane-hold">
                <div className="p-3 border-b border-red-200 flex items-center gap-2">
                  <div className="w-6 h-6 rounded-md flex items-center justify-center" style={{ background: cfg.bg }}><Icon size={13} style={{ color: cfg.color }} /></div>
                  <span className="text-xs font-semibold text-red-700">On Hold</span>
                  <span className="ml-auto text-[10px] font-bold bg-red-100 text-red-600 px-1.5 py-0.5 rounded-full">{holdCards.length}</span>
                </div>
                <div className="flex-1 overflow-y-auto p-2 space-y-2">
                  {holdCards.map(card => (
                    <div key={card.card_id} onClick={() => setSelectedCard(card)}
                      className="bg-white rounded-lg border border-red-200 p-2.5 cursor-pointer hover:border-red-300 hover:shadow-sm transition" data-testid={`card-${card.card_id}`}>
                      <div className="text-xs font-semibold text-slate-800 truncate">{card.party_name}</div>
                      <div className="text-[10px] text-slate-500">Inv: {card.invoice_number}</div>
                      <div className="text-[10px] text-red-500 mt-1">{card.status_history?.slice().reverse().find(h => h.reason)?.reason || 'On hold'}</div>
                    </div>
                  ))}
                </div>
              </div>
            );
          })()}
        </div>
      )}

      {/* Card Detail Modal */}
      {selectedCard && (
        <CardDetailModal card={selectedCard} porters={porters} onClose={() => { setSelectedCard(null); fetchCards(); }}
          onUpdateStatus={updateStatus} onUpdateCard={updateCard} onUploadDoc={uploadDoc} />
      )}

      {/* Manual Card Modal */}
      {showManual && <ManualCardModal onClose={() => setShowManual(false)} onCreate={createManual} />}
    </div>
  );
}

/* ═══════ Card Detail Modal ═══════ */
function CardDetailModal({ card, porters, onClose, onUpdateStatus, onUpdateCard, onUploadDoc }) {
  const [boxes, setBoxes] = useState(card.total_boxes || 0);
  const [transport, setTransport] = useState(card.transport_name || '');
  const [transportCharges, setTransportCharges] = useState(card.transport_charges || 0);
  const [porter, setPorter] = useState(card.porter_name || '');
  const [porterCharges, setPorterCharges] = useState(card.porter_charges || 0);
  const [lrNumber, setLrNumber] = useState(card.lr_number || '');
  const [destCity, setDestCity] = useState(card.destination_city || '');
  const [notes, setNotes] = useState(card.notes || '');
  const [physCheck, setPhysCheck] = useState(card.physical_check || false);
  const [saving, setSaving] = useState(false);

  const cfg = STATUS_CFG[card.status] || STATUS_CFG.new;

  const save = async () => {
    setSaving(true);
    await onUpdateCard(card.card_id, {
      total_boxes: parseInt(boxes) || 0,
      transport_name: transport,
      transport_charges: parseFloat(transportCharges) || 0,
      porter_name: porter,
      porter_charges: parseFloat(porterCharges) || 0,
      lr_number: lrNumber,
      destination_city: destCity,
      notes,
      physical_check: physCheck,
    });
    setSaving(false);
  };

  const nextStatus = () => {
    const flow = { new: 'queued', queued: 'processing', processing: 'packed', packed: 'dispatched', dispatched: 'info_shared' };
    return flow[card.status];
  };

  const handleFileUpload = async (docType, e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    await onUploadDoc(card.card_id, docType, file);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={onClose} data-testid="card-detail-modal">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
        {/* Header */}
        <div className="p-4 border-b border-slate-100 flex items-center justify-between sticky top-0 bg-white rounded-t-2xl z-10">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ background: cfg.bg }}>
              {React.createElement(cfg.icon, { size: 16, style: { color: cfg.color } })}
            </div>
            <div>
              <div className="text-sm font-bold text-slate-900">{card.invoice_number}</div>
              <div className="text-xs text-slate-500">{card.card_id} {card.card_type === 'manual' && <span className="text-amber-600 font-semibold">MANUAL</span>}</div>
            </div>
          </div>
          <button onClick={onClose} className="p-1.5 hover:bg-slate-100 rounded-lg transition"><X size={18} className="text-slate-400" /></button>
        </div>

        <div className="p-4 space-y-4">
          {/* Party & Invoice info */}
          <div className="grid grid-cols-2 gap-3">
            <div className="bg-slate-50 rounded-lg p-3">
              <div className="text-[10px] text-slate-400 uppercase font-semibold mb-1">Party</div>
              <div className="text-sm font-semibold text-slate-900">{card.party_name || '-'}</div>
            </div>
            <div className="bg-slate-50 rounded-lg p-3">
              <div className="text-[10px] text-slate-400 uppercase font-semibold mb-1">Amount</div>
              <div className="text-sm font-semibold text-slate-900">Rs.{fmt(card.total_amount)}</div>
            </div>
          </div>

          {/* Items */}
          {card.items && card.items.length > 0 && (
            <div className="border border-slate-200 rounded-lg">
              <div className="p-2 bg-slate-50 text-[10px] font-semibold text-slate-600 uppercase border-b border-slate-200">Items ({card.items.length})</div>
              <div className="max-h-28 overflow-y-auto">
                {card.items.map((item, i) => (
                  <div key={i} className="px-3 py-1.5 text-xs text-slate-700 border-b border-slate-50 flex justify-between">
                    <span className="truncate mr-2">{item.item || item.item_name || '-'}</span>
                    <span className="text-slate-500 flex-shrink-0">x{item.quantity || 0}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Editable fields */}
          <div className="grid grid-cols-2 gap-3">
            <Field icon={<Boxes size={13} />} label="Total Boxes" value={boxes} onChange={setBoxes} type="number" testId="card-boxes" />
            <Field icon={<MapPin size={13} />} label="Destination City" value={destCity} onChange={setDestCity} testId="card-city" />
            <Field icon={<Truck size={13} />} label="Transport Name" value={transport} onChange={setTransport} testId="card-transport" />
            <Field icon={<Hash size={13} />} label="Transport Charges" value={transportCharges} onChange={setTransportCharges} type="number" testId="card-transport-charges" />
            <div>
              <label className="text-[10px] font-semibold text-slate-500 uppercase flex items-center gap-1 mb-1"><User size={11} /> Porter</label>
              <select value={porter} onChange={e => setPorter(e.target.value)} className="w-full px-2.5 py-1.5 text-xs border border-slate-200 rounded-lg" data-testid="card-porter">
                <option value="">Select Porter</option>
                {porters.filter(p => p.is_active).map(p => <option key={p.porter_id} value={p.name}>{p.name}</option>)}
              </select>
            </div>
            <Field icon={<Hash size={13} />} label="Porter Charges" value={porterCharges} onChange={setPorterCharges} type="number" testId="card-porter-charges" />
          </div>

          {/* LR Number */}
          <Field icon={<FileText size={13} />} label="LR / Transport Receipt Number" value={lrNumber} onChange={setLrNumber} testId="card-lr-number" full />

          {/* Notes */}
          <div>
            <label className="text-[10px] font-semibold text-slate-500 uppercase flex items-center gap-1 mb-1"><MessageSquare size={11} /> Notes</label>
            <textarea value={notes} onChange={e => setNotes(e.target.value)} rows={2} className="w-full px-2.5 py-1.5 text-xs border border-slate-200 rounded-lg resize-none" data-testid="card-notes" />
          </div>

          {/* Document uploads */}
          <div className="border border-slate-200 rounded-lg p-3">
            <div className="text-[10px] font-semibold text-slate-500 uppercase mb-2">Documents</div>
            <div className="grid grid-cols-3 gap-2">
              <DocSlot label="Invoice Doc" docType="invoice_doc" existing={card.documents?.invoice_doc} onUpload={handleFileUpload} />
              <DocSlot label="Sales Order" docType="sales_order" existing={card.documents?.sales_order} onUpload={handleFileUpload} />
              <DocSlot label="LR Receipt" docType="lr_receipt" existing={card.documents?.lr_receipt} onUpload={handleFileUpload} />
            </div>
          </div>

          {/* Physical check */}
          <label className="flex items-center gap-2 bg-amber-50 border border-amber-200 rounded-lg p-3 cursor-pointer" data-testid="card-physical-check">
            <input type="checkbox" checked={physCheck} onChange={e => setPhysCheck(e.target.checked)} className="w-4 h-4 text-amber-600 rounded" />
            <span className="text-xs text-amber-800 font-medium">I confirm all items in the bill are physically verified and present</span>
          </label>

          {/* Status timeline */}
          {card.status_history && card.status_history.length > 0 && (
            <div className="border border-slate-200 rounded-lg p-3">
              <div className="text-[10px] font-semibold text-slate-500 uppercase mb-2">Status Timeline</div>
              <div className="space-y-1">
                {card.status_history.map((h, i) => (
                  <div key={i} className="flex items-center gap-2 text-[10px]">
                    <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: STATUS_CFG[h.status]?.color || '#94a3b8' }} />
                    <span className="font-medium text-slate-700">{STATUS_CFG[h.status]?.label || h.status}</span>
                    <span className="text-slate-400">{h.at?.replace('T', ' ').slice(0, 19)}</span>
                    <span className="text-slate-400">by {h.by}</span>
                    {h.reason && <span className="text-red-500">({h.reason})</span>}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Footer actions */}
        <div className="p-4 border-t border-slate-100 flex items-center gap-2 sticky bottom-0 bg-white rounded-b-2xl">
          <button onClick={save} disabled={saving} className="px-4 py-2 text-xs bg-slate-800 text-white rounded-lg hover:bg-slate-900 transition disabled:opacity-50" data-testid="card-save">
            {saving ? 'Saving...' : 'Save Changes'}
          </button>
          {card.status !== 'hold' && card.status !== 'info_shared' && (
            <button onClick={() => onUpdateStatus(card.card_id, 'hold', { hold_reason: prompt('Hold reason?') || 'Unspecified' })}
              className="px-3 py-2 text-xs bg-red-50 text-red-600 rounded-lg hover:bg-red-100 transition flex items-center gap-1" data-testid="card-hold">
              <Pause size={12} /> Hold
            </button>
          )}
          {card.status === 'hold' && (
            <button onClick={() => onUpdateStatus(card.card_id, 'processing')}
              className="px-3 py-2 text-xs bg-amber-50 text-amber-700 rounded-lg hover:bg-amber-100 transition flex items-center gap-1" data-testid="card-resume">
              <Play size={12} /> Resume
            </button>
          )}
          {nextStatus() && (
            <button onClick={() => { save().then(() => onUpdateStatus(card.card_id, nextStatus())); }}
              className="ml-auto px-4 py-2 text-xs bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition flex items-center gap-1" data-testid="card-next-status">
              Move to {STATUS_CFG[nextStatus()]?.label} <ArrowRight size={13} />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

function Field({ icon, label, value, onChange, type = 'text', testId, full }) {
  return (
    <div className={full ? 'col-span-2' : ''}>
      <label className="text-[10px] font-semibold text-slate-500 uppercase flex items-center gap-1 mb-1">{icon} {label}</label>
      <input type={type} value={value} onChange={e => onChange(e.target.value)} className="w-full px-2.5 py-1.5 text-xs border border-slate-200 rounded-lg" data-testid={testId} />
    </div>
  );
}

function DocSlot({ label, docType, existing, onUpload }) {
  const fileRef = React.useRef();
  return (
    <div className="text-center" data-testid={`doc-${docType}`}>
      <div className="text-[10px] text-slate-500 mb-1">{label}</div>
      {existing ? (
        <a href={`${API}${existing.url}`} target="_blank" rel="noreferrer" className="block p-2 bg-green-50 border border-green-200 rounded-lg text-[10px] text-green-700 hover:bg-green-100 transition">
          <CheckCircle2 size={16} className="mx-auto mb-0.5" /> Uploaded
        </a>
      ) : (
        <button onClick={() => fileRef.current?.click()} className="block w-full p-2 bg-slate-50 border border-dashed border-slate-300 rounded-lg text-[10px] text-slate-400 hover:border-blue-400 hover:text-blue-500 transition">
          <UploadCloud size={16} className="mx-auto mb-0.5" /> Upload
        </button>
      )}
      <input ref={fileRef} type="file" accept="image/*,.pdf" className="hidden" onChange={e => onUpload(docType, e)} />
    </div>
  );
}

/* ═══════ Manual Card Modal ═══════ */
function ManualCardModal({ onClose, onCreate }) {
  const [reason, setReason] = useState('sample');
  const [party, setParty] = useState('');
  const [city, setCity] = useState('');
  const [notes, setNotes] = useState('');

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={onClose} data-testid="manual-card-modal">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md p-5" onClick={e => e.stopPropagation()}>
        <h3 className="text-sm font-bold text-slate-900 mb-4">Create Manual Dispatch Card</h3>
        <div className="space-y-3">
          <div>
            <label className="text-[10px] font-semibold text-slate-500 uppercase mb-1 block">Reason</label>
            <select value={reason} onChange={e => setReason(e.target.value)} className="w-full px-2.5 py-1.5 text-xs border border-slate-200 rounded-lg" data-testid="manual-reason">
              <option value="sample">Sample</option>
              <option value="return">Return</option>
              <option value="replacement">Replacement</option>
              <option value="internal_transfer">Internal Transfer</option>
              <option value="other">Other</option>
            </select>
          </div>
          <Field icon={<User size={13} />} label="Party Name" value={party} onChange={setParty} testId="manual-party" full />
          <Field icon={<MapPin size={13} />} label="Destination City" value={city} onChange={setCity} testId="manual-city" full />
          <div className="col-span-2">
            <label className="text-[10px] font-semibold text-slate-500 uppercase mb-1 block">Notes</label>
            <textarea value={notes} onChange={e => setNotes(e.target.value)} rows={2} className="w-full px-2.5 py-1.5 text-xs border border-slate-200 rounded-lg resize-none" data-testid="manual-notes" />
          </div>
        </div>
        <div className="flex gap-2 mt-4">
          <button onClick={onClose} className="flex-1 px-3 py-2 text-xs bg-slate-100 text-slate-700 rounded-lg hover:bg-slate-200 transition">Cancel</button>
          <button onClick={() => onCreate({ reason, party_name: party, destination_city: city, notes })}
            className="flex-1 px-3 py-2 text-xs bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition" data-testid="manual-create">Create Card</button>
        </div>
      </div>
    </div>
  );
}
