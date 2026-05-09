import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import {
  ShoppingCart, Package, Clock, CheckCircle2, XCircle, Search, Plus, X,
  User, FileText, ArrowRight, Pause, AlertTriangle, Hash, MessageSquare,
  Calendar, ChevronDown, Minus, Eye, Check, Lock, ChevronLeft,
} from 'lucide-react';
import { fuzzyMatchAny } from '../utils/fuzzySearch';

const API = process.env.REACT_APP_BACKEND_URL;
const toIST = iso => { if(!iso) return '-'; try { return new Date(iso).toLocaleString('en-IN', {timeZone:'Asia/Kolkata',day:'2-digit',month:'short',year:'numeric',hour:'2-digit',minute:'2-digit',hour12:true}); } catch { return iso; } };
const fmt = n => { if(!n||n===0) return '0'; if(Math.abs(n)>=100000) return `${(n/100000).toFixed(2)}L`; if(Math.abs(n)>=1000) return `${(n/1000).toFixed(1)}K`; return n.toLocaleString('en-IN'); };
const STATUS = {
  pending:  {label:'Pending',  color:'#f59e0b', bg:'#fffbeb'},
  approved: {label:'Approved', color:'#3b82f6', bg:'#eff6ff'},
  rejected: {label:'Rejected', color:'#ef4444', bg:'#fef2f2'},
  billed:   {label:'Billed',   color:'#10b981', bg:'#ecfdf5'},
  hold:     {label:'Hold',     color:'#8b5cf6', bg:'#f5f3ff'},
};

export default function SalesmanOrderApp({ user, selectedFY, companyId }) {
  const isAdmin = user?.role === 'admin' || user?.role === 'employee';
  const isSalesman = user?.role === 'salesman';

  if (isAdmin) return <AdminOrderView companyId={companyId} selectedFY={selectedFY} />;
  return <SalesmanView companyId={companyId} selectedFY={selectedFY} />;
}

/* ═══════════════════════════════════════════════════════
   SALESMAN VIEW — Place orders, view history
   ═══════════════════════════════════════════════════════ */
function SalesmanView({ companyId, selectedFY }) {
  const [tab, setTab] = useState('dashboard'); // dashboard | new | orders | beats
  const [customers, setCustomers] = useState([]);
  const [orders, setOrders] = useState([]);
  const [stats, setStats] = useState(null);
  const [selCustomer, setSelCustomer] = useState(null);
  const [viewOrder, setViewOrder] = useState(null);
  const [loading, setLoading] = useState(true);

  const hdr = useCallback(() => ({ Authorization:`Bearer ${localStorage.getItem('flowra_token')}`, 'X-Company-Id':companyId||'' }), [companyId]);

  const fetchData = useCallback(async () => {
    try {
      const [cr, or_, st] = await Promise.all([
        axios.get(`${API}/api/salesman-orders/my-customers?company_id=${companyId||''}`, {headers:hdr()}),
        axios.get(`${API}/api/salesman-orders/orders?company_id=${companyId||''}`, {headers:hdr()}),
        axios.get(`${API}/api/salesman-orders/my-stats?company_id=${companyId||''}&fy=${selectedFY||''}`, {headers:hdr()}),
      ]);
      if(cr.data.success) setCustomers(cr.data.data.customers||[]);
      if(or_.data.success) setOrders(or_.data.data.orders||[]);
      if(st.data.success) setStats(st.data.data||null);
    } catch(e) { console.error(e); }
    setLoading(false);
  }, [companyId, hdr, selectedFY]);

  useEffect(() => { fetchData(); }, [fetchData]);

  if(loading) return <Loader/>;

  return (
    <div className="px-1" data-testid="salesman-view">
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-lg sm:text-xl font-bold text-slate-900">Sales Orders</h1>
      </div>
      <div className="flex gap-1 mb-4 border-b border-slate-200 overflow-x-auto">
        {[
          {id:'dashboard',label:'Dashboard'},
          {id:'beat-run',label:'Beat Run Today'},
          {id:'history',label:'Beat History'},
          {id:'new',label:'New Order'},
          {id:'orders',label:`My Orders (${orders.length})`},
          {id:'beats',label:'Beat Plan'},
        ].map(t=>
          <button key={t.id} onClick={()=>setTab(t.id)} className={`px-3 sm:px-4 py-2 text-xs font-medium border-b-2 whitespace-nowrap transition ${tab===t.id?'border-blue-600 text-blue-600':'border-transparent text-slate-500 hover:text-slate-700'}`} data-testid={`tab-${t.id}`}>{t.label}</button>)}
      </div>

      {tab==='dashboard' && <SalesmanDashboard stats={stats} fy={selectedFY}/>}
      {tab==='beat-run' && <BeatRunView companyId={companyId} hdr={hdr} canCheckIn={true}/>}
      {tab==='history' && <BeatHistoryView companyId={companyId} hdr={hdr} salesman={null} canCheckIn={true}/>}

      {tab==='new' && !selCustomer && (
        <div className="space-y-2" data-testid="customer-list">
          <p className="text-xs text-slate-500 mb-2">Select a customer to place order:</p>
          {customers.length===0 && <p className="text-center text-sm text-slate-400 py-10">No customers mapped. Contact admin.</p>}
          {customers.map((c,i)=>(
            <button key={i} onClick={()=>setSelCustomer(c.customer_name)} className="w-full text-left bg-white rounded-xl border border-slate-200 p-3 hover:border-blue-300 transition" data-testid={`cust-${i}`}>
              <div className="text-sm font-semibold text-slate-900">{c.customer_name}</div>
              {c.phone && <div className="text-[10px] text-slate-500">{c.phone} {c.state && `| ${c.state}`}</div>}
            </button>
          ))}
        </div>
      )}

      {tab==='new' && selCustomer && (
        <OrderForm customer={selCustomer} companyId={companyId} hdr={hdr} onBack={()=>setSelCustomer(null)} onDone={()=>{setSelCustomer(null);setTab('orders');fetchData();}}/>
      )}

      {tab==='orders' && (
        <div className="space-y-2" data-testid="my-orders">
          {orders.length===0 && <p className="text-center text-sm text-slate-400 py-10">No orders yet</p>}
          {orders.map(o=>(
            <div key={o.order_id} className="bg-white rounded-xl border border-slate-200 p-3 cursor-pointer hover:border-slate-300" onClick={()=>setViewOrder(o)} data-testid={`order-${o.order_id}`}>
              <div className="flex items-center justify-between gap-2">
                <div className="min-w-0">
                  <div className="text-xs font-mono text-slate-400">{o.order_id}</div>
                  <div className="text-sm font-semibold text-slate-900 truncate">{o.customer_name}</div>
                </div>
                <div className="text-right flex-shrink-0">
                  <StatusBadge status={o.status}/>
                  <div className="text-xs font-medium text-slate-700 mt-0.5">Rs.{fmt(o.total_amount)}</div>
                </div>
              </div>
              <div className="flex items-center justify-between mt-1 text-[10px] text-slate-400">
                <span>{o.items?.length||0} items</span>
                <span>{toIST(o.created_at)}</span>
              </div>
              {o.invoice_number && <div className="text-[10px] text-green-600 mt-0.5">Invoice: {o.invoice_number}</div>}
            </div>
          ))}
        </div>
      )}

      {tab==='beats' && <BeatView companyId={companyId} hdr={hdr} isSalesman={true}/>}

      {viewOrder && <OrderDetailModal order={viewOrder} onClose={()=>{setViewOrder(null);fetchData();}} isAdmin={false} hdr={hdr}/>}
    </div>
  );
}

/* ═══════════════════════════════════════════════════════
   ADMIN ORDER VIEW — Approval dashboard
   ═══════════════════════════════════════════════════════ */
function AdminOrderView({ companyId, selectedFY }) {
  const [tab, setTab] = useState('pending');
  const [orders, setOrders] = useState([]);
  const [stats, setStats] = useState({});
  const [viewOrder, setViewOrder] = useState(null);
  const [search, setSearch] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [loading, setLoading] = useState(true);

  const hdr = useCallback(() => ({ Authorization:`Bearer ${localStorage.getItem('flowra_token')}`, 'X-Company-Id':companyId||'' }), [companyId]);

  const fetchOrders = useCallback(async (status='') => {
    try {
      let url = `${API}/api/salesman-orders/orders?company_id=${companyId||''}&limit=200`;
      if(status) url += `&status=${status}`;
      if(search) url += `&search=${encodeURIComponent(search)}`;
      if(dateFrom) url += `&date_from=${dateFrom}`;
      if(dateTo) url += `&date_to=${dateTo}`;
      const [or, st] = await Promise.all([
        axios.get(url, {headers:hdr()}),
        axios.get(`${API}/api/salesman-orders/stats?company_id=${companyId||''}`, {headers:hdr()}),
      ]);
      if(or.data.success) setOrders(or.data.data.orders||[]);
      if(st.data.success) setStats(st.data.data.stats||{});
    } catch(e) { console.error(e); }
    setLoading(false);
  }, [companyId, hdr, search, dateFrom, dateTo]);

  const statusForTab = tab === 'all' ? '' : tab;
  useEffect(() => { fetchOrders(statusForTab); }, [fetchOrders, tab]);

  const tabs = [
    {id:'pending', label:`Pending (${stats.pending?.count||0})`},
    {id:'approved', label:`Approved (${stats.approved?.count||0})`},
    {id:'billed', label:`Billed (${stats.billed?.count||0})`},
    {id:'hold', label:`Hold (${stats.hold?.count||0})`},
    {id:'rejected', label:`Rejected (${stats.rejected?.count||0})`},
    {id:'all', label:'All'},
    {id:'beats', label:'Beats'},
  ];

  if(loading) return <Loader/>;

  return (
    <div data-testid="admin-order-view">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 mb-4">
        <h1 className="text-lg sm:text-xl font-bold text-slate-900">Salesman Orders</h1>
        <div className="flex items-center gap-2 flex-wrap">
          <div className="relative"><Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400"/>
            <input value={search} onChange={e=>setSearch(e.target.value)} placeholder="Search order/customer..." className="pl-8 pr-3 py-1.5 text-xs border border-slate-200 rounded-lg w-36 sm:w-44" data-testid="order-search"/></div>
          <input type="date" value={dateFrom} onChange={e=>setDateFrom(e.target.value)} className="text-xs border border-slate-200 rounded-lg px-2 py-1.5" data-testid="date-from" title="From"/>
          <input type="date" value={dateTo} onChange={e=>setDateTo(e.target.value)} className="text-xs border border-slate-200 rounded-lg px-2 py-1.5" data-testid="date-to" title="To"/>
        </div>
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-3 sm:grid-cols-5 gap-2 mb-4">
        <MiniStat label="Pending" value={stats.pending?.count||0} amount={stats.pending?.total||0} color="#f59e0b"/>
        <MiniStat label="Approved" value={stats.approved?.count||0} amount={stats.approved?.total||0} color="#3b82f6"/>
        <MiniStat label="Billed" value={stats.billed?.count||0} amount={stats.billed?.total||0} color="#10b981"/>
        <MiniStat label="Hold" value={stats.hold?.count||0} amount={stats.hold?.total||0} color="#8b5cf6"/>
        <MiniStat label="Rejected" value={stats.rejected?.count||0} amount={stats.rejected?.total||0} color="#ef4444"/>
      </div>

      <div className="flex gap-1 mb-4 border-b border-slate-200 overflow-x-auto">
        {tabs.map(t=><button key={t.id} onClick={()=>setTab(t.id)} className={`px-3 py-2 text-xs font-medium border-b-2 whitespace-nowrap transition ${tab===t.id?'border-blue-600 text-blue-600':'border-transparent text-slate-500 hover:text-slate-700'}`} data-testid={`tab-${t.id}`}>{t.label}</button>)}
      </div>

      {tab==='beats' ? <BeatView companyId={companyId} hdr={hdr} isSalesman={false}/> : (
        <div className="space-y-2">
          {orders.length===0 && <p className="text-center text-sm text-slate-400 py-10">No orders</p>}
          {orders.map(o=>(
            <div key={o.order_id} className="bg-white rounded-xl border border-slate-200 p-3 cursor-pointer hover:border-slate-300 transition" onClick={()=>setViewOrder(o)} data-testid={`order-${o.order_id}`}>
              <div className="flex items-center justify-between gap-2">
                <div className="min-w-0">
                  <div className="flex items-center gap-2"><span className="text-xs font-mono text-slate-400">{o.order_id}</span><StatusBadge status={o.status}/></div>
                  <div className="text-sm font-semibold text-slate-900 truncate">{o.customer_name}</div>
                  <div className="text-[10px] text-slate-500">by {o.salesman} | {toIST(o.created_at)}</div>
                </div>
                <div className="text-right flex-shrink-0">
                  <div className="text-sm font-bold text-slate-900">Rs.{fmt(o.total_amount)}</div>
                  <div className="text-[10px] text-slate-500">{o.items?.length||0} items</div>
                  {o.invoice_number && <div className="text-[10px] text-green-600">Inv: {o.invoice_number}</div>}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {viewOrder && <OrderDetailModal order={viewOrder} onClose={()=>{setViewOrder(null);fetchOrders(statusForTab);}} isAdmin={true} hdr={hdr}/>}
    </div>
  );
}

/* ═══════════════════════════════════════════════════════
   ORDER FORM — Salesman places order
   ═══════════════════════════════════════════════════════ */
function OrderForm({ customer, companyId, hdr, onBack, onDone }) {
  const [catalog, setCatalog] = useState([]);
  const [search, setSearch] = useState('');
  const [cart, setCart] = useState([]);
  const [notes, setNotes] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [catSearch, setCatSearch] = useState('');

  useEffect(() => {
    axios.get(`${API}/api/salesman-orders/catalog?company_id=${companyId||''}`, {headers:hdr()})
      .then(r => { if(r.data.success) setCatalog(r.data.data.items||[]); });
  }, [companyId, hdr]);

  const addToCart = (item) => {
    if(cart.find(c=>c.item_name===item.item_name)) return toast.error('Already in cart');
    setCart([...cart, {...item, quantity:1, remark:''}]);
  };
  const updateCart = (idx, field, value) => {
    const c = [...cart]; c[idx] = {...c[idx], [field]: value}; setCart(c);
  };
  const removeFromCart = (idx) => { setCart(cart.filter((_,i)=>i!==idx)); };

  const total = cart.reduce((s,c)=>s+(c.quantity*c.price), 0);
  // Fuzzy global search across name + part_number + aliases — ignores
  // spaces & separator chars so "tvs 10" matches "TVS-10" / "TVS(10)" etc.
  const filtered = catSearch ? catalog.filter(c =>
    fuzzyMatchAny(catSearch, [c.item_name, c.part_number, c.aliases])
  ) : catalog;

  const submit = async () => {
    if(cart.length===0) return toast.error('Add items to cart');
    setSubmitting(true);
    try {
      const r = await axios.post(`${API}/api/salesman-orders/orders`, {
        customer_name: customer, items: cart, notes,
      }, {headers:hdr()});
      if(r.data.success) { toast.success('Order submitted!'); onDone(); } else toast.error(r.data.error);
    } catch(e) { toast.error(e.response?.data?.error||'Failed'); }
    setSubmitting(false);
  };

  return (
    <div data-testid="order-form">
      <div className="flex items-center gap-2 mb-3">
        <button onClick={onBack} className="text-xs text-slate-500 hover:text-slate-700">&larr; Back</button>
        <h2 className="text-sm font-bold text-slate-900">Order for: {customer}</h2>
      </div>

      {/* Cart */}
      {cart.length>0 && (
        <div className="bg-blue-50 border border-blue-200 rounded-xl p-3 mb-3" data-testid="cart">
          <div className="text-[10px] font-semibold text-blue-700 uppercase mb-2">Cart ({cart.length} items) — Rs.{fmt(total)}</div>
          {cart.map((c,i)=>(
            <div key={i} className="flex items-start gap-2 py-1.5 border-b border-blue-100 last:border-0">
              <div className="flex-1 min-w-0">
                <div className="text-xs font-medium text-slate-800 truncate">{c.item_name}</div>
                {c.part_number && <div className="text-[9px] text-slate-400 font-mono">P/N: {c.part_number}</div>}
                <div className="text-[10px] text-slate-500">Rs.{c.price} x {c.quantity} = Rs.{fmt(c.quantity*c.price)}</div>
              </div>
              <div className="flex items-center gap-1">
                <button onClick={()=>updateCart(i,'quantity',Math.max(1,c.quantity-1))} className="w-5 h-5 flex items-center justify-center bg-white border rounded text-xs"><Minus size={10}/></button>
                <input type="number" value={c.quantity} onChange={e=>updateCart(i,'quantity',parseInt(e.target.value)||1)} className="w-12 text-center text-xs border rounded py-0.5" data-testid={`qty-${i}`}/>
                <button onClick={()=>updateCart(i,'quantity',c.quantity+1)} className="w-5 h-5 flex items-center justify-center bg-white border rounded text-xs"><Plus size={10}/></button>
              </div>
              <button onClick={()=>removeFromCart(i)} className="p-1 hover:bg-red-50 rounded"><X size={14} className="text-red-400"/></button>
            </div>
          ))}
          {cart.map((c,i)=>(
            <input key={`r-${i}`} value={c.remark} onChange={e=>updateCart(i,'remark',e.target.value)} placeholder={`Remark for ${c.item_name.slice(0,20)}...`} className="w-full mt-1 px-2 py-1 text-[10px] border border-blue-200 rounded bg-white" data-testid={`remark-${i}`}/>
          ))}
          <textarea value={notes} onChange={e=>setNotes(e.target.value)} placeholder="Order notes (optional)" rows={2} className="w-full mt-2 px-2 py-1.5 text-xs border border-blue-200 rounded bg-white resize-none" data-testid="order-notes"/>
          <button onClick={submit} disabled={submitting} className="w-full mt-2 px-4 py-2 text-xs bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 font-semibold" data-testid="submit-order">
            {submitting ? 'Submitting...' : `Submit Order — Rs.${fmt(total)}`}
          </button>
        </div>
      )}

      {/* Catalog */}
      <div className="relative mb-3"><Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400"/>
        <input value={catSearch} onChange={e=>setCatSearch(e.target.value)} placeholder="Search by name or part number..." className="w-full pl-8 pr-3 py-2 text-sm border border-slate-200 rounded-lg" data-testid="cat-search"/></div>
      <div className="space-y-1.5" data-testid="catalog">
        {filtered.map((item,i)=>(
          <div key={i} className="bg-white rounded-lg border border-slate-200 p-2.5 flex items-center justify-between" data-testid={`cat-${i}`}>
            <div className="min-w-0 flex-1">
              <div className="text-xs font-semibold text-slate-800 truncate">{item.item_name}</div>
              {item.part_number && <div className="text-[9px] text-slate-400 font-mono">P/N: {item.part_number}</div>}
              <div className="flex gap-3 text-[10px] text-slate-500 flex-wrap">
                <span className="font-semibold text-slate-700">Rs.{Number(item.price||0).toLocaleString('en-IN')}</span>
                <span className={item.stock_qty>0?'text-green-600':'text-red-500'}>Stock: {item.stock_qty} {item.unit}</span>
                {item.stock_group && <span className="hidden sm:inline">{item.stock_group}</span>}
              </div>
            </div>
            <button onClick={()=>addToCart(item)} disabled={cart.find(c=>c.item_name===item.item_name)} className="px-2 py-1 text-[10px] bg-blue-50 text-blue-600 rounded-lg hover:bg-blue-100 disabled:opacity-30 flex-shrink-0" data-testid={`add-${i}`}>
              <Plus size={12}/>
            </button>
          </div>
        ))}
        {filtered.length===0 && <p className="text-center text-xs text-slate-400 py-6">No products found</p>}
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════
   ORDER DETAIL MODAL
   ═══════════════════════════════════════════════════════ */
function OrderDetailModal({ order, onClose, isAdmin, hdr }) {
  const [o, setO] = useState(order);
  const [invoiceNum, setInvoiceNum] = useState('');
  const [adminNotes, setAdminNotes] = useState('');
  const [rejectReason, setRejectReason] = useState('');
  const [processing, setProcessing] = useState(false);

  const changeStatus = async (status, extra={}) => {
    setProcessing(true);
    try {
      const r = await axios.patch(`${API}/api/salesman-orders/orders/${o.order_id}/status`, {status, ...extra}, {headers:hdr()});
      if(r.data.success) { toast.success(r.data.message);
        const updated = await axios.get(`${API}/api/salesman-orders/orders/${o.order_id}`, {headers:hdr()});
        if(updated.data.success) setO(updated.data.data);
      } else toast.error(r.data.error);
    } catch(e) { toast.error(e.response?.data?.error||'Failed'); }
    setProcessing(false);
  };

  const cfg = STATUS[o.status]||STATUS.pending;

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/40 p-0 sm:p-4" onClick={onClose} data-testid="order-detail-modal">
      <div className="bg-white rounded-t-2xl sm:rounded-2xl shadow-2xl w-full sm:max-w-2xl max-h-[92vh] sm:max-h-[90vh] overflow-y-auto" onClick={e=>e.stopPropagation()}>
        <div className="p-3 sm:p-4 border-b border-slate-100 flex items-center justify-between sticky top-0 bg-white rounded-t-2xl z-10">
          <div className="min-w-0">
            <div className="flex items-center gap-2"><span className="text-sm font-bold text-slate-900">{o.order_id}</span><StatusBadge status={o.status}/></div>
            <div className="text-[10px] text-slate-500">{o.customer_name} | by {o.salesman} | {toIST(o.created_at)}</div>
          </div>
          <button onClick={onClose} className="p-1.5 hover:bg-slate-100 rounded-lg"><X size={18} className="text-slate-400"/></button>
        </div>
        <div className="p-3 sm:p-4 space-y-3">
          {/* Items */}
          <div className="border border-slate-200 rounded-lg">
            <div className="p-2 bg-slate-50 text-[9px] font-semibold text-slate-600 uppercase border-b flex justify-between"><span>Items ({o.items?.length})</span><span>Rs.{fmt(o.total_amount)}</span></div>
            <div className="divide-y divide-slate-50">
              {(o.items||[]).map((it,i)=>(
                <div key={i} className="px-3 py-2">
                  <div className="flex items-center justify-between">
                    <div className="min-w-0 flex-1">
                      <div className="text-xs font-medium text-slate-800 truncate">{it.item_name}</div>
                      {it.part_number && <div className="text-[9px] text-slate-400 font-mono">P/N: {it.part_number}</div>}
                    </div>
                    <span className="text-xs text-slate-600 flex-shrink-0">x{it.quantity} @ Rs.{it.price} = <strong>Rs.{fmt(it.amount)}</strong></span>
                  </div>
                  {it.remark && <div className="text-[10px] text-slate-400 mt-0.5 italic">{it.remark}</div>}
                </div>
              ))}
            </div>
          </div>
          {o.notes && <div><span className="text-[9px] text-slate-400 uppercase font-semibold">Notes</span><p className="text-xs text-slate-600 bg-slate-50 rounded-lg p-2 mt-1">{o.notes}</p></div>}
          {o.admin_notes && <div><span className="text-[9px] text-slate-400 uppercase font-semibold">Admin Notes</span><p className="text-xs text-blue-700 bg-blue-50 rounded-lg p-2 mt-1">{o.admin_notes}</p></div>}
          {o.invoice_number && <div className="bg-green-50 border border-green-200 rounded-lg p-2.5"><span className="text-[9px] text-green-600 uppercase font-semibold">Invoice Number</span><p className="text-sm font-bold text-green-800">{o.invoice_number}</p></div>}

          {/* Timeline */}
          {o.status_history?.length>0 && <div className="border border-slate-200 rounded-lg p-2.5"><div className="text-[9px] font-semibold text-slate-500 uppercase mb-1.5">Timeline</div>
            <div className="space-y-0.5">{o.status_history.map((h,i)=><div key={i} className="flex items-center gap-1.5 text-[10px]">
              <span className="w-1.5 h-1.5 rounded-full flex-shrink-0" style={{background:STATUS[h.status]?.color||'#94a3b8'}}/><span className="font-medium text-slate-700">{STATUS[h.status]?.label||h.status}</span><span className="text-slate-400">{toIST(h.at)}</span><span className="text-slate-400">by {h.by}</span>{h.reason && <span className="text-red-500">({h.reason})</span>}</div>)}</div></div>}

          {/* Admin Actions */}
          {isAdmin && o.status==='pending' && (
            <div className="space-y-2 border-t border-slate-200 pt-3">
              <textarea value={adminNotes} onChange={e=>setAdminNotes(e.target.value)} placeholder="Admin notes (optional)" rows={2} className="w-full px-2.5 py-1.5 text-xs border border-slate-200 rounded-lg resize-none" data-testid="admin-notes"/>
              <div className="flex gap-2">
                <button onClick={()=>changeStatus('approved', {admin_notes:adminNotes})} disabled={processing} className="flex-1 px-3 py-2 text-xs bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50" data-testid="btn-approve">Approve</button>
                <button onClick={()=>changeStatus('hold', {admin_notes:adminNotes})} disabled={processing} className="px-3 py-2 text-xs bg-purple-50 text-purple-600 rounded-lg hover:bg-purple-100" data-testid="btn-hold">Hold</button>
                <button onClick={()=>{const r=prompt('Rejection reason (required):');if(r&&r.trim())changeStatus('rejected',{reject_reason:r.trim(),admin_notes:adminNotes});else if(r!==null)toast.error('Rejection reason is required');}} disabled={processing} className="px-3 py-2 text-xs bg-red-50 text-red-600 rounded-lg hover:bg-red-100" data-testid="btn-reject">Reject</button>
              </div>
            </div>
          )}
          {isAdmin && o.status==='approved' && (
            <div className="space-y-2 border-t border-slate-200 pt-3">
              <div className="text-xs text-slate-600">Mark as billed — enter the Tally invoice number:</div>
              <input value={invoiceNum} onChange={e=>setInvoiceNum(e.target.value)} placeholder="Invoice number from Tally" className="w-full px-2.5 py-1.5 text-xs border border-slate-200 rounded-lg" data-testid="invoice-input"/>
              <div className="flex gap-2">
                <button onClick={()=>{if(!invoiceNum.trim())return toast.error('Invoice number required');changeStatus('billed',{invoice_number:invoiceNum.trim()});}} disabled={processing} className="flex-1 px-3 py-2 text-xs bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50" data-testid="btn-bill">Mark as Billed</button>
                <button onClick={()=>changeStatus('hold')} disabled={processing} className="px-3 py-2 text-xs bg-purple-50 text-purple-600 rounded-lg hover:bg-purple-100">Hold</button>
              </div>
            </div>
          )}
          {isAdmin && o.status==='hold' && (
            <div className="flex gap-2 border-t border-slate-200 pt-3">
              <button onClick={()=>changeStatus('approved')} disabled={processing} className="flex-1 px-3 py-2 text-xs bg-blue-600 text-white rounded-lg">Resume to Approved</button>
              <button onClick={()=>{const r=prompt('Rejection reason (required):');if(r&&r.trim())changeStatus('rejected',{reject_reason:r.trim()});else if(r!==null)toast.error('Rejection reason is required');}} disabled={processing} className="px-3 py-2 text-xs bg-red-50 text-red-600 rounded-lg">Reject</button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════
   BEAT VIEW
   ═══════════════════════════════════════════════════════ */
function BeatView({ companyId, hdr, isSalesman }) {
  const [beats, setBeats] = useState([]);
  useEffect(() => {
    axios.get(`${API}/api/salesman-orders/beats?company_id=${companyId||''}`, {headers:hdr()})
      .then(r => { if(r.data.success) setBeats(r.data.data.beats||[]); });
  }, [companyId, hdr]);

  const markVisit = async (beatId) => {
    try {
      const r = await axios.post(`${API}/api/salesman-orders/beats/${beatId}/visit`, {}, {headers:hdr()});
      if(r.data.success) toast.success('Visit recorded');
    } catch { toast.error('Failed'); }
  };

  return (
    <div data-testid="beat-view">
      {beats.length===0 && <p className="text-center text-sm text-slate-400 py-10">{isSalesman?'No beat plan assigned. Contact admin.':'No beat plans created yet.'}</p>}
      {beats.map((b,i)=>(
        <div key={i} className="bg-white rounded-xl border border-slate-200 p-3 mb-2 flex items-center justify-between">
          <div><div className="text-xs font-semibold text-slate-900">{b.customer_name}</div>
            <div className="text-[10px] text-slate-500">{b.day_of_week} | {b.frequency}</div>
            {b.visits?.length>0 && <div className="text-[10px] text-green-600">Last visit: {toIST(b.visits[b.visits.length-1]?.at)}</div>}
          </div>
          {isSalesman && <button onClick={()=>markVisit(b.beat_id)} className="px-2 py-1 text-[10px] bg-green-50 text-green-600 rounded-lg hover:bg-green-100">Visited</button>}
        </div>
      ))}
    </div>
  );
}

/* ═══ Shared Components ═══ */
function StatusBadge({ status }) {
  const s = STATUS[status]||STATUS.pending;
  return <span className="text-[9px] px-1.5 py-0.5 rounded-full font-bold" style={{background:s.bg,color:s.color}}>{s.label}</span>;
}
function MiniStat({ label, value, amount, color }) {
  return <div className="bg-white rounded-lg border border-slate-200 p-2"><div className="text-[9px] text-slate-500">{label}</div><div className="text-sm font-bold" style={{color}}>{value}</div><div className="text-[9px] text-slate-400">Rs.{fmt(amount)}</div></div>;
}
function Loader() { return <div className="flex items-center justify-center h-48"><div className="animate-spin w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full"/></div>; }

// ─── Beat Run Today ──────────────────────────────────────────────────────
function BeatRunView({ companyId, hdr, runDate = null, salesman = null, canCheckIn = true }) {
  const [run, setRun] = useState(null);
  const [loading, setLoading] = useState(true);
  const [unName, setUnName] = useState('');
  const [unDetails, setUnDetails] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const fetchRun = useCallback(async () => {
    setLoading(true);
    try {
      const url = `${API}/api/salesman-orders/beat-run/today?company_id=${companyId||''}${runDate?`&run_date=${runDate}`:''}${salesman?`&salesman=${encodeURIComponent(salesman)}`:''}`;
      const r = await axios.get(url, { headers: hdr() });
      if (r.data?.success) setRun(r.data.data);
    } catch { /* ignore */ }
    setLoading(false);
  }, [companyId, hdr, runDate, salesman]);

  useEffect(() => { fetchRun(); }, [fetchRun]);

  const checkIn = async (customer_name, visited) => {
    if (!canCheckIn || run?.locked) return;
    try {
      await axios.post(`${API}/api/salesman-orders/beat-run/check-in`,
        { customer_name, visited, company_id: companyId || '', salesman: salesman || undefined },
        { headers: hdr() });
      fetchRun();
    } catch { toast.error('Check-in failed'); }
  };

  const addUnplanned = async () => {
    if (!unName.trim()) { toast.error('Enter customer name'); return; }
    if (run?.locked) return;
    setSubmitting(true);
    try {
      const r = await axios.post(`${API}/api/salesman-orders/beat-run/add-unplanned`,
        { customer_name: unName.trim(), details: unDetails.trim(), company_id: companyId || '' },
        { headers: hdr() });
      if (r.data?.success) {
        toast.success('Unplanned visit added');
        setUnName(''); setUnDetails('');
        fetchRun();
      } else toast.error(r.data?.error || 'Failed');
    } catch { toast.error('Failed'); }
    setSubmitting(false);
  };

  if (loading) return <Loader/>;
  if (!run) return <p className="text-center text-xs text-slate-400 py-6">No data.</p>;

  const visitedCount = (run.planned||[]).filter(p => p.visited_at).length;
  const total = (run.planned||[]).length;
  const dateLabel = (() => { try { return new Date(run.run_date).toLocaleDateString('en-IN', {weekday:'long', day:'2-digit', month:'short', year:'numeric'}); } catch { return run.run_date; } })();

  return (
    <div className="space-y-3" data-testid="beat-run-view">
      {/* Header */}
      <div className="bg-white rounded-lg border border-slate-200 p-3 flex items-center justify-between gap-2">
        <div className="min-w-0">
          <div className="flex items-center gap-2 mb-0.5">
            <h3 className="text-sm font-semibold text-slate-800">{dateLabel}</h3>
            {run.locked && <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-slate-100 text-slate-500 font-bold flex items-center gap-1" data-testid="locked-badge"><Lock size={10}/>LOCKED</span>}
          </div>
          <p className="text-[11px] text-slate-500">{run.salesman} · {run.day_of_week}</p>
        </div>
        <div className="text-right flex-shrink-0">
          <div className="text-lg font-bold text-blue-600">{visitedCount}/{total}</div>
          <div className="text-[10px] text-slate-500">planned visited</div>
        </div>
      </div>

      {/* Planned visits checklist */}
      <div className="bg-white rounded-lg border border-slate-200 overflow-hidden" data-testid="planned-list">
        <div className="px-3 py-2 border-b border-slate-100"><h4 className="text-xs font-semibold text-slate-700">Planned Visits ({total})</h4></div>
        {total === 0 && <p className="text-center text-xs text-slate-400 py-6 italic">No customers scheduled for {run.day_of_week}.</p>}
        {(run.planned||[]).map((p, i) => {
          const done = !!p.visited_at;
          return (
            <button key={i} onClick={() => checkIn(p.customer_name, !done)}
              disabled={!canCheckIn || run.locked}
              className={`w-full text-left px-3 py-2.5 border-b border-slate-50 last:border-0 flex items-center gap-2.5 transition ${done?'bg-green-50':'hover:bg-slate-50'} ${(!canCheckIn || run.locked)?'cursor-not-allowed opacity-90':'cursor-pointer'}`}
              data-testid={`planned-${i}`}>
              <div className={`w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0 transition ${done?'bg-green-500 text-white':'border-2 border-slate-300'}`}>
                {done && <Check size={12}/>}
              </div>
              <div className="min-w-0 flex-1">
                <div className={`text-xs sm:text-sm ${done?'font-medium text-green-800 line-through':'font-medium text-slate-800'} truncate`}>{p.customer_name}</div>
                <div className="text-[10px] text-slate-500">{p.frequency}{p.visited_at ? ` · visited ${new Date(p.visited_at).toLocaleTimeString('en-IN',{hour:'2-digit',minute:'2-digit',hour12:true,timeZone:'Asia/Kolkata'})}` : ''}</div>
              </div>
            </button>
          );
        })}
      </div>

      {/* Unplanned visits */}
      <div className="bg-white rounded-lg border border-slate-200 overflow-hidden" data-testid="unplanned-list">
        <div className="px-3 py-2 border-b border-slate-100 flex items-center justify-between">
          <h4 className="text-xs font-semibold text-slate-700">Unplanned Visits ({(run.unplanned||[]).length})</h4>
        </div>
        {(run.unplanned||[]).length === 0 && <p className="text-center text-[11px] text-slate-400 py-3 italic">None yet.</p>}
        {(run.unplanned||[]).map((u, i) => (
          <div key={i} className="px-3 py-2 border-b border-slate-50 last:border-0" data-testid={`unplanned-${i}`}>
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-1.5">
                  <span className="text-xs font-medium text-slate-800 truncate">{u.customer_name}</span>
                  <span className="text-[8px] px-1 py-0.5 rounded-full bg-amber-100 text-amber-700 font-bold" data-testid="new-tag">NEW</span>
                </div>
                {u.details && <p className="text-[10px] text-slate-500 mt-0.5">{u.details}</p>}
              </div>
              <span className="text-[9px] text-slate-400 flex-shrink-0">{new Date(u.added_at).toLocaleTimeString('en-IN',{hour:'2-digit',minute:'2-digit',hour12:true,timeZone:'Asia/Kolkata'})}</span>
            </div>
          </div>
        ))}
        {canCheckIn && !run.locked && (
          <div className="px-3 py-2.5 bg-slate-50 border-t border-slate-100">
            <p className="text-[10px] text-slate-500 mb-1.5">Met someone outside the plan? Add quickly — tagged NEW until they appear in Tally.</p>
            <input value={unName} onChange={e=>setUnName(e.target.value)} placeholder="Customer name *"
              className="w-full px-2 py-1.5 text-xs border border-slate-200 rounded mb-1.5" data-testid="unplanned-name"/>
            <input value={unDetails} onChange={e=>setUnDetails(e.target.value)} placeholder="Details (phone / location / what they need)"
              className="w-full px-2 py-1.5 text-xs border border-slate-200 rounded mb-1.5" data-testid="unplanned-details"/>
            <button onClick={addUnplanned} disabled={submitting || !unName.trim()}
              className="w-full px-3 py-1.5 text-xs bg-blue-600 text-white rounded font-medium disabled:opacity-50" data-testid="add-unplanned-btn">
              {submitting?'Adding...':'Add Unplanned Visit'}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Beat History (read-only past runs) ─────────────────────────────────
function BeatHistoryView({ companyId, hdr, salesman = null }) {
  const [runs, setRuns] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selRun, setSelRun] = useState(null);

  useEffect(() => {
    setLoading(true);
    const url = `${API}/api/salesman-orders/beat-run/history?company_id=${companyId||''}${salesman?`&salesman=${encodeURIComponent(salesman)}`:''}&limit=60`;
    axios.get(url, { headers: hdr() })
      .then(r => { if (r.data?.success) setRuns(r.data.data.runs||[]); })
      .finally(() => setLoading(false));
  }, [companyId, hdr, salesman]);

  if (loading) return <Loader/>;
  if (selRun) return (
    <div data-testid="history-detail">
      <button onClick={()=>setSelRun(null)} className="text-xs text-blue-600 mb-2 flex items-center gap-1" data-testid="back-to-history"><ChevronLeft size={14}/>Back to history</button>
      <BeatRunView companyId={companyId} hdr={hdr} runDate={selRun.run_date} salesman={selRun.salesman} canCheckIn={false}/>
    </div>
  );

  return (
    <div className="space-y-2" data-testid="beat-history-view">
      {runs.length === 0 && <p className="text-center text-xs text-slate-400 py-8 italic">No past beat runs yet.</p>}
      {runs.map((r, i) => {
        const date = (() => { try { return new Date(r.run_date).toLocaleDateString('en-IN', {weekday:'short', day:'2-digit', month:'short', year:'numeric'}); } catch { return r.run_date; } })();
        const pct = r.planned_count ? Math.round(r.visited_count / r.planned_count * 100) : 0;
        return (
          <button key={i} onClick={()=>setSelRun(r)} className="w-full text-left bg-white rounded-lg border border-slate-200 p-3 hover:border-blue-300 transition" data-testid={`history-row-${i}`}>
            <div className="flex items-center justify-between gap-2">
              <div className="min-w-0">
                <div className="flex items-center gap-1.5 mb-0.5">
                  <span className="text-xs font-semibold text-slate-800">{date}</span>
                  {r.locked && <span className="text-[8px] px-1 py-0.5 rounded-full bg-slate-100 text-slate-500 font-bold flex items-center gap-0.5"><Lock size={9}/>LOCKED</span>}
                </div>
                {salesman === null && <p className="text-[10px] text-slate-500">{r.salesman}</p>}
                <p className="text-[10px] text-slate-500">{r.visited_count}/{r.planned_count} planned · {r.unplanned_count} unplanned</p>
              </div>
              <div className="text-right flex-shrink-0">
                <div className={`text-base font-bold ${pct>=80?'text-green-600':pct>=50?'text-blue-600':pct>=20?'text-amber-600':'text-slate-400'}`}>{pct}%</div>
                <div className="text-[9px] text-slate-400">coverage</div>
              </div>
            </div>
          </button>
        );
      })}
    </div>
  );
}

function SalesmanDashboard({ stats, fy }) {
  if (!stats) return <p className="text-center text-xs text-slate-400 py-6" data-testid="dashboard-empty">No stats available.</p>;
  if (!stats.has_master) return (
    <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 text-xs text-amber-800" data-testid="dashboard-no-master">
      You haven't been mapped as a salesman by your admin yet. Once your admin adds your name in the Salesman Performance page (with a target & customer list for FY {fy}), your dashboard will populate here automatically.
    </div>
  );
  const ach = stats.achievement_percentage || 0;
  const achColor = ach >= 100 ? 'text-green-600 bg-green-100' : ach >= 75 ? 'text-blue-600 bg-blue-100' : ach >= 50 ? 'text-amber-600 bg-amber-100' : 'text-red-600 bg-red-100';
  const fmtNum = (n) => Number(n||0).toLocaleString('en-IN', {maximumFractionDigits:0});

  return (
    <div className="space-y-3" data-testid="salesman-dashboard">
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 sm:gap-3">
        <KPI label="Achieved" value={`Rs.${fmtNum(stats.achieved_amount)}`} sub={`${stats.total_customers} customers`} color="blue" testid="kpi-achieved"/>
        <KPI label="Expected (YTD)" value={`Rs.${fmtNum(stats.expected_target)}`} sub={`Annual: Rs.${fmtNum(stats.annual_target)}`} color="slate" testid="kpi-expected"/>
        <KPI label="Monthly Target" value={`Rs.${fmtNum(stats.monthly_target)}`} sub={`Quarterly: Rs.${fmtNum(stats.quarterly_target)}`} color="slate" testid="kpi-monthly"/>
        <div className={`rounded-lg p-2.5 ${achColor}`} data-testid="kpi-achievement">
          <div className="text-[10px] uppercase tracking-wide opacity-70">Achievement</div>
          <div className="text-xl sm:text-2xl font-bold mt-0.5">{ach}%</div>
          <div className="text-[10px] opacity-70 mt-0.5">{ach >= 100 ? 'Target met!' : 'vs YTD-prorated'}</div>
        </div>
      </div>

      <div className="bg-white rounded-lg border border-slate-200 overflow-hidden" data-testid="customer-breakdown">
        <div className="px-3 py-2 border-b border-slate-100 flex items-center justify-between">
          <h3 className="text-xs font-semibold text-slate-700">Customer-wise Sales (FY {stats.fy})</h3>
          <span className="text-[10px] text-slate-400">{stats.customers.length} active</span>
        </div>
        <div className="max-h-80 overflow-y-auto">
          {stats.customers.length === 0 && <p className="text-center text-xs text-slate-400 py-6">No sales recorded yet.</p>}
          {stats.customers.map((c, i) => (
            <details key={i} className="border-b border-slate-100 last:border-0 group" data-testid={`cust-${i}`}>
              <summary className="px-3 py-2 cursor-pointer hover:bg-slate-50 flex items-center justify-between">
                <div className="min-w-0 flex-1">
                  <div className="text-xs font-medium text-slate-800 truncate">{c.customer_name}</div>
                  <div className="text-[10px] text-slate-500">{c.count} order{c.count !== 1 ? 's' : ''} · {c.items.length} item{c.items.length !== 1 ? 's' : ''}</div>
                </div>
                <span className="text-xs font-semibold text-blue-600 flex-shrink-0">Rs.{fmtNum(c.amount)}</span>
              </summary>
              <div className="px-3 pb-2 bg-slate-50 text-[10px]">
                {c.items.slice(0, 20).map((it, j) => (
                  <div key={j} className="flex justify-between py-0.5">
                    <span className="truncate">{it.item_name}</span>
                    <span className="text-slate-500 flex-shrink-0 ml-2">x{it.quantity} = Rs.{fmtNum(it.amount)}</span>
                  </div>
                ))}
                {c.items.length > 20 && <div className="text-[10px] text-slate-400 italic mt-1">+{c.items.length - 20} more line items</div>}
              </div>
            </details>
          ))}
        </div>
      </div>

      {stats.items_sold && stats.items_sold.length > 0 && (
        <div className="bg-white rounded-lg border border-slate-200 overflow-hidden" data-testid="items-sold">
          <div className="px-3 py-2 border-b border-slate-100">
            <h3 className="text-xs font-semibold text-slate-700">Top Items Sold</h3>
          </div>
          <div className="max-h-60 overflow-y-auto">
            {stats.items_sold.slice(0, 25).map((it, i) => (
              <div key={i} className="px-3 py-1.5 border-b border-slate-50 last:border-0 flex items-center justify-between text-xs">
                <span className="truncate flex-1 min-w-0">{it.item_name}</span>
                <span className="text-slate-500 flex-shrink-0 ml-2">Qty {fmtNum(it.quantity)} · Rs.{fmtNum(it.revenue)}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function KPI({ label, value, sub, color = 'slate', testid }) {
  const colorMap = {
    blue: 'bg-blue-50 border-blue-100 text-blue-900',
    slate: 'bg-white border-slate-200 text-slate-900',
  };
  return (
    <div className={`rounded-lg border p-2.5 ${colorMap[color]}`} data-testid={testid}>
      <div className="text-[10px] uppercase tracking-wide text-slate-500">{label}</div>
      <div className="text-base sm:text-lg font-bold mt-0.5 truncate">{value}</div>
      {sub && <div className="text-[10px] text-slate-400 mt-0.5 truncate">{sub}</div>}
    </div>
  );
}
