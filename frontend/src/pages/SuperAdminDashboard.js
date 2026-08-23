import React, { useState, useEffect, useCallback, useMemo } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import {
  Users, Shield, RefreshCw, Activity,
  Eye, EyeOff, X, UserPlus,
  FileText, AlertTriangle,
  IndianRupee, TrendingUp, CreditCard, Receipt, Heart,
  BarChart3, Wallet, Calendar, Gift, Database,
  Sparkles, Copy, Download, Building2, ChevronUp, ChevronDown,
} from 'lucide-react';
import ActivityLog from './ActivityLog';
import SuperAdminBackups from './SuperAdminBackups';
import {
  ALL_FEATURES, PLANS, STAFF_FEATURES_LIST,
  formatINR, formatDate, generateStrongPassword,
} from './super-admin/utils';
import { OverviewTab } from './super-admin/tabs/OverviewTab';
import { SubscriptionsTab } from './super-admin/tabs/SubscriptionsTab';
import { PaymentsTab } from './super-admin/tabs/PaymentsTab';
import { InvoicesTab } from './super-admin/tabs/InvoicesTab';
import { ProspectsTab } from './super-admin/tabs/ProspectsTab';
import { HealthTab } from './super-admin/tabs/HealthTab';
import { AdminsTab } from './super-admin/tabs/AdminsTab';
import { RenewalsTab } from './super-admin/tabs/RenewalsTab';
import { StaffTab } from './super-admin/tabs/StaffTab';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

const SuperAdminDashboard = ({ token, user }) => {
  // FLOWRA staff get the same UI but tabs are filtered to their feature
  // checklist. Pure super_admin sees everything plus the Staff Mgmt tab.
  const isSuperAdmin = user?.role === 'super_admin';
  const staffFeatures = useMemo(() => new Set(user?.staff_features || []), [user?.staff_features]);
  const allowedTab = (id) => isSuperAdmin || staffFeatures.has(id);
  const [activeTab, setActiveTab] = useState(() => isSuperAdmin ? 'overview'
    : ((user?.staff_features || [])[0] || 'overview'));
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
  const [staffList, setStaffList] = useState([]);
  const [staffEditing, setStaffEditing] = useState(null);
  const [resetStaffPwd, setResetStaffPwd] = useState(null);

  // Modals
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showResetModal, setShowResetModal] = useState(null);
  const [showEditModal, setShowEditModal] = useState(null);
  const [expandedAdmin, setExpandedAdmin] = useState(null);
  const [newAdmin, setNewAdmin] = useState({
    username: '', password: '', name: '',
    plan: 'starter', billing_cycle: 'annual', subscription_months: 12,
    features: PLANS.starter.features,
    mobile: '', address: '', city: '',
    company_name: '', gst: '', industry: '',
    sales_count: 1, dispatch_count: 0,
  });
  const [editAdmin, setEditAdmin] = useState(null);
  const [resetPassword, setResetPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [convertModal, setConvertModal] = useState(null);
  const [convertData, setConvertData] = useState({ password: '', plan: 'professional', billing_cycle: 'annual', subscription_months: 12 });
  const [processModal, setProcessModal] = useState(null);
  const [processData, setProcessData] = useState({ action: 'approve', plan: '', subscription_months: 12, notes: '' });

  // Payment modal — searchable customer picker + auto-filled due amount
  const [showPaymentModal, setShowPaymentModal] = useState(false);
  const [paymentForm, setPaymentForm] = useState({
    customer_username: '', amount: '', payment_mode: 'bank_transfer',
    reference_no: '', notes: '', period_description: '',
  });
  const [paymentCustomer, setPaymentCustomer] = useState(null);       // {plan, balance_due, base_price, ...}
  const [customerSearchTerm, setCustomerSearchTerm] = useState('');
  const [customerSuggestions, setCustomerSuggestions] = useState([]);

  // Invoice modal — searchable + fixed plan amount + discount (0-20 %)
  const [showInvoiceModal, setShowInvoiceModal] = useState(false);
  const [invoiceForm, setInvoiceForm] = useState({
    customer_username: '', description: '', period_from: '', period_to: '',
    discount_pct: 0,
  });
  const [invoiceCustomer, setInvoiceCustomer] = useState(null);
  const [invoiceSearchTerm, setInvoiceSearchTerm] = useState('');
  const [invoiceSuggestions, setInvoiceSuggestions] = useState([]);

  // Industry dropdown data (loaded once on mount)
  const [industries, setIndustries] = useState([]);

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

  // Load the curated Indian industry list once (Phase B — SuperAdmin
  // new-customer form dropdown).
  useEffect(() => {
    if (!isSuperAdmin) return;
    axios.get(`${API}/super-admin/industries`, { headers })
      .then((r) => setIndustries(r.data?.data?.industries || []))
      .catch(() => setIndustries([]));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isSuperAdmin, token]);

  // --- CRUD functions (kept from original) ---
  const createAdmin = async () => {
    if (!newAdmin.username || !newAdmin.password) { toast.error('Email and password are required'); return; }
    if (!newAdmin.name?.trim()) { toast.error('Customer full name is required'); return; }
    if (!newAdmin.mobile?.trim()) { toast.error('Mobile / WhatsApp is required'); return; }
    if (!newAdmin.city?.trim()) { toast.error('City is required'); return; }
    if (!newAdmin.company_name?.trim()) { toast.error('Company name is required'); return; }
    if (!newAdmin.industry?.trim()) { toast.error('Please pick an industry'); return; }
    try {
      const plan = PLANS[newAdmin.plan];
      const res = await axios.post(`${API}/super-admin/admins`, {
        ...newAdmin,
        features: newAdmin.features,
        max_companies: plan.maxCompanies,
        max_employees: plan.maxEmployees,
        sales_count: parseInt(newAdmin.sales_count) || 0,
        dispatch_count: parseInt(newAdmin.dispatch_count) || 0,
      }, { headers });
      if (res.data?.success) {
        const d = res.data.data || {};
        toast.success(d.email_sent
          ? `${res.data.message} · welcome email sent`
          : `${res.data.message} · welcome email NOT sent (check RESEND_API_KEY)`);
        setShowCreateModal(false);
        setNewAdmin({
          username: '', password: '', name: '',
          plan: 'starter', billing_cycle: 'annual', subscription_months: 12,
          features: PLANS.starter.features,
          mobile: '', address: '', city: '',
          company_name: '', gst: '', industry: '',
          sales_count: 1, dispatch_count: 0,
        });
        fetchData();
      } else toast.error(res.data?.error || 'Failed');
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
      if (res.data?.success) {
        const bd = res.data.data?.billing_delta;
        toast.success(res.data.message);
        setShowEditModal(null); setEditAdmin(null); fetchData();
        // If the plan change created a billing delta, prompt the SuperAdmin
        // to record the difference on the Payments tab (or refund).
        if (bd && bd.direction !== 'none' && bd.amount > 0) {
          const goRecord = window.confirm(
            `${bd.narrative}\n\nOld total: ₹${(bd.old_total||0).toLocaleString('en-IN')}\n` +
            `Refund credit (unused): ₹${(bd.refund_credit||0).toLocaleString('en-IN')}\n` +
            `New total: ₹${(bd.new_total||0).toLocaleString('en-IN')}\n\n` +
            `Net ${bd.direction.toUpperCase()}: ₹${bd.amount.toLocaleString('en-IN')}\n\n` +
            `Click OK to jump to Record Payment now, or Cancel to skip.`
          );
          if (goRecord) {
            setActiveTab('payments');
            setPaymentForm(f => ({ ...f, customer_username: editAdmin.username, amount: String(bd.amount), notes: bd.narrative, period_description: `Adjustment for plan change (${bd.direction})` }));
            // Refresh preview for the picker
            try {
              const c = await axios.get(`${API}/super-admin/customers/search`, { headers, params: { q: editAdmin.username } });
              const match = (c.data?.data?.customers || []).find(x => x.username === editAdmin.username);
              if (match) { setPaymentCustomer(match); setCustomerSearchTerm(`${match.name || match.company_name || match.username} (${match.username})`); }
            } catch { /* non-fatal */ }
            setShowPaymentModal(true);
          }
        }
      } else toast.error(res.data?.error || 'Failed to save changes');
    } catch (err) { toast.error(err.response?.data?.error || 'Failed to save changes'); }
  };

  const updateProspectStatus = async (prospectId, status) => {
    // Optimistic update — snap the dropdown to the new value immediately
    // so the SuperAdmin sees the change reflected even before the API
    // round-trip completes.
    setProspects((prev) => prev.map((p) => p.prospect_id === prospectId ? { ...p, status } : p));
    try {
      const res = await axios.put(`${API}/super-admin/prospects/${prospectId}/status`, { status }, { headers });
      if (res.data?.success) {
        toast.success('Status updated');
        fetchData();
      } else {
        toast.error(res.data?.error || 'Failed to update status');
        fetchData();     // reconcile from server
      }
    } catch (err) {
      toast.error(err.response?.data?.error || 'Failed to update status');
      fetchData();
    }
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

  // --- Customer picker helpers used by Record Payment + Generate Invoice
  const searchCustomers = async (term, setter) => {
    try {
      const res = await axios.get(`${API}/super-admin/customers/search`, {
        headers, params: { q: term || '', limit: 20 },
      });
      setter(res.data?.data?.customers || []);
    } catch {
      setter([]);
    }
  };

  const selectPaymentCustomer = (c) => {
    setPaymentCustomer(c);
    setPaymentForm(f => ({ ...f, customer_username: c.username, amount: String(c.balance_due || '') }));
    setCustomerSearchTerm(`${c.name || c.company_name || c.username} (${c.username})`);
    setCustomerSuggestions([]);
  };

  const selectInvoiceCustomer = (c) => {
    setInvoiceCustomer(c);
    setInvoiceForm(f => ({ ...f, customer_username: c.username }));
    setInvoiceSearchTerm(`${c.name || c.company_name || c.username} (${c.username})`);
    setInvoiceSuggestions([]);
  };

  // --- NEW: Payment & Invoice functions ---
  const recordPayment = async () => {
    if (!paymentForm.customer_username || !paymentForm.amount || parseFloat(paymentForm.amount) <= 0) {
      toast.error('Pick a customer and enter a valid amount'); return;
    }
    try {
      const res = await axios.post(`${API}/super-admin/payments`, { ...paymentForm, amount: parseFloat(paymentForm.amount) }, { headers });
      if (res.data?.success) {
        toast.success(res.data.message);
        setShowPaymentModal(false);
        setPaymentForm({ customer_username: '', amount: '', payment_mode: 'bank_transfer', reference_no: '', notes: '', period_description: '' });
        setPaymentCustomer(null); setCustomerSearchTerm(''); setCustomerSuggestions([]);
        fetchData();
      } else toast.error(res.data?.error || 'Failed');
    } catch { toast.error('Failed to record payment'); }
  };

  const generateInvoice = async () => {
    if (!invoiceForm.customer_username) { toast.error('Please pick a customer'); return; }
    const disc = Math.max(0, Math.min(20, parseFloat(invoiceForm.discount_pct) || 0));
    try {
      const res = await axios.post(`${API}/super-admin/invoices/generate`, {
        customer_username: invoiceForm.customer_username,
        description: invoiceForm.description,
        period_from: invoiceForm.period_from,
        period_to: invoiceForm.period_to,
        discount_pct: disc,
      }, { headers });
      if (res.data?.success) {
        const d = res.data.data || {};
        toast.success(`${res.data.message} · Final ₹${(d.final_amount || 0).toLocaleString('en-IN')}`);
        setShowInvoiceModal(false);
        setInvoiceForm({ customer_username: '', description: '', period_from: '', period_to: '', discount_pct: 0 });
        setInvoiceCustomer(null); setInvoiceSearchTerm(''); setInvoiceSuggestions([]);
        fetchData();
      } else toast.error(res.data?.error || 'Failed');
    } catch { toast.error('Failed to generate invoice'); }
  };

  const downloadInvoicePDF = async (invoiceId, invoiceNumber) => {
    try {
      const res = await axios.get(`${API}/super-admin/invoices/${invoiceId}/pdf`, { headers, responseType: 'blob' });
      const url = window.URL.createObjectURL(new Blob([res.data], { type: 'application/pdf' }));
      const link = document.createElement('a');
      link.href = url;
      // File name = invoice number (SuperAdmin spec — avoids the ugly
      // "anonymous.pdf" that browsers used to show).
      link.setAttribute('download', `${invoiceNumber || invoiceId}.pdf`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch { toast.error('Failed to download PDF'); }
  };

  const markInvoiceStatus = async (invoiceId, status) => {
    const inv = (invoices || []).find(i => i.invoice_id === invoiceId);
    const invNo = inv?.invoice_number || invoiceId;
    const amt = inv?.amount || 0;
    let payload = { status };

    if (status === 'paid') {
      const ok = window.confirm(
        `Mark invoice ${invNo} (₹${amt.toLocaleString('en-IN')}) as PAID?\n\n` +
        `This will create a payment record for the customer.\n\nClick OK to continue and enter payment details.`);
      if (!ok) return;
      const mode = window.prompt('Payment mode? (bank_transfer / upi / cash / cheque / razorpay)', 'bank_transfer');
      if (!mode) return;
      const ref = window.prompt('Reference no. (UTR / Cheque / etc.)?', '') || '';
      const notes = window.prompt('Notes (optional)', `Payment for invoice ${invNo}`) || '';
      payload.create_payment = { amount: amt, payment_mode: mode, reference_no: ref, notes,
                                 period_description: inv?.description || '' };
    } else if (status === 'unpaid') {
      const reason = window.prompt(
        `Flip invoice ${invNo} back to UNPAID.\n\nReason for the change (required — audit trail):`, '');
      if (!reason?.trim()) { toast.error('Reason required to flip an invoice back to unpaid'); return; }
      payload.reason = reason.trim();
    } else if (status === 'cancelled') {
      if (!window.confirm(`Cancel invoice ${invNo}?`)) return;
    }

    try {
      const r = await axios.put(`${API}/super-admin/invoices/${invoiceId}/status`, payload, { headers });
      if (r.data?.success) { toast.success(r.data.message); fetchData(); }
      else toast.error(r.data?.error || 'Failed to update');
    } catch (e) { toast.error(e.response?.data?.error || 'Failed to update'); }
  };

  const openLedger = async (username) => {
    try {
      const res = await axios.get(`${API}/super-admin/customer-ledger/${username}`, { headers });
      if (res.data?.success) { setLedgerData(res.data.data); setLedgerModal(username); }
    } catch { toast.error('Failed to load ledger'); }
  };

  // ── FLOWRA Staff (control-panel employees) CRUD ──────────────────────
  const fetchStaff = useCallback(async () => {
    if (!isSuperAdmin) return;
    try {
      const res = await axios.get(`${API}/super-admin/staff`, { headers });
      if (res.data?.success) setStaffList(res.data.data?.staff || []);
    } catch { /* non-fatal — table just stays empty */ }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, isSuperAdmin]);

  useEffect(() => { fetchStaff(); }, [fetchStaff]);

  const submitStaffForm = async () => {
    if (!staffEditing) return;
    const { username, name, password, features, _isNew } = staffEditing;
    if (!name?.trim()) { toast.error('Name is required'); return; }
    if (_isNew) {
      if (!username || !username.includes('@')) { toast.error('Valid email is required'); return; }
      if (!password || password.length < 6) { toast.error('Password must be at least 6 characters'); return; }
    }
    try {
      if (_isNew) {
        const res = await axios.post(`${API}/super-admin/staff`, {
          username: username.trim().toLowerCase(), name: name.trim(), password, features: features || [],
        }, { headers });
        if (res.data?.success) { toast.success('Staff account created'); setStaffEditing(null); fetchStaff(); }
        else toast.error(res.data?.error || 'Failed');
      } else {
        const res = await axios.put(`${API}/super-admin/staff/${username}/features`, {
          features: features || [],
        }, { headers });
        if (res.data?.success) { toast.success('Features updated'); setStaffEditing(null); fetchStaff(); }
        else toast.error(res.data?.error || 'Failed');
      }
    } catch (err) { toast.error(err.response?.data?.error || 'Failed'); }
  };

  const toggleStaffActive = async (username) => {
    try {
      const res = await axios.put(`${API}/super-admin/staff/${username}/toggle-active`, {}, { headers });
      if (res.data?.success) { toast.success('Status updated'); fetchStaff(); }
    } catch { toast.error('Failed'); }
  };

  const deleteStaff = async (username) => {
    if (!window.confirm(`Permanently delete staff account '${username}'?`)) return;
    try {
      const res = await axios.delete(`${API}/super-admin/staff/${username}`, { headers });
      if (res.data?.success) { toast.success('Staff deleted'); fetchStaff(); }
    } catch { toast.error('Failed'); }
  };

  const submitResetStaffPwd = async () => {
    if (!resetStaffPwd) return;
    const { username, password } = resetStaffPwd;
    if (!password || password.length < 6) { toast.error('Password must be at least 6 characters'); return; }
    try {
      const res = await axios.post(`${API}/super-admin/staff/${username}/reset-password`, { password }, { headers });
      if (res.data?.success) { toast.success('Password reset'); setResetStaffPwd(null); }
      else toast.error(res.data?.error || 'Failed');
    } catch { toast.error('Failed'); }
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
    // Staff Mgmt — only the SuperAdmin sees this tab (control-panel users
    // cannot create more control-panel users).
    ...(isSuperAdmin ? [{ id: 'staff', label: 'Staff', icon: Users }] : []),
  ].filter(t => t.id === 'staff' ? isSuperAdmin : allowedTab(t.id));

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

      {/* ===== TAB CONTENT (extracted to /pages/super-admin/tabs/) ===== */}
      {activeTab === 'overview' && businessData && (
        <OverviewTab
          businessData={businessData}
          onRecordPayment={() => setShowPaymentModal(true)}
          onGenerateInvoice={() => setShowInvoiceModal(true)}
          onNewAdmin={() => setShowCreateModal(true)}
        />
      )}

      {activeTab === 'subscriptions' && (
        <SubscriptionsTab admins={admins} onOpenLedger={openLedger} onEditAdmin={openEditAdmin}
          token={token}
          onConvertTrial={(admin) => {
            const plan = window.prompt(`Convert '${admin.username}' to which paid plan? (starter / professional / enterprise)`, 'enterprise');
            if (!plan || !['starter','professional','enterprise'].includes(plan.toLowerCase())) return;
            const cycle = window.prompt('Billing cycle? (monthly / annual)', 'annual') || 'annual';
            const months = parseInt(window.prompt('Duration in months?', '12') || '12');
            const pricing = PLANS[plan.toLowerCase()] || PLANS.enterprise;
            const total = cycle === 'annual' ? pricing.annual * (months/12) : pricing.monthly * months;
            const amount = parseFloat(window.prompt(`Amount received (in ₹)? Default = full plan cost.`, String(total)) || total);
            const mode = window.prompt('Payment mode? (bank_transfer / upi / cash / cheque / razorpay)', 'bank_transfer') || 'bank_transfer';
            const ref = window.prompt('Reference no. (UTR/Cheque/etc.)?', '') || '';
            axios.post(`${API}/super-admin/admins/${admin.username}/convert-trial`,
              { plan: plan.toLowerCase(), billing_cycle: cycle, subscription_months: months, amount, payment_mode: mode, reference_no: ref },
              { headers }).then((r) => {
                if (r.data?.success) { toast.success(r.data.message); fetchData(); }
                else toast.error(r.data?.error || 'Failed to convert');
              }).catch((e) => toast.error(e.response?.data?.error || 'Convert failed'));
          }} />
      )}

      {activeTab === 'payments' && (
        <PaymentsTab payments={payments} onRecordPayment={() => setShowPaymentModal(true)} />
      )}

      {activeTab === 'invoices' && (
        <InvoicesTab
          invoices={invoices}
          onGenerateInvoice={() => setShowInvoiceModal(true)}
          onDownloadPDF={downloadInvoicePDF}
          onMarkStatus={markInvoiceStatus}
        />
      )}

      {activeTab === 'prospects' && (
        <ProspectsTab
          prospects={prospects}
          prospectStats={prospectStats}
          onUpdateStatus={updateProspectStatus}
          onConvert={(p) => {
            setConvertModal(p.prospect_id);
            setConvertData({ password: '', plan: p.plan_interest || 'professional', billing_cycle: 'annual', subscription_months: 12 });
          }}
        />
      )}

      {activeTab === 'health' && (
        <HealthTab healthData={healthData} onOpenLedger={openLedger} />
      )}

      {activeTab === 'admins' && (
        <AdminsTab
          admins={admins}
          expandedAdmin={expandedAdmin}
          setExpandedAdmin={setExpandedAdmin}
          onCreateAdmin={() => setShowCreateModal(true)}
          onToggleActive={toggleActive}
          onEditAdmin={openEditAdmin}
          onResetPassword={(u) => setShowResetModal(u)}
          onDeleteAdmin={deleteAdmin}
        />
      )}

      {activeTab === 'renewals' && (
        <RenewalsTab
          renewals={renewals}
          onRenew={(u) => {
            setProcessModal(u.username);
            setProcessData({ action: 'approve', plan: u.plan, subscription_months: 12, notes: '' });
          }}
        />
      )}

      {activeTab === 'referrals' && <ReferralManagement token={token} />}
      {activeTab === 'questionnaires' && <QuestionnaireLeads headers={headers} />}
      {activeTab === 'activity' && <ActivityLog />}
      {activeTab === 'backups' && <SuperAdminBackups />}

      {activeTab === 'staff' && isSuperAdmin && (
        <StaffTab
          staffList={staffList}
          onNewStaff={setStaffEditing}
          onEditStaff={setStaffEditing}
          onResetPassword={setResetStaffPwd}
          onToggleActive={toggleStaffActive}
          onDeleteStaff={deleteStaff}
        />
      )}

      {/* ===== MODALS ===== */}

      {/* Record Payment Modal — searchable customer picker + due auto-fill */}
      {showPaymentModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4" onClick={e => e.target === e.currentTarget && setShowPaymentModal(false)}>
          <div className="bg-white rounded-xl w-full max-w-lg p-6" data-testid="payment-modal">
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-lg font-semibold text-slate-900">Record Payment</h3>
              <button onClick={() => setShowPaymentModal(false)}><X size={20} className="text-slate-400" /></button>
            </div>
            <div className="space-y-4">
              <div className="relative">
                <label className="block text-sm font-medium text-slate-700 mb-1">Customer *</label>
                <input
                  type="text"
                  value={customerSearchTerm}
                  placeholder="Type name, email or company…"
                  onChange={(e) => {
                    setCustomerSearchTerm(e.target.value);
                    setPaymentCustomer(null);
                    setPaymentForm(f => ({ ...f, customer_username: '', amount: '' }));
                    searchCustomers(e.target.value, setCustomerSuggestions);
                  }}
                  onFocus={() => searchCustomers(customerSearchTerm, setCustomerSuggestions)}
                  className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm"
                  data-testid="payment-customer-search"
                />
                {customerSuggestions.length > 0 && !paymentCustomer && (
                  <div className="absolute z-10 mt-1 w-full max-h-56 overflow-y-auto bg-white border border-slate-200 rounded-lg shadow-lg">
                    {customerSuggestions.map((c) => (
                      <button key={c.username} type="button"
                        onClick={() => selectPaymentCustomer(c)}
                        data-testid={`payment-cust-opt-${c.username}`}
                        className="block w-full text-left px-3 py-2 text-sm hover:bg-emerald-50 border-b border-slate-100 last:border-0">
                        <div className="font-medium text-slate-800">{c.name || c.company_name || c.username}</div>
                        <div className="text-[11px] text-slate-500">{c.username} · {c.plan_name} · Due <b className="text-rose-600">₹{(c.balance_due || 0).toLocaleString('en-IN')}</b></div>
                      </button>
                    ))}
                  </div>
                )}
              </div>

              {paymentCustomer && (
                <div className="bg-slate-50 border border-slate-200 rounded-lg p-3 text-sm space-y-1" data-testid="payment-customer-preview">
                  <div className="flex justify-between"><span className="text-slate-500">Plan</span><span className="font-medium">{paymentCustomer.plan_name} · {paymentCustomer.billing_cycle}</span></div>
                  <div className="flex justify-between"><span className="text-slate-500">Total billed</span><span className="font-medium">₹{(paymentCustomer.total_billed || 0).toLocaleString('en-IN')}</span></div>
                  <div className="flex justify-between"><span className="text-slate-500">Total received</span><span className="font-medium text-emerald-700">₹{(paymentCustomer.total_paid || 0).toLocaleString('en-IN')}</span></div>
                  <div className="flex justify-between border-t border-slate-200 pt-1 mt-1"><span className="text-slate-700 font-semibold">Balance due</span><span className="font-bold text-rose-600">₹{(paymentCustomer.balance_due || 0).toLocaleString('en-IN')}</span></div>
                </div>
              )}

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
              <button onClick={recordPayment} disabled={!paymentForm.customer_username}
                className="w-full py-2.5 bg-emerald-600 text-white rounded-lg font-medium hover:bg-emerald-700 disabled:opacity-40 disabled:cursor-not-allowed"
                data-testid="confirm-payment">
                Record Payment
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Generate Invoice Modal — searchable + fixed plan amount + 0-20% discount */}
      {showInvoiceModal && (() => {
        const disc = Math.max(0, Math.min(20, parseFloat(invoiceForm.discount_pct) || 0));
        const base = invoiceCustomer?.base_price || 0;
        const discAmt = Math.round(base * disc / 100 * 100) / 100;
        const finalAmt = Math.round((base - discAmt) * 100) / 100;
        return (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4" onClick={e => e.target === e.currentTarget && setShowInvoiceModal(false)}>
          <div className="bg-white rounded-xl w-full max-w-lg p-6" data-testid="invoice-modal">
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-lg font-semibold text-slate-900">Generate Invoice</h3>
              <button onClick={() => setShowInvoiceModal(false)}><X size={20} className="text-slate-400" /></button>
            </div>
            <div className="space-y-4">
              <div className="relative">
                <label className="block text-sm font-medium text-slate-700 mb-1">Customer *</label>
                <input
                  type="text"
                  value={invoiceSearchTerm}
                  placeholder="Type name, email or company…"
                  onChange={(e) => {
                    setInvoiceSearchTerm(e.target.value);
                    setInvoiceCustomer(null);
                    setInvoiceForm(f => ({ ...f, customer_username: '' }));
                    searchCustomers(e.target.value, setInvoiceSuggestions);
                  }}
                  onFocus={() => searchCustomers(invoiceSearchTerm, setInvoiceSuggestions)}
                  className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm"
                  data-testid="invoice-customer-search"
                />
                {invoiceSuggestions.length > 0 && !invoiceCustomer && (
                  <div className="absolute z-10 mt-1 w-full max-h-56 overflow-y-auto bg-white border border-slate-200 rounded-lg shadow-lg">
                    {invoiceSuggestions.map((c) => (
                      <button key={c.username} type="button"
                        onClick={() => selectInvoiceCustomer(c)}
                        data-testid={`invoice-cust-opt-${c.username}`}
                        className="block w-full text-left px-3 py-2 text-sm hover:bg-blue-50 border-b border-slate-100 last:border-0">
                        <div className="font-medium text-slate-800">{c.name || c.company_name || c.username}</div>
                        <div className="text-[11px] text-slate-500">{c.username} · {c.plan_name} · {c.billing_cycle} ₹{(c.base_price || 0).toLocaleString('en-IN')}</div>
                      </button>
                    ))}
                  </div>
                )}
              </div>

              {invoiceCustomer && (
                <div className="bg-blue-50/60 border border-blue-200 rounded-lg p-3 text-sm space-y-1" data-testid="invoice-customer-preview">
                  <div className="flex justify-between"><span className="text-slate-600">Plan</span><span className="font-medium">{invoiceCustomer.plan_name} · {invoiceCustomer.billing_cycle}</span></div>
                  <div className="flex justify-between"><span className="text-slate-600">Base amount (fixed)</span><span className="font-semibold">₹{base.toLocaleString('en-IN')}</span></div>
                  <div className="flex justify-between"><span className="text-slate-600">Discount</span><span className="text-rose-600">−₹{discAmt.toLocaleString('en-IN')} ({disc.toFixed(1)}%)</span></div>
                  <div className="flex justify-between border-t border-blue-200 pt-1 mt-1"><span className="text-slate-800 font-semibold">Final invoice</span><span className="font-bold text-blue-700" data-testid="invoice-final-amount">₹{finalAmt.toLocaleString('en-IN')}</span></div>
                </div>
              )}

              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Discount % (0 – 20)</label>
                <input
                  type="number" min={0} max={20} step={0.5}
                  value={invoiceForm.discount_pct}
                  onChange={(e) => {
                    const v = Math.max(0, Math.min(20, parseFloat(e.target.value) || 0));
                    setInvoiceForm(p => ({ ...p, discount_pct: v }));
                  }}
                  className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm"
                  placeholder="0"
                  data-testid="invoice-discount-pct"
                />
                <p className="text-[10px] text-slate-400 mt-1">Capped at 20 %. Applied to this invoice only.</p>
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Description</label>
                <input type="text" value={invoiceForm.description} onChange={e => setInvoiceForm(p => ({ ...p, description: e.target.value }))}
                  className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm" placeholder="Defaults to plan subscription" data-testid="invoice-description" />
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
              <button onClick={generateInvoice} disabled={!invoiceForm.customer_username}
                className="w-full py-2.5 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 disabled:opacity-40 disabled:cursor-not-allowed"
                data-testid="confirm-invoice">
                Generate Invoice · ₹{finalAmt.toLocaleString('en-IN')}
              </button>
            </div>
          </div>
        </div>
        );
      })()}

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
                        <button onClick={() => downloadInvoicePDF(inv.invoice_id, inv.invoice_number)} className="p-1 text-slate-400 hover:text-blue-600"><Download size={14} /></button>
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
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Password *</label>
                <div className="flex gap-2">
                  <input type="text" value={newAdmin.password} onChange={e => setNewAdmin({ ...newAdmin, password: e.target.value })} className="flex-1 min-w-0 px-3 py-2 border border-slate-200 rounded-lg text-sm font-mono" placeholder="Enter or generate" data-testid="new-admin-password" />
                  <button type="button" onClick={() => { const p = generateStrongPassword(); setNewAdmin({ ...newAdmin, password: p }); toast.success('Strong password generated'); }} className="flex items-center gap-1 px-3 py-2 text-xs font-semibold bg-gradient-to-r from-purple-600 to-blue-600 text-white rounded-lg hover:from-purple-700 hover:to-blue-700 whitespace-nowrap" data-testid="generate-password-btn" title="Generate a 12-character strong password">
                    <Sparkles size={14}/>Generate
                  </button>
                  <button type="button" disabled={!newAdmin.password} onClick={async () => { try { await navigator.clipboard.writeText(newAdmin.password); toast.success('Password copied'); } catch { toast.error('Copy failed'); } }} className="flex items-center gap-1 px-3 py-2 text-xs font-semibold bg-slate-100 text-slate-700 rounded-lg hover:bg-slate-200 disabled:opacity-50" data-testid="copy-password-btn" title="Copy password to clipboard">
                    <Copy size={14}/>
                  </button>
                </div>
                <p className="text-[10px] text-slate-400 mt-1">Tip: this password is included in the welcome email sent to the new admin. Ask them to change it after first login.</p>
              </div>
              <div><label className="block text-sm font-medium text-slate-700 mb-1">Full Name *</label><input type="text" value={newAdmin.name} onChange={e => setNewAdmin({ ...newAdmin, name: e.target.value })} className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm" data-testid="new-admin-name" placeholder="Customer's full name" /></div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">Mobile (WhatsApp) *</label>
                  <input type="tel" value={newAdmin.mobile} onChange={e => setNewAdmin({ ...newAdmin, mobile: e.target.value })} className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm" data-testid="new-admin-mobile" placeholder="+91…" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">City *</label>
                  <input type="text" value={newAdmin.city} onChange={e => setNewAdmin({ ...newAdmin, city: e.target.value })} className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm" data-testid="new-admin-city" />
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Complete Address</label>
                <textarea value={newAdmin.address} onChange={e => setNewAdmin({ ...newAdmin, address: e.target.value })} rows={2}
                  className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm" data-testid="new-admin-address"
                  placeholder="Street, area, state, PIN" />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">Company Name *</label>
                  <input type="text" value={newAdmin.company_name} onChange={e => setNewAdmin({ ...newAdmin, company_name: e.target.value })} className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm" data-testid="new-admin-company" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">GST No.</label>
                  <input type="text" value={newAdmin.gst} onChange={e => setNewAdmin({ ...newAdmin, gst: e.target.value.toUpperCase() })} placeholder='GSTIN or "URP"'
                    className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm font-mono uppercase" data-testid="new-admin-gst" />
                  <p className="text-[10px] text-slate-400 mt-1">Enter <b>URP</b> if the customer is unregistered.</p>
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Business Industry *</label>
                <select value={newAdmin.industry} onChange={e => setNewAdmin({ ...newAdmin, industry: e.target.value })}
                  className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm" data-testid="new-admin-industry">
                  <option value="">Select industry…</option>
                  {industries.map((it) => <option key={it} value={it}>{it}</option>)}
                </select>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">Sales team size *</label>
                  <input type="number" min={0} value={newAdmin.sales_count} onChange={e => setNewAdmin({ ...newAdmin, sales_count: Math.max(0, parseInt(e.target.value) || 0) })}
                    className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm" data-testid="new-admin-sales-count" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">Dispatch team size *</label>
                  <input type="number" min={0} value={newAdmin.dispatch_count} onChange={e => setNewAdmin({ ...newAdmin, dispatch_count: Math.max(0, parseInt(e.target.value) || 0) })}
                    className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm" data-testid="new-admin-dispatch-count" />
                </div>
              </div>
              <p className="text-[10px] text-slate-400 -mt-2">Informational only. Employee cap is enforced by the plan.</p>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">Plan</label>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                  {Object.entries(PLANS).map(([id, plan]) => (
                    <button key={id} onClick={() => setNewAdmin({ ...newAdmin, plan: id, features: [...plan.features] })}
                      className={`p-3 border rounded-lg text-left ${newAdmin.plan === id ? (id === 'trial' ? 'border-cyan-500 bg-cyan-50 ring-1 ring-cyan-500' : 'border-blue-500 bg-blue-50 ring-1 ring-blue-500') : 'border-slate-200'}`} data-testid={`new-plan-${id}`}>
                      <p className="text-sm font-bold">{plan.name}</p>
                      <p className={`text-xs ${id === 'trial' ? 'text-cyan-700 font-semibold' : 'text-blue-600'}`}>
                        {id === 'trial' ? 'Free · 14 days' :
                          formatINR(newAdmin.billing_cycle === 'annual' ? Math.round(plan.annual / 12) : plan.monthly) + '/mo'}
                      </p>
                      <div className="text-[10px] text-slate-500 mt-1">{plan.maxCompanies} co | {plan.maxEmployees} emp</div>
                    </button>
                  ))}
                </div>
              </div>
              {newAdmin.plan !== 'trial' && (
                <>
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
                </>
              )}
              {newAdmin.plan === 'trial' && (
                <div className="bg-cyan-50 border border-cyan-200 rounded-lg p-3 text-xs text-cyan-900 leading-relaxed">
                  <b>Free Trial (14 days)</b> · Full Enterprise features. Login is disabled on day 14 if not converted. Reminder emails go out on day 5, 8, 12 and 14 automatically.
                </div>
              )}
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

      {/* Create / Edit Flowra Staff Modal */}
      {staffEditing && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4" onClick={e => e.target === e.currentTarget && setStaffEditing(null)}>
          <div className="bg-white rounded-xl w-full max-w-xl max-h-[90vh] overflow-y-auto p-6" data-testid="staff-modal">
            <div className="flex items-center justify-between mb-5">
              <h3 className="text-lg font-semibold text-slate-900">
                {staffEditing._isNew ? 'New Staff Account' : `Edit ${staffEditing.username}`}
              </h3>
              <button onClick={() => setStaffEditing(null)}><X size={20} className="text-slate-400" /></button>
            </div>

            <div className="space-y-4">
              {staffEditing._isNew ? (
                <>
                  <div>
                    <label className="block text-xs font-semibold text-slate-700 mb-1">Email *</label>
                    <input type="email" value={staffEditing.username}
                      onChange={e => setStaffEditing(p => ({ ...p, username: e.target.value }))}
                      className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm"
                      placeholder="employee@flowra.in" data-testid="staff-email-input" />
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-slate-700 mb-1">Full Name *</label>
                    <input type="text" value={staffEditing.name}
                      onChange={e => setStaffEditing(p => ({ ...p, name: e.target.value }))}
                      className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm"
                      placeholder="Riya Sharma" data-testid="staff-name-input" />
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-slate-700 mb-1">Initial Password *</label>
                    <div className="flex gap-2">
                      <input type="text" value={staffEditing.password}
                        onChange={e => setStaffEditing(p => ({ ...p, password: e.target.value }))}
                        className="flex-1 px-3 py-2 border border-slate-200 rounded-lg text-sm font-mono"
                        data-testid="staff-password-input" />
                      <button type="button"
                        onClick={() => setStaffEditing(p => ({ ...p, password: generateStrongPassword() }))}
                        className="px-3 py-2 border border-slate-200 rounded-lg text-xs flex items-center gap-1 hover:bg-slate-50"
                        data-testid="staff-generate-pwd">
                        <Sparkles size={12} /> Generate
                      </button>
                      <button type="button"
                        onClick={() => { navigator.clipboard.writeText(staffEditing.password); toast.success('Password copied'); }}
                        className="px-3 py-2 border border-slate-200 rounded-lg text-xs flex items-center gap-1 hover:bg-slate-50">
                        <Copy size={12} /> Copy
                      </button>
                    </div>
                    <p className="text-[10px] text-slate-400 mt-1">Staff will be required to change this on first login.</p>
                  </div>
                </>
              ) : (
                <div className="p-3 bg-slate-50 rounded-lg">
                  <div className="text-xs text-slate-500">Editing</div>
                  <div className="font-medium">{staffEditing.name} <span className="text-slate-400 font-normal">·</span> <span className="text-slate-500 font-normal">{staffEditing.username}</span></div>
                </div>
              )}

              {/* Feature checklist */}
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-2">
                  Tabs Enabled ({(staffEditing.features || []).length}/{STAFF_FEATURES_LIST.length})
                </label>
                <div className="grid grid-cols-2 gap-1.5 p-3 bg-slate-50 rounded-lg border border-slate-200">
                  {STAFF_FEATURES_LIST.map(f => {
                    const checked = (staffEditing.features || []).includes(f.id);
                    return (
                      <label key={f.id}
                        className={`flex items-center gap-2 px-2 py-1.5 rounded cursor-pointer text-xs transition ${checked ? 'bg-blue-50 text-blue-800' : 'hover:bg-white text-slate-600'}`}
                        data-testid={`staff-feature-${f.id}`}>
                        <input type="checkbox" checked={checked} onChange={() => {
                          setStaffEditing(prev => ({
                            ...prev,
                            features: checked
                              ? (prev.features || []).filter(x => x !== f.id)
                              : [...(prev.features || []), f.id],
                          }));
                        }} className="w-3.5 h-3.5 rounded border-slate-300 text-blue-600 focus:ring-blue-500" />
                        <span className="font-medium">{f.label}</span>
                      </label>
                    );
                  })}
                </div>
                <div className="flex gap-2 mt-2">
                  <button type="button" onClick={() => setStaffEditing(p => ({ ...p, features: STAFF_FEATURES_LIST.map(x => x.id) }))}
                    className="text-[11px] text-blue-600 hover:underline">Select all</button>
                  <span className="text-slate-300">·</span>
                  <button type="button" onClick={() => setStaffEditing(p => ({ ...p, features: [] }))}
                    className="text-[11px] text-slate-500 hover:underline">Clear</button>
                </div>
              </div>

              <div className="flex justify-end gap-3 pt-2">
                <button onClick={() => setStaffEditing(null)} className="px-4 py-2 text-sm border border-slate-200 rounded-lg">Cancel</button>
                <button onClick={submitStaffForm} className="px-4 py-2 text-sm bg-[#2563EB] text-white rounded-lg font-medium" data-testid="staff-submit">
                  {staffEditing._isNew ? 'Create Staff' : 'Save Features'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Reset Staff Password Modal */}
      {resetStaffPwd && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4" onClick={e => e.target === e.currentTarget && setResetStaffPwd(null)}>
          <div className="bg-white rounded-xl p-6 w-full max-w-sm" data-testid="staff-reset-modal">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-slate-900">Reset Staff Password</h3>
              <button onClick={() => setResetStaffPwd(null)}><X size={20} className="text-slate-400" /></button>
            </div>
            <p className="text-sm text-slate-500 mb-3">Reset for <strong>{resetStaffPwd.username}</strong></p>
            <div className="flex gap-2">
              <input type="text" value={resetStaffPwd.password}
                onChange={e => setResetStaffPwd(p => ({ ...p, password: e.target.value }))}
                className="flex-1 px-3 py-2 border border-slate-200 rounded-lg text-sm font-mono"
                data-testid="staff-reset-input" />
              <button onClick={() => setResetStaffPwd(p => ({ ...p, password: generateStrongPassword() }))}
                className="px-3 py-2 border border-slate-200 rounded-lg text-xs flex items-center gap-1 hover:bg-slate-50">
                <Sparkles size={12} />
              </button>
              <button onClick={() => { navigator.clipboard.writeText(resetStaffPwd.password); toast.success('Copied'); }}
                className="px-3 py-2 border border-slate-200 rounded-lg text-xs flex items-center gap-1 hover:bg-slate-50">
                <Copy size={12} />
              </button>
            </div>
            <div className="flex justify-end gap-3 mt-5">
              <button onClick={() => setResetStaffPwd(null)} className="px-4 py-2 text-sm border border-slate-200 rounded-lg">Cancel</button>
              <button onClick={submitResetStaffPwd} className="px-4 py-2 text-sm bg-[#2563EB] text-white rounded-lg" data-testid="staff-reset-confirm">Reset</button>
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
                  {(Array.isArray(q.pain_points) ? q.pain_points : []).length > 0 && (
                    <div className="mb-2">
                      <span className="text-[10px] font-semibold text-slate-500 uppercase tracking-wide">Pain Points:</span>
                      <div className="flex flex-wrap gap-1 mt-1">
                        {q.pain_points.map((p, i) => <span key={i} className="px-2 py-0.5 bg-red-50 text-red-700 rounded text-[10px]">{String(p).slice(0, 50)}</span>)}
                      </div>
                    </div>
                  )}
                  {q.biggest_challenge && <p className="text-xs text-slate-600 mb-2"><span className="font-semibold text-slate-500">Challenge:</span> {q.biggest_challenge}</p>}
                  {(Array.isArray(q.next_steps) ? q.next_steps : []).length > 0 && (
                    <div className="mb-3">
                      <span className="text-[10px] font-semibold text-slate-500 uppercase tracking-wide">Requested:</span>
                      <div className="flex flex-wrap gap-1 mt-1">
                        {q.next_steps.map((n, i) => <span key={i} className="px-2 py-0.5 bg-blue-50 text-blue-700 rounded text-[10px]">{String(n)}</span>)}
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
