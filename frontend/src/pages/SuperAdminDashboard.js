import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import {
  Users, Shield, ToggleLeft, ToggleRight, Trash2, Key,
  Plus, ChevronDown, ChevronUp, RefreshCw, Activity,
  Lock, Eye, EyeOff, X, Pencil, Calendar, Clock, Building2,
  UserPlus, Phone, Mail, FileText, ArrowRightCircle, AlertTriangle, Check,
  IndianRupee, TrendingUp, CreditCard, Receipt, Heart, Download,
  BarChart3, Wallet, CircleDollarSign, BadgeCheck, XCircle, Gift, Database
} from 'lucide-react';
import ActivityLog from './ActivityLog';
import SuperAdminBackups from './SuperAdminBackups';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

const ALL_FEATURES = [
  { id: 'dashboard', label: 'Dashboard', desc: 'Overview stats & charts' },
  { id: 'sales', label: 'Sales', desc: 'Sales vouchers & analytics' },
  { id: 'crm', label: 'CRM', desc: 'Customer outstanding & behavior' },
  { id: 'inventory', label: 'Inventory', desc: 'Stock management & items' },
  { id: 'analytics', label: 'Analytics', desc: 'Movement analysis & reports' },
  { id: 'salesman', label: 'Salesman', desc: 'Salesman performance & orders' },
  { id: 'ai_reports', label: 'AI Reports', desc: 'AI-powered insights' },
  { id: 'insider', label: 'Insider Result', desc: 'BI analytics & forecasts' },
  { id: 'ca_corner', label: 'CA Corner', desc: 'P&L, Balance Sheet, Cash Flow' },
  { id: 'dispatch', label: 'Dispatch', desc: 'Dispatch terminal & tracking' },
  { id: 'sync_history', label: 'Sync History', desc: 'Data sync logs' },
  { id: 'setup', label: 'Setup', desc: 'Tally* connection settings' },
];

const PLANS = {
  starter: { name: 'Starter', monthly: 999, annual: 9990, maxCompanies: 1, maxEmployees: 2, features: ['dashboard', 'sales', 'inventory', 'sync_history', 'setup'] },
  professional: { name: 'Professional', monthly: 2499, annual: 24990, maxCompanies: 3, maxEmployees: 5, features: ['dashboard', 'sales', 'crm', 'inventory', 'analytics', 'sync_history', 'setup'] },
  enterprise: { name: 'Enterprise', monthly: 3799, annual: 37990, maxCompanies: 10, maxEmployees: 20, features: ALL_FEATURES.map(f => f.id) }
};

const formatINR = (n) => `Rs.${(n || 0).toLocaleString('en-IN', { maximumFractionDigits: 0 })}`;
const formatDate = (d) => {
  if (!d) return '—';
  const dt = (d.includes && (d.includes('+') || d.includes('Z'))) ? new Date(d) : new Date(d + 'Z');
  return dt.toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'Asia/Kolkata' });
};

const SuperAdminDashboard = ({ token }) => {
  const [activeTab, setActiveTab] = useState('overview');
  const [loading, setLoading] = useState(true);

  // Data states
  const [stats, setStats] = useState(null);
  const [admins, setAdmins] = useState([]);
  const [businessData, setBusinessData] = useState(null);
  const [payments, setPayments] = useState({ payments: [], total_amount: 0, by_mode: {} });
  const [invoices, setInvoices] = useState({ invoices: [], total_invoiced: 0 });
  const [healthData, setHealthData] = useState([]);
  const [prospects, setProspects] = useState([]);
  const [prospectStats, setProspectStats] = useState({});
  const [renewals, setRenewals] = useState({ renewal_requests: [], near_expiry: [], expired: [], stats: {} });

  // Modals
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showResetModal, setShowResetModal] = useState(null);
  const [showEditModal, setShowEditModal] = useState(null);
  const [expandedAdmin, setExpandedAdmin] = useState(null);
  const [newAdmin, setNewAdmin] = useState({ username: '', password: '', name: '', plan: 'starter', billing_cycle: 'annual', subscription_months: 12, features: PLANS.starter.features });
  const [editAdmin, setEditAdmin] = useState(null);
  const [resetPassword, setResetPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [convertModal, setConvertModal] = useState(null);
  const [convertData, setConvertData] = useState({ password: '', plan: 'professional', billing_cycle: 'annual', subscription_months: 12 });
  const [processModal, setProcessModal] = useState(null);
  const [processData, setProcessData] = useState({ action: 'approve', plan: '', subscription_months: 12, notes: '' });

  // Payment modal
  const [showPaymentModal, setShowPaymentModal] = useState(false);
  const [paymentForm, setPaymentForm] = useState({ customer_username: '', amount: '', payment_mode: 'bank_transfer', reference_no: '', notes: '', period_description: '' });

  // Invoice modal
  const [showInvoiceModal, setShowInvoiceModal] = useState(false);
  const [invoiceForm, setInvoiceForm] = useState({ customer_username: '', amount: '', description: '', period_from: '', period_to: '' });

  // Customer ledger
  const [ledgerModal, setLedgerModal] = useState(null);
  const [ledgerData, setLedgerData] = useState(null);

  const headers = token ? { Authorization: `Bearer ${token}` } : {};

  const fetchData = useCallback(async () => {
    try {
      setLoading(true);
      const [statsRes, adminsRes, prospectsRes, renewalsRes, bizRes, paymentsRes, invoicesRes, healthRes] = await Promise.all([
        axios.get(`${API}/super-admin/stats`, { headers }),
        axios.get(`${API}/super-admin/admins`, { headers }),
        axios.get(`${API}/super-admin/prospects`, { headers }).catch(() => ({ data: { data: { prospects: [], stats: {} } } })),
        axios.get(`${API}/super-admin/renewals`, { headers }).catch(() => ({ data: { data: { renewal_requests: [], near_expiry: [], expired: [], stats: {} } } })),
        axios.get(`${API}/super-admin/business-dashboard`, { headers }).catch(() => ({ data: { data: null } })),
        axios.get(`${API}/super-admin/payments`, { headers }).catch(() => ({ data: { data: { payments: [], total_amount: 0 } } })),
        axios.get(`${API}/super-admin/invoices`, { headers }).catch(() => ({ data: { data: { invoices: [], total_invoiced: 0 } } })),
        axios.get(`${API}/super-admin/customer-health`, { headers }).catch(() => ({ data: { data: { customers: [] } } })),
      ]);
      setStats(statsRes.data?.data);
      setAdmins(adminsRes.data?.data?.admins || []);
      setProspects(prospectsRes.data?.data?.prospects || []);
      setProspectStats(prospectsRes.data?.data?.stats || {});
      setRenewals(renewalsRes.data?.data || { renewal_requests: [], near_expiry: [], expired: [], stats: {} });
      setBusinessData(bizRes.data?.data);
      setPayments(paymentsRes.data?.data || { payments: [], total_amount: 0, by_mode: {} });
      setInvoices(invoicesRes.data?.data || { invoices: [], total_invoiced: 0 });
      setHealthData(healthRes.data?.data?.customers || []);
    } catch { toast.error('Failed to fetch data'); }
    finally { setLoading(false); }
  }, [token]);

  useEffect(() => { fetchData(); }, [fetchData]);

  // --- CRUD functions (kept from original) ---
  const createAdmin = async () => {
    if (!newAdmin.username || !newAdmin.password) { toast.error('Email and password are required'); return; }
    try {
      const plan = PLANS[newAdmin.plan];
      const res = await axios.post(`${API}/super-admin/admins`, {
        ...newAdmin, features: newAdmin.features, max_companies: plan.maxCompanies, max_employees: plan.maxEmployees
      }, { headers });
      if (res.data?.success) { toast.success(res.data.message); setShowCreateModal(false); setNewAdmin({ username: '', password: '', name: '', plan: 'starter', billing_cycle: 'annual', subscription_months: 12 }); fetchData(); }
      else toast.error(res.data?.error || 'Failed');
    } catch (err) { toast.error(err.response?.data?.error || 'Failed to create admin'); }
  };

  const toggleActive = async (username) => {
    try {
      const res = await axios.put(`${API}/super-admin/admins/${username}/toggle`, {}, { headers });
      if (res.data?.success) { toast.success(res.data.message); fetchData(); }
    } catch { toast.error('Failed to toggle status'); }
  };

  const deleteAdmin = async (username) => {
    if (!window.confirm(`DELETE admin '${username}' and ALL their data?`)) return;
    try {
      const res = await axios.delete(`${API}/super-admin/admins/${username}`, { headers });
      if (res.data?.success) { toast.success(res.data.message); fetchData(); }
      else toast.error(res.data?.error || 'Failed');
    } catch { toast.error('Failed to delete admin'); }
  };

  const handleResetPassword = async () => {
    if (!resetPassword || resetPassword.length < 4) { toast.error('Password must be at least 4 characters'); return; }
    try {
      const res = await axios.post(`${API}/super-admin/admins/${showResetModal}/reset-password`, { new_password: resetPassword }, { headers });
      if (res.data?.success) { toast.success(res.data.message); setShowResetModal(null); setResetPassword(''); }
      else toast.error(res.data?.error || 'Failed');
    } catch { toast.error('Failed to reset password'); }
  };

  const openEditAdmin = (admin) => {
    setEditAdmin({ username: admin.username, name: admin.name || '', plan: admin.plan || 'enterprise', billing_cycle: admin.billing_cycle || 'annual', subscription_months: admin.subscription_months || 12, features: admin.features || [] });
    setShowEditModal(admin.username);
  };

  const saveEditAdmin = async () => {
    try {
      const plan = PLANS[editAdmin.plan];
      const res = await axios.put(`${API}/super-admin/admins/${editAdmin.username}/edit`, {
        name: editAdmin.name, plan: editAdmin.plan, billing_cycle: editAdmin.billing_cycle, subscription_months: editAdmin.subscription_months,
        features: plan.features, max_companies: plan.maxCompanies, max_employees: plan.maxEmployees
      }, { headers });
      if (res.data?.success) { toast.success(res.data.message); setShowEditModal(null); setEditAdmin(null); fetchData(); }
      else toast.error(res.data?.error || 'Failed');
    } catch { toast.error('Failed to save changes'); }
  };

  const updateProspectStatus = async (prospectId, status) => {
    try {
      const res = await axios.put(`${API}/super-admin/prospects/${prospectId}/status`, { status }, { headers });
      if (res.data?.success) { toast.success(`Status updated`); fetchData(); }
    } catch { toast.error('Failed to update status'); }
  };

  const convertProspect = async () => {
    if (!convertData.password || convertData.password.length < 6) { toast.error('Password must be at least 6 characters'); return; }
    try {
      const plan = PLANS[convertData.plan];
      const res = await axios.post(`${API}/super-admin/prospects/${convertModal}/convert`, {
        ...convertData, features: plan.features, max_companies: plan.maxCompanies, max_employees: plan.maxEmployees
      }, { headers });
      if (res.data?.success) { toast.success(res.data.message); setConvertModal(null); fetchData(); }
      else toast.error(res.data?.error || 'Failed');
    } catch { toast.error('Failed to convert'); }
  };

  // --- NEW: Payment & Invoice functions ---
  const recordPayment = async () => {
    if (!paymentForm.customer_username || !paymentForm.amount || parseFloat(paymentForm.amount) <= 0) {
      toast.error('Customer and valid amount required'); return;
    }
    try {
      const res = await axios.post(`${API}/super-admin/payments`, { ...paymentForm, amount: parseFloat(paymentForm.amount) }, { headers });
      if (res.data?.success) { toast.success(res.data.message); setShowPaymentModal(false); setPaymentForm({ customer_username: '', amount: '', payment_mode: 'bank_transfer', reference_no: '', notes: '', period_description: '' }); fetchData(); }
      else toast.error(res.data?.error || 'Failed');
    } catch { toast.error('Failed to record payment'); }
  };

  const generateInvoice = async () => {
    if (!invoiceForm.customer_username || !invoiceForm.amount || parseFloat(invoiceForm.amount) <= 0) {
      toast.error('Customer and valid amount required'); return;
    }
    try {
      const res = await axios.post(`${API}/super-admin/invoices/generate`, { ...invoiceForm, amount: parseFloat(invoiceForm.amount) }, { headers });
      if (res.data?.success) { toast.success(res.data.message); setShowInvoiceModal(false); setInvoiceForm({ customer_username: '', amount: '', description: '', period_from: '', period_to: '' }); fetchData(); }
      else toast.error(res.data?.error || 'Failed');
    } catch { toast.error('Failed to generate invoice'); }
  };

  const downloadInvoicePDF = async (invoiceId) => {
    try {
      const res = await axios.get(`${API}/super-admin/invoices/${invoiceId}/pdf`, { headers, responseType: 'blob' });
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `Invoice_${invoiceId}.pdf`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch { toast.error('Failed to download PDF'); }
  };

  const markInvoiceStatus = async (invoiceId, status) => {
    try {
      await axios.put(`${API}/super-admin/invoices/${invoiceId}/status`, { status }, { headers });
      toast.success(`Invoice marked as ${status}`);
      fetchData();
    } catch { toast.error('Failed to update'); }
  };

  const openLedger = async (username) => {
    try {
      const res = await axios.get(`${API}/super-admin/customer-ledger/${username}`, { headers });
      if (res.data?.success) { setLedgerData(res.data.data); setLedgerModal(username); }
    } catch { toast.error('Failed to load ledger'); }
  };

  if (loading) return <div className="flex items-center justify-center h-64"><div className="loading-spinner" /></div>;

  const tabs = [
    { id: 'overview', label: 'Overview', icon: BarChart3 },
    { id: 'subscriptions', label: 'Subscriptions', icon: CreditCard },
    { id: 'payments', label: 'Payments', icon: Wallet },
    { id: 'invoices', label: 'Invoices', icon: Receipt },
    { id: 'prospects', label: 'Prospects', icon: UserPlus },
    { id: 'health', label: 'Customer Health', icon: Heart },
    { id: 'admins', label: 'Admin Mgmt', icon: Shield },
    { id: 'renewals', label: 'Renewals', icon: Calendar },
    { id: 'referrals', label: 'Referrals', icon: Gift },
    { id: 'questionnaires', label: 'Leads', icon: FileText },
    { id: 'backups', label: 'Backups', icon: Database },
    { id: 'activity', label: 'Activity', icon: Activity },
  ];

  return (
    <div className="max-w-[1400px] mx-auto p-4 sm:p-6" data-testid="super-admin-dashboard">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">FLOWRA Command Center</h1>
          <p className="text-sm text-slate-500">Business operations & subscription management</p>
        </div>
        <button onClick={fetchData} className="px-4 py-2 text-sm border border-slate-200 rounded-lg hover:bg-slate-50 flex items-center gap-1.5" data-testid="refresh-all">
          <RefreshCw size={14} /> Refresh
        </button>
      </div>

      {/* Tab Navigation */}
      <div className="flex gap-1 overflow-x-auto mb-6 bg-slate-100 rounded-xl p-1" data-testid="seller-tabs">
        {tabs.map(tab => {
          const Icon = tab.icon;
          return (
            <button key={tab.id} onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-medium whitespace-nowrap transition-all ${activeTab === tab.id ? 'bg-white text-[#2563EB] shadow-sm' : 'text-slate-500 hover:text-slate-700'}`}
              data-testid={`tab-${tab.id}`}>
              <Icon size={14} /> {tab.label}
            </button>
          );
        })}
      </div>

      {/* ===== OVERVIEW TAB ===== */}
      {activeTab === 'overview' && businessData && (
        <div data-testid="overview-tab">
          {/* Revenue Cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
            <div className="bg-gradient-to-br from-blue-600 to-blue-700 rounded-xl p-5 text-white">
              <div className="flex items-center gap-2 text-blue-200 text-xs mb-1"><IndianRupee size={14} /> Monthly Recurring</div>
              <div className="text-2xl font-bold" data-testid="mrr-value">{formatINR(businessData.mrr)}</div>
              <div className="text-blue-200 text-xs mt-1">MRR</div>
            </div>
            <div className="bg-gradient-to-br from-emerald-600 to-emerald-700 rounded-xl p-5 text-white">
              <div className="flex items-center gap-2 text-emerald-200 text-xs mb-1"><TrendingUp size={14} /> Annual Revenue</div>
              <div className="text-2xl font-bold" data-testid="arr-value">{formatINR(businessData.arr)}</div>
              <div className="text-emerald-200 text-xs mt-1">ARR</div>
            </div>
            <div className="bg-gradient-to-br from-violet-600 to-violet-700 rounded-xl p-5 text-white">
              <div className="flex items-center gap-2 text-violet-200 text-xs mb-1"><CircleDollarSign size={14} /> Collections</div>
              <div className="text-2xl font-bold" data-testid="collected-value">{formatINR(businessData.total_received)}</div>
              <div className="text-violet-200 text-xs mt-1">{businessData.collection_rate}% collected</div>
            </div>
            <div className="bg-gradient-to-br from-rose-600 to-rose-700 rounded-xl p-5 text-white">
              <div className="flex items-center gap-2 text-rose-200 text-xs mb-1"><AlertTriangle size={14} /> Outstanding</div>
              <div className="text-2xl font-bold" data-testid="outstanding-value">{formatINR(businessData.outstanding)}</div>
              <div className="text-rose-200 text-xs mt-1">Balance due</div>
            </div>
          </div>

          {/* Customer & Plan metrics */}
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-6">
            <div className="bg-white border border-slate-200 rounded-xl p-4">
              <div className="text-xs text-slate-500 mb-1">Total Customers</div>
              <div className="text-xl font-bold text-slate-900" data-testid="total-customers">{businessData.total_customers}</div>
            </div>
            <div className="bg-white border border-slate-200 rounded-xl p-4">
              <div className="text-xs text-slate-500 mb-1">Active</div>
              <div className="text-xl font-bold text-emerald-600">{businessData.active_customers}</div>
            </div>
            <div className="bg-white border border-slate-200 rounded-xl p-4">
              <div className="text-xs text-slate-500 mb-1">ARPU</div>
              <div className="text-xl font-bold text-blue-600">{formatINR(businessData.arpu)}</div>
            </div>
            <div className="bg-white border border-slate-200 rounded-xl p-4">
              <div className="text-xs text-slate-500 mb-1">Contract Value</div>
              <div className="text-xl font-bold text-slate-900">{formatINR(businessData.total_contract_value)}</div>
            </div>
            <div className="bg-white border border-slate-200 rounded-xl p-4">
              <div className="text-xs text-slate-500 mb-1">Total Payments</div>
              <div className="text-xl font-bold text-slate-900">{businessData.total_payments}</div>
            </div>
          </div>

          {/* Plan Distribution */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
            <div className="bg-white border border-slate-200 rounded-xl p-5">
              <h3 className="text-sm font-semibold text-slate-900 mb-4">Plan Distribution</h3>
              {Object.entries(businessData.plan_distribution || {}).map(([plan, count]) => {
                const total = businessData.active_customers || 1;
                const pct = Math.round((count / total) * 100);
                const colors = { starter: 'bg-slate-400', professional: 'bg-blue-500', enterprise: 'bg-purple-500' };
                return (
                  <div key={plan} className="mb-3">
                    <div className="flex items-center justify-between text-sm mb-1">
                      <span className="capitalize font-medium">{plan}</span>
                      <span className="text-slate-500">{count} ({pct}%)</span>
                    </div>
                    <div className="w-full bg-slate-100 rounded-full h-2">
                      <div className={`${colors[plan] || 'bg-blue-500'} h-2 rounded-full transition-all`} style={{ width: `${pct}%` }} />
                    </div>
                  </div>
                );
              })}
            </div>
            <div className="bg-white border border-slate-200 rounded-xl p-5">
              <h3 className="text-sm font-semibold text-slate-900 mb-4">Recent Payments</h3>
              {businessData.recent_payments?.length === 0 ? (
                <p className="text-sm text-slate-400 text-center py-4">No payments recorded yet</p>
              ) : (
                <div className="space-y-3">
                  {businessData.recent_payments?.map((p, i) => (
                    <div key={i} className="flex items-center justify-between py-2 border-b border-slate-50 last:border-0">
                      <div>
                        <div className="text-sm font-medium text-slate-800">{p.customer_name || p.customer_username}</div>
                        <div className="text-xs text-slate-400">{formatDate(p.payment_date)} · {p.payment_mode?.replace('_', ' ')}</div>
                      </div>
                      <div className="text-sm font-bold text-emerald-600">{formatINR(p.amount)}</div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Quick Actions */}
          <div className="flex flex-wrap gap-3">
            <button onClick={() => setShowPaymentModal(true)} className="px-4 py-2.5 bg-emerald-600 text-white rounded-lg text-sm font-medium hover:bg-emerald-700 flex items-center gap-2" data-testid="quick-record-payment">
              <IndianRupee size={16} /> Record Payment
            </button>
            <button onClick={() => setShowInvoiceModal(true)} className="px-4 py-2.5 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 flex items-center gap-2" data-testid="quick-generate-invoice">
              <Receipt size={16} /> Generate Invoice
            </button>
            <button onClick={() => setShowCreateModal(true)} className="px-4 py-2.5 bg-slate-800 text-white rounded-lg text-sm font-medium hover:bg-slate-900 flex items-center gap-2" data-testid="quick-new-admin">
              <Plus size={16} /> New Customer
            </button>
          </div>
        </div>
      )}

      {/* ===== SUBSCRIPTIONS TAB ===== */}
      {activeTab === 'subscriptions' && (
        <div data-testid="subscriptions-tab">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-slate-900">Subscription Management</h2>
          </div>
          <div className="bg-white border border-slate-200 rounded-xl overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-sm" data-testid="subscriptions-table">
                <thead>
                  <tr className="bg-slate-50 text-xs text-slate-500 uppercase">
                    <th className="py-3 px-4 text-left">Customer</th>
                    <th className="py-3 px-4 text-left">Plan</th>
                    <th className="py-3 px-4 text-left">Billing</th>
                    <th className="py-3 px-4 text-left">Started</th>
                    <th className="py-3 px-4 text-left">Expires</th>
                    <th className="py-3 px-4 text-right">Value</th>
                    <th className="py-3 px-4 text-center">Status</th>
                    <th className="py-3 px-4 text-center">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {admins.map(admin => {
                    const plan = admin.plan || 'enterprise';
                    const cycle = admin.billing_cycle || 'annual';
                    const months = admin.subscription_months || 12;
                    const pricing = PLANS[plan] || PLANS.enterprise;
                    const value = cycle === 'annual' ? pricing.annual * (months / 12) : pricing.monthly * months;
                    const start = admin.subscription_start || admin.created_at;
                    let expires = '—'; let daysLeft = null; let isExpired = false;
                    if (start) {
                      const end = new Date(start); end.setMonth(end.getMonth() + months);
                      expires = formatDate(end.toISOString());
                      daysLeft = Math.ceil((end - new Date()) / 86400000);
                      isExpired = daysLeft < 0;
                    }
                    return (
                      <tr key={admin.username} className="border-t border-slate-100 hover:bg-slate-50" data-testid={`sub-row-${admin.username}`}>
                        <td className="py-3 px-4">
                          <div className="font-medium text-slate-800">{admin.name || admin.username}</div>
                          <div className="text-xs text-slate-400">{admin.username}</div>
                        </td>
                        <td className="py-3 px-4">
                          <span className={`text-[10px] px-2 py-0.5 rounded-full font-bold uppercase ${plan === 'enterprise' ? 'bg-purple-50 text-purple-700' : plan === 'professional' ? 'bg-blue-50 text-blue-700' : 'bg-slate-100 text-slate-600'}`}>
                            {plan}
                          </span>
                        </td>
                        <td className="py-3 px-4 text-slate-600 capitalize">{cycle} · {months}mo</td>
                        <td className="py-3 px-4 text-slate-600">{formatDate(start)}</td>
                        <td className="py-3 px-4 text-slate-600">{expires}</td>
                        <td className="py-3 px-4 text-right font-medium text-slate-800">{formatINR(value)}</td>
                        <td className="py-3 px-4 text-center">
                          {isExpired ? (
                            <span className="text-[10px] bg-red-50 text-red-700 px-2 py-0.5 rounded-full font-bold">EXPIRED</span>
                          ) : daysLeft !== null && daysLeft <= 30 ? (
                            <span className="text-[10px] bg-amber-50 text-amber-700 px-2 py-0.5 rounded-full font-bold">{daysLeft}d LEFT</span>
                          ) : admin.active ? (
                            <span className="text-[10px] bg-emerald-50 text-emerald-700 px-2 py-0.5 rounded-full font-bold">ACTIVE</span>
                          ) : (
                            <span className="text-[10px] bg-slate-100 text-slate-500 px-2 py-0.5 rounded-full font-bold">INACTIVE</span>
                          )}
                        </td>
                        <td className="py-3 px-4 text-center">
                          <div className="flex items-center justify-center gap-1">
                            <button onClick={() => openLedger(admin.username)} className="p-1.5 text-slate-400 hover:text-blue-600 hover:bg-blue-50 rounded-lg" title="View Ledger" data-testid={`ledger-${admin.username}`}>
                              <FileText size={14} />
                            </button>
                            <button onClick={() => openEditAdmin(admin)} className="p-1.5 text-slate-400 hover:text-blue-600 hover:bg-blue-50 rounded-lg" title="Edit" data-testid={`edit-sub-${admin.username}`}>
                              <Pencil size={14} />
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* ===== PAYMENTS TAB ===== */}
      {activeTab === 'payments' && (
        <div data-testid="payments-tab">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-slate-900">Payment Ledger</h2>
            <button onClick={() => setShowPaymentModal(true)} className="px-4 py-2 bg-emerald-600 text-white rounded-lg text-sm font-medium hover:bg-emerald-700 flex items-center gap-2" data-testid="record-payment-btn">
              <Plus size={14} /> Record Payment
            </button>
          </div>
          {/* Summary */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
            <div className="bg-white border border-slate-200 rounded-xl p-4">
              <div className="text-xs text-slate-500 mb-1">Total Collected</div>
              <div className="text-xl font-bold text-emerald-600" data-testid="total-collected">{formatINR(payments.total_amount)}</div>
            </div>
            <div className="bg-white border border-slate-200 rounded-xl p-4">
              <div className="text-xs text-slate-500 mb-1">Transactions</div>
              <div className="text-xl font-bold text-slate-900">{payments.payments?.length || 0}</div>
            </div>
            {Object.entries(payments.by_mode || {}).slice(0, 2).map(([mode, amt]) => (
              <div key={mode} className="bg-white border border-slate-200 rounded-xl p-4">
                <div className="text-xs text-slate-500 mb-1 capitalize">{mode.replace('_', ' ')}</div>
                <div className="text-xl font-bold text-slate-900">{formatINR(amt)}</div>
              </div>
            ))}
          </div>
          {/* Payment list */}
          <div className="bg-white border border-slate-200 rounded-xl overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-sm" data-testid="payments-table">
                <thead>
                  <tr className="bg-slate-50 text-xs text-slate-500 uppercase">
                    <th className="py-3 px-4 text-left">Customer</th>
                    <th className="py-3 px-4 text-right">Amount</th>
                    <th className="py-3 px-4 text-left">Mode</th>
                    <th className="py-3 px-4 text-left">Reference</th>
                    <th className="py-3 px-4 text-left">Period</th>
                    <th className="py-3 px-4 text-left">Date</th>
                  </tr>
                </thead>
                <tbody>
                  {payments.payments?.map((p, i) => (
                    <tr key={i} className="border-t border-slate-100 hover:bg-slate-50" data-testid={`payment-row-${i}`}>
                      <td className="py-3 px-4">
                        <div className="font-medium text-slate-800">{p.customer_name || p.customer_username}</div>
                        <div className="text-xs text-slate-400">{p.customer_username}</div>
                      </td>
                      <td className="py-3 px-4 text-right font-bold text-emerald-600">{formatINR(p.amount)}</td>
                      <td className="py-3 px-4 text-slate-600 capitalize">{(p.payment_mode || '').replace('_', ' ')}</td>
                      <td className="py-3 px-4 text-slate-600 font-mono text-xs">{p.reference_no || '—'}</td>
                      <td className="py-3 px-4 text-slate-600">{p.period_description || '—'}</td>
                      <td className="py-3 px-4 text-slate-600">{formatDate(p.payment_date)}</td>
                    </tr>
                  ))}
                  {(!payments.payments || payments.payments.length === 0) && (
                    <tr><td colSpan={6} className="py-8 text-center text-slate-400">No payments recorded yet</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* ===== INVOICES TAB ===== */}
      {activeTab === 'invoices' && (
        <div data-testid="invoices-tab">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-slate-900">Invoices</h2>
            <button onClick={() => setShowInvoiceModal(true)} className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 flex items-center gap-2" data-testid="generate-invoice-btn">
              <Plus size={14} /> Generate Invoice
            </button>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
            <div className="bg-white border border-slate-200 rounded-xl p-4">
              <div className="text-xs text-slate-500 mb-1">Total Invoiced</div>
              <div className="text-xl font-bold text-blue-600">{formatINR(invoices.total_invoiced)}</div>
            </div>
            <div className="bg-white border border-slate-200 rounded-xl p-4">
              <div className="text-xs text-slate-500 mb-1">Total Invoices</div>
              <div className="text-xl font-bold text-slate-900">{invoices.total}</div>
            </div>
            <div className="bg-white border border-slate-200 rounded-xl p-4">
              <div className="text-xs text-slate-500 mb-1">Paid</div>
              <div className="text-xl font-bold text-emerald-600">{invoices.paid_count}</div>
            </div>
            <div className="bg-white border border-slate-200 rounded-xl p-4">
              <div className="text-xs text-slate-500 mb-1">Unpaid</div>
              <div className="text-xl font-bold text-red-600">{invoices.unpaid_count}</div>
            </div>
          </div>
          <div className="bg-white border border-slate-200 rounded-xl overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-sm" data-testid="invoices-table">
                <thead>
                  <tr className="bg-slate-50 text-xs text-slate-500 uppercase">
                    <th className="py-3 px-4 text-left">Invoice #</th>
                    <th className="py-3 px-4 text-left">Customer</th>
                    <th className="py-3 px-4 text-right">Amount</th>
                    <th className="py-3 px-4 text-left">Date</th>
                    <th className="py-3 px-4 text-center">Status</th>
                    <th className="py-3 px-4 text-center">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {invoices.invoices?.map((inv, i) => (
                    <tr key={i} className="border-t border-slate-100 hover:bg-slate-50" data-testid={`invoice-row-${i}`}>
                      <td className="py-3 px-4 font-mono text-sm font-medium text-slate-800">{inv.invoice_number}</td>
                      <td className="py-3 px-4">
                        <div className="font-medium text-slate-800">{inv.customer_name}</div>
                        <div className="text-xs text-slate-400">{inv.description?.substring(0, 40)}</div>
                      </td>
                      <td className="py-3 px-4 text-right font-bold text-blue-600">{formatINR(inv.amount)}</td>
                      <td className="py-3 px-4 text-slate-600">{formatDate(inv.invoice_date)}</td>
                      <td className="py-3 px-4 text-center">
                        <span className={`text-[10px] px-2 py-0.5 rounded-full font-bold uppercase ${inv.status === 'paid' ? 'bg-emerald-50 text-emerald-700' : inv.status === 'cancelled' ? 'bg-slate-100 text-slate-500' : 'bg-red-50 text-red-700'}`}>
                          {inv.status}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-center">
                        <div className="flex items-center justify-center gap-1">
                          <button onClick={() => downloadInvoicePDF(inv.invoice_id)} className="p-1.5 text-slate-400 hover:text-blue-600 hover:bg-blue-50 rounded-lg" title="Download PDF" data-testid={`download-invoice-${i}`}>
                            <Download size={14} />
                          </button>
                          {inv.status === 'unpaid' && (
                            <button onClick={() => markInvoiceStatus(inv.invoice_id, 'paid')} className="p-1.5 text-slate-400 hover:text-emerald-600 hover:bg-emerald-50 rounded-lg" title="Mark Paid" data-testid={`mark-paid-${i}`}>
                              <BadgeCheck size={14} />
                            </button>
                          )}
                          {inv.status === 'paid' && (
                            <button onClick={() => markInvoiceStatus(inv.invoice_id, 'unpaid')} className="p-1.5 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded-lg" title="Mark Unpaid">
                              <XCircle size={14} />
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                  {(!invoices.invoices || invoices.invoices.length === 0) && (
                    <tr><td colSpan={6} className="py-8 text-center text-slate-400">No invoices generated yet</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* ===== PROSPECTS TAB ===== */}
      {activeTab === 'prospects' && (
        <div data-testid="prospects-tab">
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-6">
            {[
              { label: 'Total', value: prospectStats.total || 0, color: 'text-slate-700' },
              { label: 'New', value: prospectStats.new || 0, color: 'text-blue-600' },
              { label: 'Contacted', value: prospectStats.contacted || 0, color: 'text-amber-600' },
              { label: 'Converted', value: prospectStats.converted || 0, color: 'text-emerald-600' },
              { label: 'Lost', value: prospectStats.lost || 0, color: 'text-red-600' },
            ].map(s => (
              <div key={s.label} className="bg-white border border-slate-200 rounded-xl p-4">
                <p className="text-xs text-slate-500">{s.label}</p>
                <p className={`text-xl font-bold ${s.color}`}>{s.value}</p>
              </div>
            ))}
          </div>
          <div className="space-y-3">
            {prospects.map(p => (
              <div key={p.prospect_id} className="bg-white border border-slate-200 rounded-xl p-4" data-testid={`prospect-${p.prospect_id}`}>
                <div className="flex items-center justify-between mb-2">
                  <div>
                    <h4 className="font-medium text-slate-900">{p.company_name || p.email}</h4>
                    <p className="text-xs text-slate-500">{p.email} · {p.contact_person}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <select value={p.status} onChange={e => updateProspectStatus(p.prospect_id, e.target.value)}
                      className="text-xs border border-slate-200 rounded-lg px-2 py-1.5" data-testid={`prospect-status-${p.prospect_id}`}>
                      <option value="new">New</option>
                      <option value="contacted">Contacted</option>
                      <option value="demo_given">Demo Given</option>
                      <option value="negotiating">Negotiating</option>
                      <option value="converted">Converted</option>
                      <option value="lost">Lost</option>
                    </select>
                    {p.status !== 'converted' && p.status !== 'lost' && (
                      <button onClick={() => { setConvertModal(p.prospect_id); setConvertData({ password: '', plan: p.plan_interest || 'professional', billing_cycle: 'annual', subscription_months: 12 }); }}
                        className="text-xs bg-green-600 text-white px-3 py-1.5 rounded-lg font-medium hover:bg-green-700 flex items-center gap-1"
                        data-testid={`convert-${p.prospect_id}`}>
                        <ArrowRightCircle size={12} /> Convert
                      </button>
                    )}
                  </div>
                </div>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
                  <div><span className="text-slate-400">Plan:</span> <span className="ml-1 capitalize">{p.selected_plan || '—'}</span></div>
                  <div><span className="text-slate-400">Demo:</span> <span className={`ml-1 ${p.demo_completed ? 'text-green-600' : p.demo_requested ? 'text-amber-600' : 'text-slate-400'}`}>{p.demo_completed ? 'Done' : p.demo_requested ? 'Requested' : '—'}</span></div>
                  <div><span className="text-slate-400">Phone:</span> <span className="ml-1">{p.phone || '—'}</span></div>
                  <div><span className="text-slate-400">Date:</span> <span className="ml-1">{formatDate(p.created_at)}</span></div>
                </div>
              </div>
            ))}
            {prospects.length === 0 && <p className="text-center text-slate-400 py-8">No prospects yet</p>}
          </div>
        </div>
      )}

      {/* ===== CUSTOMER HEALTH TAB ===== */}
      {activeTab === 'health' && (
        <div data-testid="health-tab">
          <h2 className="text-lg font-semibold text-slate-900 mb-4">Customer Health Monitor</h2>
          <div className="bg-white border border-slate-200 rounded-xl overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-sm" data-testid="health-table">
                <thead>
                  <tr className="bg-slate-50 text-xs text-slate-500 uppercase">
                    <th className="py-3 px-4 text-left">Customer</th>
                    <th className="py-3 px-4 text-center">Health</th>
                    <th className="py-3 px-4 text-left">Last Sync</th>
                    <th className="py-3 px-4 text-right">Items</th>
                    <th className="py-3 px-4 text-right">Sales</th>
                    <th className="py-3 px-4 text-right">Customers</th>
                    <th className="py-3 px-4 text-right">Paid</th>
                    <th className="py-3 px-4 text-left">Sub Expires</th>
                    <th className="py-3 px-4 text-center">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {healthData.map((h, i) => {
                    const statusColors = { active: 'bg-emerald-50 text-emerald-700', moderate: 'bg-amber-50 text-amber-700', inactive: 'bg-red-50 text-red-700', never_synced: 'bg-slate-100 text-slate-500' };
                    return (
                      <tr key={i} className="border-t border-slate-100 hover:bg-slate-50" data-testid={`health-row-${i}`}>
                        <td className="py-3 px-4">
                          <div className="font-medium text-slate-800">{h.name || h.username}</div>
                          <div className="text-xs text-slate-400">{h.plan} · {h.employee_count} emp · {h.companies?.join(', ') || '—'}</div>
                        </td>
                        <td className="py-3 px-4 text-center">
                          <span className={`text-[10px] px-2 py-0.5 rounded-full font-bold uppercase ${statusColors[h.health_status] || 'bg-slate-100 text-slate-500'}`}>
                            {h.health_status?.replace('_', ' ')}
                          </span>
                        </td>
                        <td className="py-3 px-4 text-slate-600 text-xs">
                          {h.last_sync ? (
                            <div>
                              <div>{formatDate(h.last_sync)}</div>
                              <div className="text-slate-400">{h.days_since_sync === 0 ? 'Today' : `${h.days_since_sync}d ago`}</div>
                            </div>
                          ) : 'Never'}
                        </td>
                        <td className="py-3 px-4 text-right text-slate-700">{h.inventory_items?.toLocaleString()}</td>
                        <td className="py-3 px-4 text-right text-slate-700">{h.sales_vouchers?.toLocaleString()}</td>
                        <td className="py-3 px-4 text-right text-slate-700">{h.customers}</td>
                        <td className="py-3 px-4 text-right font-medium text-emerald-600">{formatINR(h.total_paid)}</td>
                        <td className="py-3 px-4 text-slate-600 text-xs">{formatDate(h.subscription_expires)}<br/><span className={h.days_left < 0 ? 'text-red-600 font-bold' : h.days_left <= 30 ? 'text-amber-600' : 'text-slate-400'}>{h.days_left < 0 ? `Exp ${Math.abs(h.days_left)}d` : `${h.days_left}d left`}</span></td>
                        <td className="py-3 px-4 text-center">
                          <button onClick={() => openLedger(h.username)} className="p-1.5 text-slate-400 hover:text-blue-600 hover:bg-blue-50 rounded-lg" title="Ledger">
                            <FileText size={14} />
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* ===== ADMINS TAB ===== */}
      {activeTab === 'admins' && (
        <div data-testid="admins-tab">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-lg font-semibold text-slate-900">Admin Management</h2>
            <button onClick={() => setShowCreateModal(true)} className="px-4 py-2 text-sm bg-[#2563EB] text-white rounded-lg hover:bg-[#1D4ED8] flex items-center gap-1.5" data-testid="create-admin-btn">
              <Plus size={14} /> New Admin
            </button>
          </div>
          <div className="space-y-4">
            {admins.map(admin => {
              const subMonths = admin.subscription_months || 12;
              const subStart = admin.subscription_start || admin.created_at || '';
              let subEndDate = '—'; let subActive = false;
              if (subStart) { const s = new Date(subStart); const e = new Date(s); e.setMonth(e.getMonth() + subMonths); subEndDate = formatDate(e.toISOString()); subActive = e > new Date(); }
              return (
                <div key={admin.username} className="bg-white border border-slate-200 rounded-xl overflow-hidden" data-testid={`admin-card-${admin.username}`}>
                  <div className="p-5">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-4 flex-1 min-w-0 cursor-pointer" onClick={() => setExpandedAdmin(expandedAdmin === admin.username ? null : admin.username)}>
                        <div className={`w-3 h-3 rounded-full flex-shrink-0 ${admin.active ? 'bg-green-500' : 'bg-red-400'}`} />
                        <div className="min-w-0">
                          <div className="font-semibold text-slate-900">{admin.name || admin.username}</div>
                          <div className="text-xs text-slate-500">@{admin.username} · {admin.employee_count || 0}/{admin.max_employees || 20} employees</div>
                        </div>
                      </div>
                      <div className="flex items-center gap-2 flex-shrink-0">
                        <span className={`text-[10px] px-2 py-0.5 rounded-full font-bold uppercase ${admin.plan === 'enterprise' ? 'bg-purple-50 text-purple-700' : admin.plan === 'professional' ? 'bg-blue-50 text-blue-700' : 'bg-slate-100 text-slate-600'}`}>{admin.plan || 'enterprise'}</span>
                        <button onClick={e => { e.stopPropagation(); toggleActive(admin.username); }} className={`px-3 py-1.5 text-xs rounded-lg font-medium flex items-center gap-1 ${admin.active ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'}`} data-testid={`toggle-active-${admin.username}`}>
                          {admin.active ? <ToggleRight size={14} /> : <ToggleLeft size={14} />} {admin.active ? 'Active' : 'Inactive'}
                        </button>
                        <button onClick={e => { e.stopPropagation(); openEditAdmin(admin); }} className="p-1.5 text-slate-400 hover:text-blue-600 hover:bg-blue-50 rounded-lg" data-testid={`edit-admin-${admin.username}`}><Pencil size={14} /></button>
                        <button onClick={e => { e.stopPropagation(); setShowResetModal(admin.username); }} className="p-1.5 text-slate-400 hover:text-blue-600 hover:bg-blue-50 rounded-lg" data-testid={`reset-pwd-${admin.username}`}><Key size={14} /></button>
                        <button onClick={e => { e.stopPropagation(); deleteAdmin(admin.username); }} className="p-1.5 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded-lg" data-testid={`delete-admin-${admin.username}`}><Trash2 size={14} /></button>
                        <button onClick={() => setExpandedAdmin(expandedAdmin === admin.username ? null : admin.username)} className="p-1.5 text-slate-400 rounded-lg" data-testid={`expand-admin-${admin.username}`}>
                          {expandedAdmin === admin.username ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                        </button>
                      </div>
                    </div>
                  </div>
                  {expandedAdmin === admin.username && (
                    <div className="border-t border-slate-100 p-5 bg-slate-50 space-y-4">
                      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                        <div><span className="text-slate-400 text-xs">Companies:</span><div className="font-medium">{admin.companies?.join(', ') || 'None'}</div></div>
                        <div><span className="text-slate-400 text-xs">Subscription:</span><div className="font-medium">{formatDate(subStart)} → {subEndDate}</div></div>
                        <div><span className="text-slate-400 text-xs">Billing:</span><div className="font-medium capitalize">{admin.billing_cycle || 'annual'} · {subMonths}mo</div></div>
                        <div><span className="text-slate-400 text-xs">Features:</span><div className="font-medium">{admin.features?.length || 0}/{ALL_FEATURES.length}</div></div>
                      </div>
                      <div className="flex flex-wrap gap-1">
                        {ALL_FEATURES.map(f => (
                          <span key={f.id} className={`text-[10px] px-2 py-0.5 rounded ${admin.features?.includes(f.id) ? 'bg-emerald-50 text-emerald-700' : 'bg-slate-100 text-slate-400'}`}>{f.label}</span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* ===== RENEWALS TAB ===== */}
      {activeTab === 'renewals' && (
        <div data-testid="renewals-tab">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
            {[
              { label: 'Pending', value: renewals.stats?.pending_renewals || 0, color: 'text-amber-600' },
              { label: 'Near Expiry', value: renewals.stats?.near_expiry_count || 0, color: 'text-orange-600' },
              { label: 'Expired', value: renewals.stats?.expired_count || 0, color: 'text-red-600' },
              { label: 'Total Requests', value: renewals.stats?.total_requests || 0, color: 'text-slate-700' },
            ].map(s => (
              <div key={s.label} className="bg-white border border-slate-200 rounded-xl p-4">
                <p className="text-xs text-slate-500">{s.label}</p>
                <p className={`text-xl font-bold ${s.color}`}>{s.value}</p>
              </div>
            ))}
          </div>
          {renewals.expired?.length > 0 && (
            <div className="mb-6">
              <h3 className="text-sm font-semibold text-red-700 mb-3 flex items-center gap-1.5"><AlertTriangle size={14} /> Expired</h3>
              {renewals.expired.map(u => (
                <div key={u.username} className="bg-red-50 border border-red-200 rounded-xl p-4 flex items-center justify-between mb-2">
                  <div>
                    <p className="font-medium text-red-900">{u.name || u.username}</p>
                    <p className="text-xs text-red-700">{u.username} | {u.plan?.toUpperCase()}</p>
                    <p className="text-xs text-red-600 mt-1">Expired {Math.abs(u.days_left)} days ago</p>
                  </div>
                  <button onClick={() => { setProcessModal(u.username); setProcessData({ action: 'approve', plan: u.plan, subscription_months: 12, notes: '' }); }}
                    className="px-4 py-2 bg-green-600 text-white rounded-lg text-xs font-medium hover:bg-green-700" data-testid={`renew-${u.username}`}>Renew</button>
                </div>
              ))}
            </div>
          )}
          {renewals.near_expiry?.length > 0 && (
            <div className="mb-6">
              <h3 className="text-sm font-semibold text-amber-700 mb-3 flex items-center gap-1.5"><Clock size={14} /> Expiring Soon</h3>
              {renewals.near_expiry.map(u => (
                <div key={u.username} className="bg-amber-50 border border-amber-200 rounded-xl p-4 flex items-center justify-between mb-2">
                  <div>
                    <p className="font-medium text-amber-900">{u.name || u.username}</p>
                    <p className="text-xs text-amber-700">{u.username} | {u.plan?.toUpperCase()}</p>
                    <p className="text-xs text-amber-600 mt-1">{u.days_left} days left</p>
                  </div>
                  <button onClick={() => { setProcessModal(u.username); setProcessData({ action: 'approve', plan: u.plan, subscription_months: 12, notes: '' }); }}
                    className="px-4 py-2 bg-green-600 text-white rounded-lg text-xs font-medium hover:bg-green-700">Renew</button>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ===== REFERRALS TAB ===== */}
      {activeTab === 'referrals' && <ReferralManagement token={token} />}

      {/* ===== QUESTIONNAIRES (LEADS) TAB ===== */}
      {activeTab === 'questionnaires' && <QuestionnaireLeads headers={headers} />}

      {/* ===== ACTIVITY TAB ===== */}
      {activeTab === 'activity' && <ActivityLog />}

      {/* ===== BACKUPS TAB ===== */}
      {activeTab === 'backups' && <SuperAdminBackups />}

      {/* ===== MODALS ===== */}

      {/* Record Payment Modal */}
      {showPaymentModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4" onClick={e => e.target === e.currentTarget && setShowPaymentModal(false)}>
          <div className="bg-white rounded-xl w-full max-w-lg p-6" data-testid="payment-modal">
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-lg font-semibold text-slate-900">Record Payment</h3>
              <button onClick={() => setShowPaymentModal(false)}><X size={20} className="text-slate-400" /></button>
            </div>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Customer *</label>
                <select value={paymentForm.customer_username} onChange={e => setPaymentForm(p => ({ ...p, customer_username: e.target.value }))}
                  className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm" data-testid="payment-customer-select">
                  <option value="">Select customer</option>
                  {admins.map(a => <option key={a.username} value={a.username}>{a.name || a.username} ({a.plan})</option>)}
                </select>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">Amount (Rs.) *</label>
                  <input type="number" value={paymentForm.amount} onChange={e => setPaymentForm(p => ({ ...p, amount: e.target.value }))}
                    className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm" placeholder="0" data-testid="payment-amount" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">Payment Mode</label>
                  <select value={paymentForm.payment_mode} onChange={e => setPaymentForm(p => ({ ...p, payment_mode: e.target.value }))}
                    className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm" data-testid="payment-mode">
                    <option value="bank_transfer">Bank Transfer</option>
                    <option value="upi">UPI</option>
                    <option value="cash">Cash</option>
                    <option value="cheque">Cheque</option>
                    <option value="other">Other</option>
                  </select>
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Reference No.</label>
                <input type="text" value={paymentForm.reference_no} onChange={e => setPaymentForm(p => ({ ...p, reference_no: e.target.value }))}
                  className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm" placeholder="UTR / Cheque No." data-testid="payment-reference" />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Period Description</label>
                <input type="text" value={paymentForm.period_description} onChange={e => setPaymentForm(p => ({ ...p, period_description: e.target.value }))}
                  className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm" placeholder="e.g., Annual 2026-27" data-testid="payment-period" />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Notes</label>
                <textarea value={paymentForm.notes} onChange={e => setPaymentForm(p => ({ ...p, notes: e.target.value }))}
                  className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm" rows={2} placeholder="Optional notes" />
              </div>
              <button onClick={recordPayment} className="w-full py-2.5 bg-emerald-600 text-white rounded-lg font-medium hover:bg-emerald-700" data-testid="confirm-payment">
                Record Payment
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Generate Invoice Modal */}
      {showInvoiceModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4" onClick={e => e.target === e.currentTarget && setShowInvoiceModal(false)}>
          <div className="bg-white rounded-xl w-full max-w-lg p-6" data-testid="invoice-modal">
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-lg font-semibold text-slate-900">Generate Invoice</h3>
              <button onClick={() => setShowInvoiceModal(false)}><X size={20} className="text-slate-400" /></button>
            </div>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Customer *</label>
                <select value={invoiceForm.customer_username} onChange={e => {
                  const admin = admins.find(a => a.username === e.target.value);
                  const plan = admin?.plan || 'enterprise'; const cycle = admin?.billing_cycle || 'annual';
                  const pricing = PLANS[plan] || PLANS.enterprise;
                  const amt = cycle === 'annual' ? pricing.annual : pricing.monthly;
                  setInvoiceForm(p => ({ ...p, customer_username: e.target.value, amount: amt.toString(), description: `${pricing.name || 'Enterprise'} Plan - ${cycle === 'annual' ? 'Annual' : 'Monthly'} Subscription` }));
                }}
                  className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm" data-testid="invoice-customer-select">
                  <option value="">Select customer</option>
                  {admins.map(a => <option key={a.username} value={a.username}>{a.name || a.username} ({a.plan})</option>)}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Amount (Rs.) *</label>
                <input type="number" value={invoiceForm.amount} onChange={e => setInvoiceForm(p => ({ ...p, amount: e.target.value }))}
                  className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm" data-testid="invoice-amount" />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Description</label>
                <input type="text" value={invoiceForm.description} onChange={e => setInvoiceForm(p => ({ ...p, description: e.target.value }))}
                  className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm" placeholder="Subscription description" data-testid="invoice-description" />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">Period From</label>
                  <input type="date" value={invoiceForm.period_from} onChange={e => setInvoiceForm(p => ({ ...p, period_from: e.target.value }))}
                    className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm" data-testid="invoice-period-from" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">Period To</label>
                  <input type="date" value={invoiceForm.period_to} onChange={e => setInvoiceForm(p => ({ ...p, period_to: e.target.value }))}
                    className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm" data-testid="invoice-period-to" />
                </div>
              </div>
              <button onClick={generateInvoice} className="w-full py-2.5 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700" data-testid="confirm-invoice">
                Generate Invoice
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Customer Ledger Modal */}
      {ledgerModal && ledgerData && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4" onClick={e => e.target === e.currentTarget && setLedgerModal(null)}>
          <div className="bg-white rounded-xl w-full max-w-2xl p-6 max-h-[90vh] overflow-y-auto" data-testid="ledger-modal">
            <div className="flex items-center justify-between mb-6">
              <div>
                <h3 className="text-lg font-semibold text-slate-900">{ledgerData.customer?.name || ledgerModal} — Ledger</h3>
                <p className="text-xs text-slate-500">{ledgerData.customer?.plan?.toUpperCase()} Plan · {ledgerData.customer?.billing_cycle} · Expires {formatDate(ledgerData.customer?.subscription_expires)}</p>
              </div>
              <button onClick={() => setLedgerModal(null)}><X size={20} className="text-slate-400" /></button>
            </div>
            <div className="grid grid-cols-3 gap-4 mb-6">
              <div className="bg-blue-50 rounded-lg p-3">
                <div className="text-xs text-blue-600">Total Billed</div>
                <div className="text-lg font-bold text-blue-700">{formatINR(ledgerData.total_billed)}</div>
              </div>
              <div className="bg-emerald-50 rounded-lg p-3">
                <div className="text-xs text-emerald-600">Total Paid</div>
                <div className="text-lg font-bold text-emerald-700">{formatINR(ledgerData.total_paid)}</div>
              </div>
              <div className="bg-red-50 rounded-lg p-3">
                <div className="text-xs text-red-600">Balance Due</div>
                <div className="text-lg font-bold text-red-700">{formatINR(ledgerData.balance_due)}</div>
              </div>
            </div>
            <h4 className="text-sm font-semibold text-slate-700 mb-3">Payment History</h4>
            {ledgerData.payments?.length === 0 ? (
              <p className="text-sm text-slate-400 text-center py-4">No payments recorded</p>
            ) : (
              <div className="space-y-2 mb-6">
                {ledgerData.payments?.map((p, i) => (
                  <div key={i} className="flex items-center justify-between p-3 bg-slate-50 rounded-lg">
                    <div>
                      <div className="text-sm font-medium">{formatINR(p.amount)}</div>
                      <div className="text-xs text-slate-400">{p.payment_mode?.replace('_', ' ')} · {p.reference_no || '—'}</div>
                    </div>
                    <div className="text-xs text-slate-500">{formatDate(p.payment_date)}</div>
                  </div>
                ))}
              </div>
            )}
            {ledgerData.invoices?.length > 0 && (
              <>
                <h4 className="text-sm font-semibold text-slate-700 mb-3">Invoices</h4>
                <div className="space-y-2">
                  {ledgerData.invoices.map((inv, i) => (
                    <div key={i} className="flex items-center justify-between p-3 bg-slate-50 rounded-lg">
                      <div>
                        <div className="text-sm font-medium font-mono">{inv.invoice_number}</div>
                        <div className="text-xs text-slate-400">{inv.description?.substring(0, 50)}</div>
                      </div>
                      <div className="flex items-center gap-3">
                        <span className={`text-[10px] px-2 py-0.5 rounded-full font-bold ${inv.status === 'paid' ? 'bg-emerald-50 text-emerald-700' : 'bg-red-50 text-red-700'}`}>{inv.status}</span>
                        <span className="text-sm font-bold">{formatINR(inv.amount)}</span>
                        <button onClick={() => downloadInvoicePDF(inv.invoice_id)} className="p-1 text-slate-400 hover:text-blue-600"><Download size={14} /></button>
                      </div>
                    </div>
                  ))}
                </div>
              </>
            )}
          </div>
        </div>
      )}

      {/* Convert Prospect Modal */}
      {convertModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4" onClick={e => e.target === e.currentTarget && setConvertModal(null)}>
          <div className="bg-white rounded-xl w-full max-w-lg p-6 max-h-[90vh] overflow-y-auto" data-testid="convert-modal">
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-lg font-semibold text-slate-900">Convert Prospect</h3>
              <button onClick={() => setConvertModal(null)}><X size={20} className="text-slate-400" /></button>
            </div>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Password *</label>
                <input type="text" value={convertData.password} onChange={e => setConvertData(p => ({ ...p, password: e.target.value }))}
                  className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm" placeholder="Min 6 characters" data-testid="convert-password" />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">Plan</label>
                <div className="grid grid-cols-3 gap-2">
                  {Object.entries(PLANS).map(([id, plan]) => (
                    <button key={id} onClick={() => setConvertData(p => ({ ...p, plan: id }))}
                      className={`p-3 border rounded-lg text-left ${convertData.plan === id ? 'border-blue-500 bg-blue-50 ring-1 ring-blue-500' : 'border-slate-200'}`} data-testid={`plan-select-${id}`}>
                      <p className="text-sm font-bold">{plan.name}</p>
                      <p className="text-xs text-blue-600">{formatINR(convertData.billing_cycle === 'annual' ? Math.round(plan.annual / 12) : plan.monthly)}/mo</p>
                    </button>
                  ))}
                </div>
              </div>
              <div className="flex gap-2">
                {['monthly', 'annual'].map(c => (
                  <button key={c} onClick={() => setConvertData(p => ({ ...p, billing_cycle: c }))}
                    className={`flex-1 py-2 text-sm font-medium rounded-lg border ${convertData.billing_cycle === c ? 'border-blue-500 bg-blue-50 text-blue-700' : 'border-slate-200'}`}>
                    {c === 'annual' ? 'Annual (Save 17%)' : 'Monthly'}
                  </button>
                ))}
              </div>
              <select value={convertData.subscription_months} onChange={e => setConvertData(p => ({ ...p, subscription_months: parseInt(e.target.value) }))}
                className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm" data-testid="convert-subscription">
                <option value={1}>1 month</option><option value={3}>3 months</option><option value={6}>6 months</option>
                <option value={12}>12 months</option><option value={24}>24 months</option>
              </select>
              <button onClick={convertProspect} className="w-full bg-green-600 text-white py-2.5 rounded-lg font-medium hover:bg-green-700" data-testid="convert-confirm-btn">
                Convert to Admin — {PLANS[convertData.plan]?.name}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Process Renewal Modal */}
      {processModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4" onClick={e => e.target === e.currentTarget && setProcessModal(null)}>
          <div className="bg-white rounded-xl w-full max-w-lg p-6" data-testid="process-renewal-modal">
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-lg font-semibold text-slate-900">Renew: {processModal}</h3>
              <button onClick={() => setProcessModal(null)}><X size={20} className="text-slate-400" /></button>
            </div>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">Plan</label>
                <div className="grid grid-cols-3 gap-2">
                  {Object.entries(PLANS).map(([id, plan]) => (
                    <button key={id} onClick={() => setProcessData(p => ({ ...p, plan: id }))}
                      className={`p-3 border rounded-lg text-left ${processData.plan === id ? 'border-blue-500 bg-blue-50 ring-1 ring-blue-500' : 'border-slate-200'}`}>
                      <p className="text-sm font-bold">{plan.name}</p>
                    </button>
                  ))}
                </div>
              </div>
              <select value={processData.subscription_months} onChange={e => setProcessData(p => ({ ...p, subscription_months: parseInt(e.target.value) }))}
                className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm">
                <option value={1}>1 month</option><option value={3}>3 months</option><option value={6}>6 months</option>
                <option value={12}>12 months</option><option value={24}>24 months</option>
              </select>
              <button onClick={async () => {
                try {
                  const res = await axios.put(`${API}/super-admin/renewals/${processModal}/process`, processData, { headers });
                  if (res.data?.success) { toast.success(res.data.message); setProcessModal(null); fetchData(); }
                  else toast.error(res.data?.error || 'Failed');
                } catch { toast.error('Failed to process'); }
              }} className="w-full py-2.5 bg-green-600 text-white rounded-lg font-medium hover:bg-green-700" data-testid="process-renewal-btn">
                Approve & Renew
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Create Admin Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={e => e.target === e.currentTarget && setShowCreateModal(false)}>
          <div className="bg-white rounded-xl p-6 w-full max-w-lg mx-4 max-h-[90vh] overflow-y-auto" data-testid="create-admin-modal">
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-lg font-semibold text-slate-900">Create Admin</h3>
              <button onClick={() => setShowCreateModal(false)}><X size={20} className="text-slate-400" /></button>
            </div>
            <div className="space-y-4">
              <div><label className="block text-sm font-medium text-slate-700 mb-1">Email *</label><input type="email" value={newAdmin.username} onChange={e => setNewAdmin({ ...newAdmin, username: e.target.value })} className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm" data-testid="new-admin-email" /></div>
              <div><label className="block text-sm font-medium text-slate-700 mb-1">Password *</label><input type="text" value={newAdmin.password} onChange={e => setNewAdmin({ ...newAdmin, password: e.target.value })} className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm" data-testid="new-admin-password" /></div>
              <div><label className="block text-sm font-medium text-slate-700 mb-1">Name</label><input type="text" value={newAdmin.name} onChange={e => setNewAdmin({ ...newAdmin, name: e.target.value })} className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm" data-testid="new-admin-name" /></div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">Plan</label>
                <div className="grid grid-cols-3 gap-2">
                  {Object.entries(PLANS).map(([id, plan]) => (
                    <button key={id} onClick={() => setNewAdmin({ ...newAdmin, plan: id, features: [...plan.features] })}
                      className={`p-3 border rounded-lg text-left ${newAdmin.plan === id ? 'border-blue-500 bg-blue-50 ring-1 ring-blue-500' : 'border-slate-200'}`} data-testid={`new-plan-${id}`}>
                      <p className="text-sm font-bold">{plan.name}</p>
                      <p className="text-xs text-blue-600">{formatINR(newAdmin.billing_cycle === 'annual' ? Math.round(plan.annual / 12) : plan.monthly)}/mo</p>
                      <div className="text-[10px] text-slate-500 mt-1">{plan.maxCompanies} co | {plan.maxEmployees} emp</div>
                    </button>
                  ))}
                </div>
              </div>
              <div className="flex gap-2">
                {['monthly', 'annual'].map(c => (
                  <button key={c} onClick={() => setNewAdmin({ ...newAdmin, billing_cycle: c })}
                    className={`flex-1 py-2 text-sm font-medium rounded-lg border ${newAdmin.billing_cycle === c ? 'border-blue-500 bg-blue-50 text-blue-700' : 'border-slate-200'}`}>
                    {c === 'annual' ? 'Annual (Save 17%)' : 'Monthly'}
                  </button>
                ))}
              </div>
              <select value={newAdmin.subscription_months} onChange={e => setNewAdmin({ ...newAdmin, subscription_months: parseInt(e.target.value) })}
                className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm" data-testid="new-admin-subscription">
                <option value={1}>1 Month</option><option value={3}>3 Months</option><option value={6}>6 Months</option>
                <option value={12}>12 Months</option><option value={24}>24 Months</option><option value={36}>36 Months</option>
              </select>
              {/* Feature Gating Checkboxes */}
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">Features ({newAdmin.features?.length || 0}/{ALL_FEATURES.length})</label>
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-1.5 p-3 bg-slate-50 rounded-lg border border-slate-200 max-h-48 overflow-y-auto">
                  {ALL_FEATURES.map(f => {
                    const checked = newAdmin.features?.includes(f.id);
                    return (
                      <label key={f.id} className={`flex items-center gap-2 px-2 py-1.5 rounded cursor-pointer text-xs transition ${checked ? 'bg-emerald-50 text-emerald-800' : 'hover:bg-white text-slate-600'}`} data-testid={`new-feature-${f.id}`}>
                        <input type="checkbox" checked={checked} onChange={() => {
                          setNewAdmin(prev => ({
                            ...prev,
                            features: checked ? prev.features.filter(x => x !== f.id) : [...(prev.features || []), f.id]
                          }));
                        }} className="w-3.5 h-3.5 rounded border-slate-300 text-emerald-600 focus:ring-emerald-500" />
                        <div>
                          <div className="font-medium leading-tight">{f.label}</div>
                          <div className="text-[9px] text-slate-400 leading-tight">{f.desc}</div>
                        </div>
                      </label>
                    );
                  })}
                </div>
              </div>
              <button onClick={createAdmin} className="w-full py-2.5 bg-[#2563EB] text-white rounded-lg font-medium hover:bg-[#1D4ED8]" data-testid="confirm-create-admin">Create Admin</button>
            </div>
          </div>
        </div>
      )}

      {/* Edit Admin Modal */}
      {showEditModal && editAdmin && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={e => e.target === e.currentTarget && setShowEditModal(null)}>
          <div className="bg-white rounded-xl p-6 w-full max-w-lg mx-4 max-h-[90vh] overflow-y-auto" data-testid="edit-admin-modal">
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-lg font-semibold text-slate-900">Edit Admin</h3>
              <button onClick={() => { setShowEditModal(null); setEditAdmin(null); }}><X size={20} className="text-slate-400" /></button>
            </div>
            <div className="space-y-4">
              <div className="p-3 bg-slate-50 rounded-lg"><div className="text-xs text-slate-500">Email</div><div className="font-medium">{editAdmin.username}</div></div>
              <div><label className="block text-sm font-medium text-slate-700 mb-1">Name</label><input type="text" value={editAdmin.name} onChange={e => setEditAdmin({ ...editAdmin, name: e.target.value })} className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm" data-testid="edit-admin-name" /></div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">Plan</label>
                <div className="grid grid-cols-3 gap-2">
                  {Object.entries(PLANS).map(([id, plan]) => (
                    <button key={id} onClick={() => setEditAdmin(p => ({ ...p, plan: id, features: [...plan.features] }))}
                      className={`p-3 border rounded-lg text-left ${editAdmin.plan === id ? 'border-blue-500 bg-blue-50 ring-1 ring-blue-500' : 'border-slate-200'}`} data-testid={`edit-plan-${id}`}>
                      <p className="text-sm font-bold">{plan.name}</p>
                      <p className="text-xs text-blue-600">{formatINR(editAdmin.billing_cycle === 'annual' ? Math.round(plan.annual / 12) : plan.monthly)}/mo</p>
                    </button>
                  ))}
                </div>
              </div>
              <div className="flex gap-2">
                {['monthly', 'annual'].map(c => (
                  <button key={c} onClick={() => setEditAdmin(p => ({ ...p, billing_cycle: c }))}
                    className={`flex-1 py-2 text-sm font-medium rounded-lg border ${editAdmin.billing_cycle === c ? 'border-blue-500 bg-blue-50 text-blue-700' : 'border-slate-200'}`}>
                    {c === 'annual' ? 'Annual (Save 17%)' : 'Monthly'}
                  </button>
                ))}
              </div>
              <select value={editAdmin.subscription_months} onChange={e => setEditAdmin({ ...editAdmin, subscription_months: parseInt(e.target.value) })}
                className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm" data-testid="edit-admin-subscription">
                <option value={1}>1 Mo</option><option value={3}>3 Mo</option><option value={6}>6 Mo</option>
                <option value={12}>12 Mo</option><option value={24}>24 Mo</option><option value={36}>36 Mo</option>
              </select>
              {/* Feature Gating Checkboxes */}
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">Features ({editAdmin.features?.length || 0}/{ALL_FEATURES.length})</label>
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-1.5 p-3 bg-slate-50 rounded-lg border border-slate-200 max-h-48 overflow-y-auto">
                  {ALL_FEATURES.map(f => {
                    const checked = editAdmin.features?.includes(f.id);
                    return (
                      <label key={f.id} className={`flex items-center gap-2 px-2 py-1.5 rounded cursor-pointer text-xs transition ${checked ? 'bg-emerald-50 text-emerald-800' : 'hover:bg-white text-slate-600'}`} data-testid={`feature-toggle-${f.id}`}>
                        <input type="checkbox" checked={checked} onChange={() => {
                          setEditAdmin(prev => ({
                            ...prev,
                            features: checked ? prev.features.filter(x => x !== f.id) : [...(prev.features || []), f.id]
                          }));
                        }} className="w-3.5 h-3.5 rounded border-slate-300 text-emerald-600 focus:ring-emerald-500" />
                        <div>
                          <div className="font-medium leading-tight">{f.label}</div>
                          <div className="text-[9px] text-slate-400 leading-tight">{f.desc}</div>
                        </div>
                      </label>
                    );
                  })}
                </div>
              </div>
              <div className="flex justify-end gap-3">
                <button onClick={() => { setShowEditModal(null); setEditAdmin(null); }} className="px-4 py-2 text-sm border border-slate-200 rounded-lg">Cancel</button>
                <button onClick={saveEditAdmin} className="px-4 py-2 text-sm bg-[#2563EB] text-white rounded-lg" data-testid="confirm-edit-admin">Save</button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Reset Password Modal */}
      {showResetModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" data-testid="reset-password-modal">
          <div className="bg-white rounded-xl p-6 w-full max-w-sm mx-4">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-slate-900">Reset Password</h3>
              <button onClick={() => { setShowResetModal(null); setResetPassword(''); }}><X size={20} className="text-slate-400" /></button>
            </div>
            <p className="text-sm text-slate-500 mb-4">Reset for <strong>{showResetModal}</strong></p>
            <div className="relative">
              <input type={showPassword ? "text" : "password"} value={resetPassword} onChange={e => setResetPassword(e.target.value)}
                className="w-full px-4 py-2 border border-slate-200 rounded-lg pr-10" placeholder="New password" data-testid="reset-password-input" />
              <button onClick={() => setShowPassword(!showPassword)} className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400">
                {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
            <div className="flex justify-end gap-3 mt-6">
              <button onClick={() => { setShowResetModal(null); setResetPassword(''); }} className="px-4 py-2 text-sm border border-slate-200 rounded-lg">Cancel</button>
              <button onClick={handleResetPassword} className="px-4 py-2 text-sm bg-[#2563EB] text-white rounded-lg" data-testid="confirm-reset-password">Reset</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default SuperAdminDashboard;

/* ─── Referral Management Component ─────────────────── */
const ReferralManagement = () => {
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState(null);
  const [showRedeem, setShowRedeem] = useState(null);
  const [redeemAmount, setRedeemAmount] = useState('');
  const [redeemNotes, setRedeemNotes] = useState('');
  const [showCreditModal, setShowCreditModal] = useState(null);
  const [creditAmount, setCreditAmount] = useState('');
  const [selectedLedger, setSelectedLedger] = useState(null);
  const [ledgerData, setLedgerData] = useState(null);

  useEffect(() => { fetchData(); }, []);

  const fetchData = async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${API}/referrals/admin/overview`);
      if (res.data?.success) setData(res.data.data);
    } catch { toast.error('Failed to load referral data'); }
    finally { setLoading(false); }
  };

  const handleRedeem = async () => {
    if (!showRedeem || !redeemAmount) return;
    try {
      const res = await axios.post(`${API}/referrals/admin/redeem`, {
        username: showRedeem, amount: parseFloat(redeemAmount), notes: redeemNotes
      });
      if (res.data?.success) {
        toast.success(res.data.message);
        setShowRedeem(null); setRedeemAmount(''); setRedeemNotes('');
        fetchData();
      } else toast.error(res.data?.error);
    } catch (e) { toast.error(e.response?.data?.error || 'Failed'); }
  };

  const handleCredit = async () => {
    if (!showCreditModal || !creditAmount) return;
    try {
      const res = await axios.post(`${API}/referrals/admin/credit-commission`, {
        prospect_id: showCreditModal.prospect_id, subscription_amount: parseFloat(creditAmount)
      });
      if (res.data?.success) {
        toast.success(res.data.message);
        setShowCreditModal(null); setCreditAmount('');
        fetchData();
      } else toast.error(res.data?.error);
    } catch (e) { toast.error(e.response?.data?.error || 'Failed'); }
  };

  const viewLedger = async (username) => {
    try {
      const res = await axios.get(`${API}/referrals/admin/user-ledger?username=${encodeURIComponent(username)}`);
      if (res.data?.success) { setLedgerData(res.data.data); setSelectedLedger(username); }
    } catch { toast.error('Failed to load ledger'); }
  };

  if (loading) return <div className="flex items-center justify-center h-40"><div className="loading-spinner" /></div>;

  const stats = data?.stats || {};
  const referrers = data?.referrers || [];
  const recent = data?.recent_referrals || [];

  return (
    <div data-testid="referral-management">
      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-6 gap-3 mb-6">
        {[
          { label: 'Referral Codes', value: stats.total_referral_codes, color: 'text-slate-900' },
          { label: 'Total Referrals', value: stats.total_referrals, color: 'text-blue-700' },
          { label: 'Subscribed', value: stats.total_subscribed, color: 'text-green-700' },
          { label: 'Total Commission', value: formatINR(stats.total_commission), color: 'text-emerald-700' },
          { label: 'Redeemed', value: formatINR(stats.total_redeemed), color: 'text-purple-700' },
          { label: 'Pending Payout', value: formatINR(stats.total_pending_payout), color: 'text-amber-700' },
        ].map(s => (
          <div key={s.label} className="bg-white border border-slate-200 rounded-xl p-3 text-center">
            <div className="text-xs text-slate-500 mb-1">{s.label}</div>
            <div className={`text-lg font-bold ${s.color}`}>{s.value}</div>
          </div>
        ))}
      </div>

      {/* Referrers Table */}
      <h3 className="text-sm font-semibold text-slate-700 mb-3">Referrers</h3>
      <div className="bg-white border border-slate-200 rounded-xl overflow-x-auto mb-6">
        <table className="data-table min-w-[700px]" data-testid="referrers-table">
          <thead><tr>
            <th>User</th><th>Role</th><th className="numeric">Referrals</th>
            <th className="numeric">Subscribed</th><th className="numeric">Earned</th>
            <th className="numeric">Redeemed</th><th className="numeric">Balance</th><th>Actions</th>
          </tr></thead>
          <tbody>
            {referrers.length > 0 ? referrers.map((r, i) => {
              const balance = (r.total_earned || 0) - (r.total_redeemed || 0);
              return (
                <tr key={i}>
                  <td className="font-medium text-slate-900">{r.name || r.username}<div className="text-xs text-slate-400">{r.username}</div></td>
                  <td><span className={`px-2 py-0.5 rounded text-xs font-medium ${r.role === 'admin' ? 'bg-blue-100 text-blue-700' : 'bg-slate-100 text-slate-600'}`}>{r.role}</span></td>
                  <td className="numeric">{r.total_referrals}</td>
                  <td className="numeric text-green-700">{r.subscribed}</td>
                  <td className="numeric font-medium text-emerald-700">{formatINR(r.total_earned)}</td>
                  <td className="numeric text-purple-600">{formatINR(r.total_redeemed)}</td>
                  <td className="numeric font-bold text-amber-700">{formatINR(balance)}</td>
                  <td>
                    <div className="flex gap-1">
                      <button onClick={() => viewLedger(r.username)} className="px-2 py-1 text-xs bg-slate-100 rounded hover:bg-slate-200">Ledger</button>
                      {balance > 0 && <button onClick={() => setShowRedeem(r.username)} className="px-2 py-1 text-xs bg-green-100 text-green-700 rounded hover:bg-green-200" data-testid={`redeem-${i}`}>Redeem</button>}
                    </div>
                  </td>
                </tr>
              );
            }) : <tr><td colSpan="8" className="text-center py-8 text-slate-400">No referrers yet</td></tr>}
          </tbody>
        </table>
      </div>

      {/* Recent Referrals */}
      <h3 className="text-sm font-semibold text-slate-700 mb-3">Recent Referrals</h3>
      <div className="bg-white border border-slate-200 rounded-xl overflow-x-auto">
        <table className="data-table min-w-[700px]" data-testid="recent-referrals-table">
          <thead><tr>
            <th>Referred Company</th><th>Referrer</th><th>Code</th><th>Date</th>
            <th>Status</th><th className="numeric">Commission</th><th>Actions</th>
          </tr></thead>
          <tbody>
            {recent.length > 0 ? recent.map((r, i) => (
              <tr key={i}>
                <td className="font-medium">{r.referred_company}</td>
                <td className="text-slate-600 text-sm">{r.referrer_name || r.referrer_username}</td>
                <td className="font-mono text-xs text-slate-500">{r.referral_code}</td>
                <td className="text-slate-600">{formatDate(r.created_at)}</td>
                <td><span className={`px-2 py-0.5 rounded-full text-xs font-medium ${r.status === 'subscribed' ? 'bg-green-100 text-green-700' : 'bg-amber-100 text-amber-700'}`}>{r.status}</span></td>
                <td className="numeric">{r.commission_amount > 0 ? formatINR(r.commission_amount) : '-'}</td>
                <td>{r.status === 'pending' && <button onClick={() => setShowCreditModal(r)} className="px-2 py-1 text-xs bg-blue-100 text-blue-700 rounded hover:bg-blue-200" data-testid={`credit-${i}`}>Credit Commission</button>}</td>
              </tr>
            )) : <tr><td colSpan="7" className="text-center py-8 text-slate-400">No referrals yet</td></tr>}
          </tbody>
        </table>
      </div>

      {/* Redeem Modal */}
      {showRedeem && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4" onClick={e => e.target === e.currentTarget && setShowRedeem(null)}>
          <div className="bg-white rounded-xl max-w-md w-full p-6" data-testid="redeem-modal">
            <h3 className="text-lg font-semibold mb-4">Process Payout: {showRedeem}</h3>
            <div className="space-y-3">
              <div>
                <label className="text-sm font-medium text-slate-700">Amount (Rs.)</label>
                <input type="number" value={redeemAmount} onChange={e => setRedeemAmount(e.target.value)} className="w-full mt-1 px-3 py-2 border border-slate-200 rounded-lg" placeholder="Enter amount" data-testid="redeem-amount" />
              </div>
              <div>
                <label className="text-sm font-medium text-slate-700">Notes</label>
                <input type="text" value={redeemNotes} onChange={e => setRedeemNotes(e.target.value)} className="w-full mt-1 px-3 py-2 border border-slate-200 rounded-lg" placeholder="Payment reference, mode, etc." />
              </div>
            </div>
            <div className="flex gap-3 mt-6">
              <button onClick={handleRedeem} className="flex-1 py-2.5 bg-green-600 text-white rounded-lg font-medium hover:bg-green-700" data-testid="confirm-redeem">Process Payout</button>
              <button onClick={() => setShowRedeem(null)} className="flex-1 py-2.5 border border-slate-200 rounded-lg">Cancel</button>
            </div>
          </div>
        </div>
      )}

      {/* Credit Commission Modal */}
      {showCreditModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4" onClick={e => e.target === e.currentTarget && setShowCreditModal(null)}>
          <div className="bg-white rounded-xl max-w-md w-full p-6" data-testid="credit-modal">
            <h3 className="text-lg font-semibold mb-2">Credit Commission</h3>
            <p className="text-sm text-slate-500 mb-4">Company: <strong>{showCreditModal.referred_company}</strong> | Referrer: <strong>{showCreditModal.referrer_name}</strong></p>
            <div>
              <label className="text-sm font-medium text-slate-700">Subscription Amount (Rs.)</label>
              <input type="number" value={creditAmount} onChange={e => setCreditAmount(e.target.value)} className="w-full mt-1 px-3 py-2 border border-slate-200 rounded-lg" placeholder="Final subscription amount" data-testid="credit-amount" />
              {creditAmount > 0 && <p className="text-sm text-green-600 mt-1">Commission (3%): <strong>Rs.{(parseFloat(creditAmount) * 0.03).toFixed(2)}</strong></p>}
            </div>
            <div className="flex gap-3 mt-6">
              <button onClick={handleCredit} className="flex-1 py-2.5 bg-[#2563EB] text-white rounded-lg font-medium hover:bg-[#1D4ED8]" data-testid="confirm-credit">Credit Commission</button>
              <button onClick={() => setShowCreditModal(null)} className="flex-1 py-2.5 border border-slate-200 rounded-lg">Cancel</button>
            </div>
          </div>
        </div>
      )}

      {/* User Ledger Modal */}
      {selectedLedger && ledgerData && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4" onClick={e => e.target === e.currentTarget && setSelectedLedger(null)}>
          <div className="bg-white rounded-xl max-w-2xl w-full max-h-[80vh] overflow-y-auto p-6" data-testid="ledger-modal">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold">Ledger: {selectedLedger}</h3>
              <button onClick={() => setSelectedLedger(null)} className="text-slate-400 hover:text-slate-600"><X size={20} /></button>
            </div>
            <table className="data-table w-full">
              <thead><tr><th>Date</th><th>Type</th><th>Description</th><th className="numeric">Amount</th><th className="numeric">Balance</th></tr></thead>
              <tbody>
                {(ledgerData.ledger || []).map((e, i) => (
                  <tr key={i}>
                    <td className="text-sm">{formatDate(e.created_at)}</td>
                    <td><span className={`px-2 py-0.5 rounded text-xs font-medium ${e.type === 'credit' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>{e.type}</span></td>
                    <td className="text-sm text-slate-600">{e.description}</td>
                    <td className={`numeric font-medium ${e.type === 'credit' ? 'text-green-700' : 'text-red-600'}`}>{e.type === 'credit' ? '+' : '-'}{formatINR(e.amount)}</td>
                    <td className="numeric font-semibold">{formatINR(e.balance_after)}</td>
                  </tr>
                ))}
                {(ledgerData.ledger || []).length === 0 && <tr><td colSpan="5" className="text-center py-6 text-slate-400">No ledger entries</td></tr>}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};


/* ─── Questionnaire Leads Component ─────────────────── */
const QuestionnaireLeads = ({ headers }) => {
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState([]);
  const [total, setTotal] = useState(0);
  const [expandedIdx, setExpandedIdx] = useState(null);

  useEffect(() => { fetchLeads(); }, []);

  const fetchLeads = async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${API}/super-admin/questionnaires`, { headers });
      if (res.data?.success) {
        setData(res.data.data.questionnaires || []);
        setTotal(res.data.data.total || 0);
      }
    } catch { toast.error('Failed to fetch questionnaires'); }
    finally { setLoading(false); }
  };

  const exportExcel = async () => {
    try {
      const res = await axios.get(`${API}/super-admin/questionnaires/export`, { headers, responseType: 'blob' });
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', 'FLOWRA_Questionnaires.xlsx');
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      toast.success('Excel downloaded!');
    } catch { toast.error('Failed to export'); }
  };

  const updateStatus = async (idx, status) => {
    try {
      await axios.put(`${API}/super-admin/questionnaires/${idx}/status`, { status }, { headers });
      toast.success('Status updated');
      fetchLeads();
    } catch { toast.error('Failed to update status'); }
  };

  const statusColor = (s) => {
    if (s === 'new') return 'bg-blue-100 text-blue-700';
    if (s === 'contacted') return 'bg-amber-100 text-amber-700';
    if (s === 'qualified') return 'bg-green-100 text-green-700';
    if (s === 'closed') return 'bg-slate-100 text-slate-500';
    return 'bg-slate-100 text-slate-600';
  };

  if (loading) return <div className="flex items-center justify-center h-40"><RefreshCw size={20} className="animate-spin text-slate-400" /></div>;

  return (
    <div data-testid="questionnaires-tab">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-lg font-bold text-slate-900">Questionnaire Leads</h2>
          <p className="text-sm text-slate-500">{total} submission{total !== 1 ? 's' : ''} collected</p>
        </div>
        <div className="flex gap-2">
          <button onClick={fetchLeads} className="px-3 py-2 text-sm border border-slate-200 rounded-lg hover:bg-slate-50 flex items-center gap-1.5">
            <RefreshCw size={14} /> Refresh
          </button>
          <button onClick={exportExcel} className="px-4 py-2 text-sm bg-green-600 text-white rounded-lg hover:bg-green-700 flex items-center gap-1.5" data-testid="export-questionnaires-btn">
            <Download size={14} /> Export Excel
          </button>
        </div>
      </div>

      {data.length === 0 ? (
        <div className="bg-white border border-slate-200 rounded-xl p-10 text-center">
          <FileText size={32} className="text-slate-300 mx-auto mb-3" />
          <p className="text-slate-500 text-sm">No questionnaire submissions yet.</p>
          <p className="text-slate-400 text-xs mt-1">Share the Needs Assessment form link with prospects.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {data.map((q, idx) => (
            <div key={idx} className="bg-white border border-slate-200 rounded-xl overflow-hidden" data-testid={`lead-${idx}`}>
              <div className="flex items-center justify-between px-4 py-3 cursor-pointer hover:bg-slate-50" onClick={() => setExpandedIdx(expandedIdx === idx ? null : idx)}>
                <div className="flex items-center gap-3 min-w-0">
                  <div className="w-9 h-9 bg-blue-50 rounded-lg flex items-center justify-center shrink-0">
                    <Building2 size={16} className="text-[#2563EB]" />
                  </div>
                  <div className="min-w-0">
                    <div className="text-sm font-medium text-slate-900 truncate">{q.company_name || q.contact_person || 'Unnamed'}</div>
                    <div className="text-xs text-slate-500 truncate">{q.phone || q.email || '—'} {q.city ? `| ${q.city}` : ''}</div>
                  </div>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold ${statusColor(q.status)}`}>{q.status}</span>
                  <span className="text-[10px] text-slate-400 hidden sm:inline">{q.submitted_at ? new Date(q.submitted_at).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' }) : ''}</span>
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-100 text-slate-500">{q.submitted_by === 'employee' ? 'Rep' : 'Self'}</span>
                  {expandedIdx === idx ? <ChevronUp size={14} className="text-slate-400" /> : <ChevronDown size={14} className="text-slate-400" />}
                </div>
              </div>

              {expandedIdx === idx && (
                <div className="px-4 pb-4 border-t border-slate-100 pt-3">
                  <div className="grid sm:grid-cols-3 gap-3 text-xs mb-3">
                    <div><span className="text-slate-500">Contact:</span> <span className="text-slate-900 font-medium">{q.contact_person || '—'}</span></div>
                    <div><span className="text-slate-500">Designation:</span> <span className="text-slate-900">{q.designation || '—'}</span></div>
                    <div><span className="text-slate-500">Industry:</span> <span className="text-slate-900">{q.industry || '—'}</span></div>
                    <div><span className="text-slate-500">Employees:</span> <span className="text-slate-900">{q.employees || '—'}</span></div>
                    <div><span className="text-slate-500">Turnover:</span> <span className="text-slate-900">{q.turnover || '—'}</span></div>
                    <div><span className="text-slate-500">Tally Version:</span> <span className="text-slate-900">{q.tally_version || '—'}</span></div>
                    <div><span className="text-slate-500">Companies:</span> <span className="text-slate-900">{q.tally_companies || '—'}</span></div>
                    <div><span className="text-slate-500">Branches:</span> <span className="text-slate-900">{q.has_branches === 'yes' ? `Yes (${q.branch_count || '?'})` : q.has_branches || '—'}</span></div>
                    <div><span className="text-slate-500">Budget:</span> <span className="text-slate-900">{q.budget || '—'}</span></div>
                    <div><span className="text-slate-500">Timeline:</span> <span className="text-slate-900">{q.timeline || '—'}</span></div>
                    <div><span className="text-slate-500">Decision Maker:</span> <span className="text-slate-900">{q.decision_maker || '—'}</span></div>
                    <div><span className="text-slate-500">Heard From:</span> <span className="text-slate-900">{q.heard_from || '—'}</span></div>
                  </div>
                  {(q.pain_points || []).length > 0 && (
                    <div className="mb-2">
                      <span className="text-[10px] font-semibold text-slate-500 uppercase tracking-wide">Pain Points:</span>
                      <div className="flex flex-wrap gap-1 mt-1">
                        {q.pain_points.map((p, i) => <span key={i} className="px-2 py-0.5 bg-red-50 text-red-700 rounded text-[10px]">{p.slice(0, 50)}</span>)}
                      </div>
                    </div>
                  )}
                  {q.biggest_challenge && <p className="text-xs text-slate-600 mb-2"><span className="font-semibold text-slate-500">Challenge:</span> {q.biggest_challenge}</p>}
                  {(q.next_steps || []).length > 0 && (
                    <div className="mb-3">
                      <span className="text-[10px] font-semibold text-slate-500 uppercase tracking-wide">Requested:</span>
                      <div className="flex flex-wrap gap-1 mt-1">
                        {q.next_steps.map((n, i) => <span key={i} className="px-2 py-0.5 bg-blue-50 text-blue-700 rounded text-[10px]">{n}</span>)}
                      </div>
                    </div>
                  )}
                  {q.callback_time && <p className="text-xs text-slate-600 mb-2"><span className="font-semibold text-slate-500">Callback:</span> {q.callback_time}</p>}
                  {q.notes && <p className="text-xs text-slate-600 mb-3"><span className="font-semibold text-slate-500">Notes:</span> {q.notes}</p>}
                  <div className="flex gap-2">
                    {['new', 'contacted', 'qualified', 'closed'].map(s => (
                      <button key={s} onClick={() => updateStatus(idx, s)}
                        className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors ${q.status === s ? 'border-[#2563EB] bg-blue-50 text-[#2563EB]' : 'border-slate-200 text-slate-500 hover:bg-slate-50'}`}>
                        {s.charAt(0).toUpperCase() + s.slice(1)}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
