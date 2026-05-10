import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import {
  ShoppingCart, Package, Clock, CheckCircle2, XCircle, Search, Plus, X,
  User, FileText, ArrowRight, Pause, AlertTriangle, Hash, MessageSquare,
  Calendar, ChevronDown, Minus, Eye, Check, Lock, ChevronLeft, Sparkles,
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
   Redesigned (Feb 2026) with 3 smart sections:
     • Repeat Order   — what this customer bought in last 8-10 months
     • Suggestions    — affinity + fast-moving cross-sell
     • Browse Catalog — full inventory search
   Sticky cart, mobile-first, large touch targets.
   ═══════════════════════════════════════════════════════ */
function OrderForm({ customer, companyId, hdr, onBack, onDone }) {
  const [section, setSection] = useState('repeat');     // 'repeat' | 'suggest' | 'browse'
  const [catalog, setCatalog] = useState([]);
  const [history, setHistory] = useState([]);           // repeat-order items
  const [suggestions, setSuggestions] = useState([]);   // cross-sell items
  const [loadingHist, setLoadingHist] = useState(false);
  const [loadingSugg, setLoadingSugg] = useState(false);
  const [cart, setCart] = useState([]);
  const [notes, setNotes] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [catSearch, setCatSearch] = useState('');
  const [showCart, setShowCart] = useState(false);      // mobile bottom-sheet toggle

  // Fetch catalog (browse) once
  useEffect(() => {
    axios.get(`${API}/api/salesman-orders/catalog?company_id=${companyId||''}`, {headers:hdr()})
      .then(r => { if(r.data.success) setCatalog(r.data.data.items||[]); });
  }, [companyId, hdr]);

  // Fetch repeat-order history + cross-sell suggestions in parallel when customer changes
  useEffect(() => {
    if (!customer) return;
    setLoadingHist(true); setLoadingSugg(true);
    const enc = encodeURIComponent(customer);
    const cq = companyId ? `&company_id=${companyId}` : '';
    axios.get(`${API}/api/salesman-orders/customer-history/${enc}?months=10${cq}`, {headers:hdr()})
      .then(r => { if (r.data.success) setHistory(r.data.data.items || []); })
      .catch(() => {})
      .finally(() => setLoadingHist(false));
    axios.get(`${API}/api/salesman-orders/related-items/${enc}?months=12&limit=12${cq}`, {headers:hdr()})
      .then(r => { if (r.data.success) setSuggestions(r.data.data.items || []); })
      .catch(() => {})
      .finally(() => setLoadingSugg(false));
  }, [customer, companyId, hdr]);

  const inCart = (name) => cart.some(c => c.item_name === name);
  const addToCart = (item, qty = 1) => {
    if (inCart(item.item_name)) { toast.error('Already in cart'); return; }
    // Build a uniform cart row regardless of source (catalog/history/suggestions)
    setCart([...cart, {
      item_name: item.item_name,
      part_number: item.part_number || '',
      price: Number(item.price || item.standard_price || item.last_price || 0),
      stock_qty: Number(item.stock_qty || 0),
      unit: item.unit || '',
      quantity: Math.max(1, Math.round(qty || 1)),
      remark: '',
    }]);
    toast.success(`${item.item_name.slice(0, 28)} added`);
  };
  const updateCart = (idx, field, value) => {
    const c = [...cart]; c[idx] = {...c[idx], [field]: value}; setCart(c);
  };
  const removeFromCart = (idx) => { setCart(cart.filter((_,i)=>i!==idx)); };

  const total = cart.reduce((s,c)=>s+(c.quantity*c.price), 0);
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

  // ── Section pill tabs ───────────────────────────────────────────────
  const sections = [
    { id: 'repeat',  label: 'Repeat Order',  count: history.length,
      icon: <Clock size={13}/>, hint: '10-month buy history' },
    { id: 'suggest', label: 'Suggestions',   count: suggestions.length,
      icon: <Sparkles size={13}/>, hint: 'Cross-sell + fast movers' },
    { id: 'browse',  label: 'Browse',        count: catalog.length,
      icon: <Package size={13}/>,  hint: 'Full catalog' },
  ];

  return (
    <div data-testid="order-form" className="lg:grid lg:grid-cols-[1fr_360px] lg:gap-4">
      {/* ── Main column ─────────────────────────────────────────────── */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2 min-w-0">
            <button onClick={onBack} className="text-xs text-slate-500 hover:text-slate-700 flex-shrink-0">
              <ChevronLeft size={16} className="inline -mt-0.5"/>Back
            </button>
            <div className="min-w-0">
              <h2 className="text-sm font-bold text-slate-900 truncate">{customer}</h2>
              <div className="text-[10px] text-slate-400">New order</div>
            </div>
          </div>
          {/* Mobile cart toggle */}
          <button onClick={()=>setShowCart(s=>!s)}
            className="lg:hidden relative px-3 py-1.5 bg-blue-600 text-white text-xs rounded-lg font-semibold flex items-center gap-1.5"
            data-testid="cart-toggle">
            <ShoppingCart size={14}/> {cart.length}
            {cart.length > 0 && <span className="text-[10px]">· Rs.{fmt(total)}</span>}
          </button>
        </div>

        {/* Section pills */}
        <div className="flex gap-1.5 mb-3 overflow-x-auto pb-1" data-testid="section-pills">
          {sections.map(s => {
            const active = section === s.id;
            return (
              <button key={s.id} onClick={()=>setSection(s.id)}
                className={`flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-medium whitespace-nowrap transition border ${
                  active
                    ? 'bg-blue-600 text-white border-blue-600 shadow-sm'
                    : 'bg-white text-slate-600 border-slate-200 hover:border-slate-300'
                }`}
                data-testid={`section-${s.id}`}>
                {s.icon}
                <span>{s.label}</span>
                {s.count > 0 && (
                  <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-semibold ${
                    active ? 'bg-white/20 text-white' : 'bg-slate-100 text-slate-500'
                  }`}>{s.count}</span>
                )}
              </button>
            );
          })}
        </div>

        {/* ── REPEAT ORDER ─────────────────────────────────────────── */}
        {section === 'repeat' && (
          <div data-testid="repeat-section">
            {loadingHist ? (
              <SectionEmpty icon={<Clock size={22}/>} title="Loading history…" />
            ) : history.length === 0 ? (
              <SectionEmpty icon={<Clock size={22}/>}
                title="No purchase history found"
                hint="This customer hasn't bought anything in the last 10 months. Try Suggestions or Browse." />
            ) : (
              <div className="space-y-1.5">
                {history.map((it, i) => (
                  <RepeatRow key={i} item={it}
                    inCart={inCart(it.item_name)}
                    onAdd={(q) => addToCart(it, q)}
                    testid={`hist-${i}`}/>
                ))}
              </div>
            )}
          </div>
        )}

        {/* ── CROSS-SELL SUGGESTIONS ───────────────────────────────── */}
        {section === 'suggest' && (
          <div data-testid="suggest-section">
            {loadingSugg ? (
              <SectionEmpty icon={<Sparkles size={22}/>} title="Building suggestions…" />
            ) : suggestions.length === 0 ? (
              <SectionEmpty icon={<Sparkles size={22}/>}
                title="No suggestions yet"
                hint="Suggestions appear once the customer has prior purchases or once you bill more orders." />
            ) : (
              <div className="space-y-1.5">
                {suggestions.map((it, i) => (
                  <SuggestRow key={i} item={it}
                    inCart={inCart(it.item_name)}
                    onAdd={() => addToCart(it, 1)}
                    testid={`sugg-${i}`}/>
                ))}
              </div>
            )}
          </div>
        )}

        {/* ── BROWSE CATALOG ──────────────────────────────────────── */}
        {section === 'browse' && (
          <div data-testid="browse-section">
            <div className="relative mb-3">
              <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400"/>
              <input value={catSearch} onChange={e=>setCatSearch(e.target.value)}
                placeholder="Search by name or part number…"
                className="w-full pl-8 pr-3 py-2 text-sm border border-slate-200 rounded-lg"
                data-testid="cat-search"/>
            </div>
            <div className="space-y-1.5" data-testid="catalog">
              {filtered.slice(0, 200).map((item, i) => (
                <CatalogRow key={i} item={item}
                  inCart={inCart(item.item_name)}
                  onAdd={() => addToCart(item, 1)}
                  testid={`cat-${i}`}/>
              ))}
              {filtered.length === 0 && (
                <p className="text-center text-xs text-slate-400 py-6">No products found</p>
              )}
              {filtered.length > 200 && (
                <p className="text-center text-[10px] text-slate-400 py-2">
                  Showing first 200 of {filtered.length} — refine your search.
                </p>
              )}
            </div>
          </div>
        )}
      </div>

      {/* ── Cart panel — sticky desktop, bottom-sheet mobile ───────── */}
      <CartPanel cart={cart} total={total} notes={notes} setNotes={setNotes}
        updateCart={updateCart} removeFromCart={removeFromCart}
        submit={submit} submitting={submitting}
        showMobile={showCart} onCloseMobile={()=>setShowCart(false)}/>
    </div>
  );
}

/* Helper: format an ISO date as "12 Mar 2025" */
const formatLast = (iso) => {
  if (!iso) return '—';
  try { return new Date(iso).toLocaleDateString('en-IN', {day:'2-digit', month:'short', year:'numeric'}); }
  catch { return iso.slice(0,10); }
};

/* Empty / loading state shared between sections */
function SectionEmpty({ icon, title, hint }) {
  return (
    <div className="text-center py-12 text-slate-400">
      <div className="inline-flex items-center justify-center w-12 h-12 rounded-full bg-slate-100 text-slate-400 mb-3">{icon}</div>
      <div className="text-sm font-medium text-slate-600">{title}</div>
      {hint && <div className="text-[11px] text-slate-400 mt-1 max-w-sm mx-auto px-4">{hint}</div>}
    </div>
  );
}

/* Repeat-order row — shows "Last bought" + previous qty + 1-tap add */
function RepeatRow({ item, inCart, onAdd, testid }) {
  const lastQty = Math.round(item.last_qty || item.avg_qty_per_order || 1);
  return (
    <div className="bg-white rounded-lg border border-slate-200 p-2.5 hover:border-blue-200 transition" data-testid={testid}>
      <div className="flex items-start gap-2">
        <div className="min-w-0 flex-1">
          <div className="text-xs font-semibold text-slate-800 truncate">{item.item_name}</div>
          {item.part_number && <div className="text-[9px] text-slate-400 font-mono">P/N: {item.part_number}</div>}
          <div className="flex flex-wrap gap-x-3 gap-y-0.5 text-[10px] text-slate-500 mt-0.5">
            <span className="font-semibold text-slate-700">Rs.{Number(item.price||0).toLocaleString('en-IN')}</span>
            <span className={item.stock_qty>0?'text-green-600':'text-red-500'}>
              Stock: {item.stock_qty} {item.unit}
            </span>
            <span className="text-slate-400">
              Last <strong className="text-slate-600">{formatLast(item.last_date)}</strong>
              {' · '}{Math.round(item.last_qty || 0)} {item.unit}
            </span>
            <span className="text-slate-400">{item.order_count} orders · avg {item.avg_qty_per_order}</span>
          </div>
        </div>
        <div className="flex flex-col gap-1 flex-shrink-0">
          <button onClick={() => onAdd(lastQty)} disabled={inCart}
            className="px-2.5 py-1.5 text-[10px] font-bold bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-30 flex items-center gap-1 whitespace-nowrap"
            data-testid={`${testid}-addlast`}>
            <Plus size={11}/> {lastQty}
          </button>
          <button onClick={() => onAdd(1)} disabled={inCart}
            className="px-2.5 py-1 text-[10px] bg-slate-50 text-slate-600 rounded-lg hover:bg-slate-100 disabled:opacity-30">
            +1
          </button>
        </div>
      </div>
    </div>
  );
}

/* Cross-sell row — labels affinity vs fast-moving so the salesman can pitch */
const SIGNAL_META = {
  affinity:    { label: 'Bought with regulars', color: 'bg-violet-50 text-violet-700' },
  fast_moving: { label: 'Fast mover',           color: 'bg-amber-50  text-amber-700' },
  both:        { label: 'Hot pick',             color: 'bg-emerald-50 text-emerald-700' },
};
function SuggestRow({ item, inCart, onAdd, testid }) {
  const meta = SIGNAL_META[item.signal] || SIGNAL_META.fast_moving;
  return (
    <div className="bg-white rounded-lg border border-slate-200 p-2.5 hover:border-blue-200 transition" data-testid={testid}>
      <div className="flex items-start gap-2">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-1.5 mb-0.5 flex-wrap">
            <span className={`text-[9px] px-1.5 py-0.5 rounded font-semibold ${meta.color}`}>
              {meta.label}
            </span>
          </div>
          <div className="text-xs font-semibold text-slate-800 truncate">{item.item_name}</div>
          {item.part_number && <div className="text-[9px] text-slate-400 font-mono">P/N: {item.part_number}</div>}
          <div className="flex flex-wrap gap-x-3 text-[10px] text-slate-500 mt-0.5">
            <span className="font-semibold text-slate-700">Rs.{Number(item.price||0).toLocaleString('en-IN')}</span>
            <span className={item.stock_qty>0?'text-green-600':'text-red-500'}>
              Stock: {item.stock_qty} {item.unit}
            </span>
          </div>
        </div>
        <button onClick={onAdd} disabled={inCart}
          className="px-2.5 py-1.5 text-[10px] font-bold bg-blue-50 text-blue-600 rounded-lg hover:bg-blue-100 disabled:opacity-30 flex items-center gap-1 flex-shrink-0"
          data-testid={`${testid}-add`}>
          <Plus size={11}/> Add
        </button>
      </div>
    </div>
  );
}

/* Plain catalog row (Browse tab) */
function CatalogRow({ item, inCart, onAdd, testid }) {
  return (
    <div className="bg-white rounded-lg border border-slate-200 p-2.5 flex items-center justify-between hover:border-blue-200 transition" data-testid={testid}>
      <div className="min-w-0 flex-1">
        <div className="text-xs font-semibold text-slate-800 truncate">{item.item_name}</div>
        {item.part_number && <div className="text-[9px] text-slate-400 font-mono">P/N: {item.part_number}</div>}
        <div className="flex gap-3 text-[10px] text-slate-500 flex-wrap">
          <span className="font-semibold text-slate-700">Rs.{Number(item.price||0).toLocaleString('en-IN')}</span>
          <span className={item.stock_qty>0?'text-green-600':'text-red-500'}>Stock: {item.stock_qty} {item.unit}</span>
          {item.stock_group && <span className="hidden sm:inline">{item.stock_group}</span>}
        </div>
      </div>
      <button onClick={onAdd} disabled={inCart}
        className="px-2.5 py-1.5 text-[10px] bg-blue-50 text-blue-600 rounded-lg hover:bg-blue-100 disabled:opacity-30 flex-shrink-0 flex items-center gap-1">
        <Plus size={12}/>
      </button>
    </div>
  );
}

/* Sticky cart panel — desktop right column, mobile bottom-sheet */
function CartPanel({ cart, total, notes, setNotes, updateCart, removeFromCart,
                     submit, submitting, showMobile, onCloseMobile }) {
  const Body = (
    <div className="bg-blue-50 border border-blue-200 rounded-xl p-3 lg:sticky lg:top-3" data-testid="cart">
      <div className="flex items-center justify-between mb-2">
        <div className="text-[10px] font-semibold text-blue-700 uppercase tracking-wider">
          Cart · {cart.length} items
        </div>
        <div className="text-sm font-bold text-blue-800">Rs.{fmt(total)}</div>
      </div>
      {cart.length === 0 ? (
        <div className="text-center py-8 text-blue-400">
          <ShoppingCart size={28} className="inline mb-2 opacity-50"/>
          <div className="text-xs">Your cart is empty</div>
          <div className="text-[10px] text-blue-300 mt-1">Add items from any section above</div>
        </div>
      ) : (
        <>
          <div className="space-y-1.5 max-h-72 overflow-y-auto pr-1">
            {cart.map((c,i) => (
              <div key={i} className="bg-white rounded-lg p-2 border border-blue-100">
                <div className="flex items-start gap-1.5">
                  <div className="flex-1 min-w-0">
                    <div className="text-[11px] font-medium text-slate-800 truncate">{c.item_name}</div>
                    <div className="text-[10px] text-slate-500">Rs.{c.price} × {c.quantity} = <strong>Rs.{fmt(c.quantity*c.price)}</strong></div>
                  </div>
                  <button onClick={()=>removeFromCart(i)} className="p-0.5 hover:bg-red-50 rounded" aria-label="Remove">
                    <X size={12} className="text-red-400"/>
                  </button>
                </div>
                <div className="flex items-center gap-1 mt-1.5">
                  <button onClick={()=>updateCart(i,'quantity',Math.max(1,c.quantity-1))}
                    className="w-6 h-6 flex items-center justify-center bg-slate-50 hover:bg-slate-100 border border-slate-200 rounded text-xs">
                    <Minus size={11}/>
                  </button>
                  <input type="number" value={c.quantity}
                    onChange={e=>updateCart(i,'quantity',parseInt(e.target.value)||1)}
                    className="w-14 text-center text-xs border border-slate-200 rounded py-0.5"
                    data-testid={`qty-${i}`}/>
                  <button onClick={()=>updateCart(i,'quantity',c.quantity+1)}
                    className="w-6 h-6 flex items-center justify-center bg-slate-50 hover:bg-slate-100 border border-slate-200 rounded text-xs">
                    <Plus size={11}/>
                  </button>
                  <input value={c.remark} onChange={e=>updateCart(i,'remark',e.target.value)}
                    placeholder="Remark"
                    className="flex-1 ml-1 px-2 py-1 text-[10px] border border-slate-200 rounded"
                    data-testid={`remark-${i}`}/>
                </div>
              </div>
            ))}
          </div>
          <textarea value={notes} onChange={e=>setNotes(e.target.value)}
            placeholder="Order notes (optional)" rows={2}
            className="w-full mt-2 px-2 py-1.5 text-[11px] border border-blue-200 rounded bg-white resize-none"
            data-testid="order-notes"/>
          <button onClick={submit} disabled={submitting}
            className="w-full mt-2 px-4 py-2.5 text-xs bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 font-bold flex items-center justify-center gap-2"
            data-testid="submit-order">
            {submitting ? 'Submitting…' : <>Submit Order <ArrowRight size={14}/></>}
          </button>
        </>
      )}
    </div>
  );

  return (
    <>
      {/* Desktop: render in the grid sidebar */}
      <div className="hidden lg:block">{Body}</div>
      {/* Mobile: bottom sheet */}
      {showMobile && (
        <div className="fixed inset-0 z-40 bg-black/40 lg:hidden" onClick={onCloseMobile} data-testid="cart-sheet">
          <div className="absolute bottom-0 left-0 right-0 bg-white rounded-t-2xl p-3 max-h-[85vh] overflow-y-auto"
               onClick={e=>e.stopPropagation()}>
            <div className="flex items-center justify-between mb-2">
              <div className="text-sm font-bold text-slate-900">Cart</div>
              <button onClick={onCloseMobile} className="p-1.5 hover:bg-slate-100 rounded-lg"><X size={16}/></button>
            </div>
            {Body}
          </div>
        </div>
      )}
    </>
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
