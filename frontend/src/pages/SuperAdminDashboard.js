import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import {
  Users, Shield, ToggleLeft, ToggleRight, Trash2, Key,
  Plus, ChevronDown, ChevronUp, RefreshCw, Activity,
  Lock, Eye, EyeOff, X, Pencil, Calendar, Clock, Building2,
  UserPlus, Phone, Mail, FileText, ArrowRightCircle, AlertTriangle, Check
} from 'lucide-react';
import ActivityLog from './ActivityLog';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

const ALL_FEATURES = [
  { id: 'dashboard', label: 'Dashboard', desc: 'Overview stats & charts' },
  { id: 'sales', label: 'Sales', desc: 'Sales vouchers & analytics' },
  { id: 'crm', label: 'CRM', desc: 'Customer outstanding & behavior' },
  { id: 'inventory', label: 'Inventory', desc: 'Stock management & items' },
  { id: 'analytics', label: 'Analytics', desc: 'Movement analysis & reports' },
  { id: 'salesman', label: 'Salesman', desc: 'Salesman performance' },
  { id: 'ai_reports', label: 'AI Reports', desc: 'AI-powered insights' },
  { id: 'insider', label: 'Insider Result', desc: 'BI analytics & forecasts' },
  { id: 'sync_history', label: 'Sync History', desc: 'Data sync logs' },
  { id: 'setup', label: 'Setup', desc: 'Tally connection settings' },
];

const SuperAdminDashboard = ({ token }) => {
  const [stats, setStats] = useState(null);
  const [admins, setAdmins] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showResetModal, setShowResetModal] = useState(null);
  const [showEditModal, setShowEditModal] = useState(null);
  const [expandedAdmin, setExpandedAdmin] = useState(null);
  const [newAdmin, setNewAdmin] = useState({ username: '', password: '', name: '', plan: 'starter', billing_cycle: 'annual', subscription_months: 12 });
  const [editAdmin, setEditAdmin] = useState(null);
  const [resetPassword, setResetPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [activeTab, setActiveTab] = useState('admins');
  const [prospects, setProspects] = useState([]);
  const [prospectStats, setProspectStats] = useState({});
  const [convertModal, setConvertModal] = useState(null);
  const [convertData, setConvertData] = useState({ password: '', plan: 'professional', billing_cycle: 'annual', subscription_months: 12 });
  const [renewals, setRenewals] = useState({ renewal_requests: [], near_expiry: [], expired: [], stats: {} });
  const [processModal, setProcessModal] = useState(null);
  const [processData, setProcessData] = useState({ action: 'approve', plan: '', subscription_months: 12, notes: '' });

  const PLANS = {
    starter: { name: 'Starter', monthly: 999, annual: 9990, maxCompanies: 1, maxEmployees: 2, features: ['dashboard', 'sales', 'inventory', 'sync_history', 'setup'] },
    professional: { name: 'Professional', monthly: 2499, annual: 24990, maxCompanies: 3, maxEmployees: 5, features: ['dashboard', 'sales', 'crm', 'inventory', 'analytics', 'sync_history', 'setup'] },
    enterprise: { name: 'Enterprise', monthly: 3799, annual: 37990, maxCompanies: 10, maxEmployees: 20, features: ALL_FEATURES.map(f => f.id) }
  };

  const headers = token ? { Authorization: `Bearer ${token}` } : {};

  const fetchData = useCallback(async () => {
    try {
      setLoading(true);
      const [statsRes, adminsRes, prospectsRes, renewalsRes] = await Promise.all([
        axios.get(`${API}/super-admin/stats`, { headers }),
        axios.get(`${API}/super-admin/admins`, { headers }),
        axios.get(`${API}/super-admin/prospects`, { headers }).catch(() => ({ data: { data: { prospects: [], stats: {} } } })),
        axios.get(`${API}/super-admin/renewals`, { headers }).catch(() => ({ data: { data: { renewal_requests: [], near_expiry: [], expired: [], stats: {} } } }))
      ]);
      setStats(statsRes.data?.data);
      setAdmins(adminsRes.data?.data?.admins || []);
      setProspects(prospectsRes.data?.data?.prospects || []);
      setProspectStats(prospectsRes.data?.data?.stats || {});
      setRenewals(renewalsRes.data?.data || { renewal_requests: [], near_expiry: [], expired: [], stats: {} });
    } catch (err) {
      toast.error('Failed to fetch data');
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const createAdmin = async () => {
    if (!newAdmin.username || !newAdmin.password) {
      toast.error('Email and password are required');
      return;
    }
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(newAdmin.username)) {
      toast.error('Please enter a valid email address');
      return;
    }
    try {
      const res = await axios.post(`${API}/super-admin/admins`, {
        ...newAdmin,
        subscription_months: newAdmin.subscription_months || 12
      }, { headers });
      if (res.data?.success) {
        toast.success(`Admin '${newAdmin.username}' created with ${newAdmin.plan} plan`);
        setShowCreateModal(false);
        setNewAdmin({ username: '', password: '', name: '', plan: 'starter', billing_cycle: 'annual', subscription_months: 12 });
        fetchData();
      } else {
        toast.error(res.data?.error || 'Failed to create admin');
      }
    } catch (err) {
      toast.error('Failed to create admin');
    }
  };

  const openEditAdmin = (admin) => {
    setEditAdmin({
      username: admin.username,
      name: admin.name || '',
      plan: admin.plan || 'enterprise',
      billing_cycle: admin.billing_cycle || 'annual',
      features: [...(admin.features || [])],
      subscription_months: admin.subscription_months || 12,
      subscription_start: admin.subscription_start || admin.created_at || ''
    });
    setShowEditModal(admin.username);
  };

  const saveEditAdmin = async () => {
    if (!editAdmin) return;
    try {
      // Update subscription with plan
      await axios.put(`${API}/super-admin/admins/${editAdmin.username}/subscription`, {
        name: editAdmin.name,
        plan: editAdmin.plan,
        billing_cycle: editAdmin.billing_cycle,
        subscription_months: editAdmin.subscription_months
      }, { headers });
      toast.success('Admin updated successfully');
      setShowEditModal(null);
      setEditAdmin(null);
      fetchData();
    } catch (err) {
      toast.error('Failed to update admin');
    }
  };

  const toggleFeature = async (username, currentFeatures, featureId) => {
    const updated = currentFeatures.includes(featureId)
      ? currentFeatures.filter(f => f !== featureId)
      : [...currentFeatures, featureId];
    try {
      const res = await axios.put(`${API}/super-admin/admins/${username}/features`, { features: updated }, { headers });
      if (res.data?.success) {
        setAdmins(prev => prev.map(a =>
          a.username === username ? { ...a, features: updated } : a
        ));
        toast.success('Feature updated');
      }
    } catch (err) {
      toast.error('Failed to update feature');
    }
  };

  const toggleActive = async (username) => {
    try {
      const res = await axios.put(`${API}/super-admin/admins/${username}/toggle-active`, {}, { headers });
      if (res.data?.success) {
        toast.success(res.data.message);
        fetchData(); // Refresh all data including stats
      }
    } catch (err) {
      toast.error('Failed to toggle status');
    }
  };

  const deleteAdmin = async (username) => {
    if (!window.confirm(`DELETE admin '${username}' and ALL their data? This cannot be undone.`)) return;
    try {
      const res = await axios.delete(`${API}/super-admin/admins/${username}`, { headers });
      if (res.data?.success) {
        toast.success(res.data.message);
        fetchData();
      } else {
        toast.error(res.data?.error || 'Failed to delete');
      }
    } catch (err) {
      toast.error('Failed to delete admin');
    }
  };

  const handleResetPassword = async () => {
    if (!resetPassword || resetPassword.length < 4) {
      toast.error('Password must be at least 4 characters');
      return;
    }
    try {
      const res = await axios.post(
        `${API}/super-admin/admins/${showResetModal}/reset-password`,
        { new_password: resetPassword },
        { headers }
      );
      if (res.data?.success) {
        toast.success(res.data.message);
        setShowResetModal(null);
        setResetPassword('');
      } else {
        toast.error(res.data?.error || 'Failed to reset');
      }
    } catch (err) {
      toast.error('Failed to reset password');
    }
  };

  const toggleAllFeatures = async (username, currentFeatures) => {
    const allIds = ALL_FEATURES.map(f => f.id);
    const allActive = allIds.every(id => currentFeatures.includes(id));
    const updated = allActive ? [] : allIds;
    try {
      const res = await axios.put(`${API}/super-admin/admins/${username}/features`, { features: updated }, { headers });
      if (res.data?.success) {
        setAdmins(prev => prev.map(a =>
          a.username === username ? { ...a, features: updated } : a
        ));
        toast.success(allActive ? 'All features deactivated' : 'All features activated');
      }
    } catch (err) {
      toast.error('Failed to update features');
    }
  };

  const updateProspectStatus = async (prospectId, status, notes = '') => {
    try {
      const res = await axios.put(`${API}/super-admin/prospects/${prospectId}/status`, { status, notes }, { headers });
      if (res.data?.success) {
        toast.success(`Status updated to "${status}"`);
        fetchData();
      }
    } catch (err) { toast.error('Failed to update status'); }
  };

  const convertProspect = async () => {
    if (!convertModal) return;
    if (!convertData.password || convertData.password.length < 6) {
      toast.error('Password must be at least 6 characters');
      return;
    }
    try {
      const res = await axios.post(`${API}/super-admin/prospects/${convertModal}/convert`, {
        password: convertData.password,
        plan: convertData.plan,
        billing_cycle: convertData.billing_cycle,
        subscription_months: convertData.subscription_months
      }, { headers });
      if (res.data?.success) {
        toast.success(`Converted to admin: ${res.data.data.username}`);
        setConvertModal(null);
        setConvertData({ password: '', plan: 'professional', billing_cycle: 'annual', subscription_months: 12 });
        fetchData();
      } else {
        toast.error(res.data?.error);
      }
    } catch (err) { toast.error(err.response?.data?.error || 'Conversion failed'); }
  };

  const statusColors = {
    new: 'bg-blue-50 text-blue-700',
    contacted: 'bg-amber-50 text-amber-700',
    demo_given: 'bg-purple-50 text-purple-700',
    requirements_submitted: 'bg-indigo-50 text-indigo-700',
    negotiating: 'bg-cyan-50 text-cyan-700',
    converted: 'bg-green-50 text-green-700',
    lost: 'bg-red-50 text-red-700'
  };

  if (loading) {
    return <div className="flex items-center justify-center h-64"><div className="loading-spinner" /></div>;
  }

  return (
    <div className="max-w-7xl mx-auto" data-testid="super-admin-dashboard">
      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
        <div className="bg-white border border-slate-200 rounded-xl p-5">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-lg bg-blue-50"><Users size={20} className="text-blue-600" /></div>
            <div>
              <div className="text-2xl font-bold text-slate-900">{stats?.total_admins || 0}</div>
              <div className="text-xs text-slate-500">Total Admins</div>
            </div>
          </div>
        </div>
        <div className="bg-white border border-slate-200 rounded-xl p-5">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-lg bg-green-50"><Activity size={20} className="text-green-600" /></div>
            <div>
              <div className="text-2xl font-bold text-green-600">{stats?.active_admins || 0}</div>
              <div className="text-xs text-slate-500">Active</div>
            </div>
          </div>
        </div>
        <div className="bg-white border border-slate-200 rounded-xl p-5">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-lg bg-red-50"><Shield size={20} className="text-red-600" /></div>
            <div>
              <div className="text-2xl font-bold text-red-600">{stats?.inactive_admins || 0}</div>
              <div className="text-xs text-slate-500">Inactive</div>
            </div>
          </div>
        </div>
        <div className="bg-white border border-slate-200 rounded-xl p-5">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-lg bg-purple-50"><Users size={20} className="text-purple-600" /></div>
            <div>
              <div className="text-2xl font-bold text-purple-600">{stats?.total_employees || 0}</div>
              <div className="text-xs text-slate-500">Total Employees</div>
            </div>
          </div>
        </div>
      </div>

      {/* Tab Navigation */}
      <div className="flex items-center gap-1 mb-6 border-b border-slate-200">
        <button
          onClick={() => setActiveTab('admins')}
          className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${activeTab === 'admins' ? 'border-[#2563EB] text-[#2563EB]' : 'border-transparent text-slate-500 hover:text-slate-700'}`}
          data-testid="tab-admins"
        >
          <span className="flex items-center gap-1.5"><Users size={14} /> Admin Management</span>
        </button>
        <button
          onClick={() => setActiveTab('activity')}
          className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${activeTab === 'activity' ? 'border-[#2563EB] text-[#2563EB]' : 'border-transparent text-slate-500 hover:text-slate-700'}`}
          data-testid="tab-activity"
        >
          <span className="flex items-center gap-1.5"><Activity size={14} /> Activity Log</span>
        </button>
        <button
          onClick={() => setActiveTab('enquiries')}
          className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${activeTab === 'enquiries' ? 'border-[#2563EB] text-[#2563EB]' : 'border-transparent text-slate-500 hover:text-slate-700'}`}
          data-testid="tab-enquiries"
        >
          <span className="flex items-center gap-1.5"><UserPlus size={14} /> Enquiries {prospectStats.new > 0 && <span className="bg-red-500 text-white text-[10px] font-bold px-1.5 py-0.5 rounded-full">{prospectStats.new}</span>}</span>
        </button>
        <button
          onClick={() => setActiveTab('renewals')}
          className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${activeTab === 'renewals' ? 'border-[#2563EB] text-[#2563EB]' : 'border-transparent text-slate-500 hover:text-slate-700'}`}
          data-testid="tab-renewals"
        >
          <span className="flex items-center gap-1.5"><RefreshCw size={14} /> Renewals {(renewals.stats?.pending_renewals > 0 || renewals.stats?.expired_count > 0) && <span className="bg-red-500 text-white text-[10px] font-bold px-1.5 py-0.5 rounded-full">{(renewals.stats?.pending_renewals || 0) + (renewals.stats?.expired_count || 0)}</span>}</span>
        </button>
      </div>

      {activeTab === 'activity' && (
        <div className="bg-white border border-slate-200 rounded-xl p-6">
          <ActivityLog token={token} role="super_admin" />
        </div>
      )}

      {activeTab === 'enquiries' && (
        <div data-testid="enquiries-section">
          {/* Enquiry Stats */}
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-6">
            {[
              { label: 'Total', value: prospectStats.total || 0, color: 'text-slate-700' },
              { label: 'New', value: prospectStats.new || 0, color: 'text-blue-600' },
              { label: 'Contacted', value: prospectStats.contacted || 0, color: 'text-amber-600' },
              { label: 'Demo Given', value: prospectStats.demo_given || 0, color: 'text-purple-600' },
              { label: 'Converted', value: prospectStats.converted || 0, color: 'text-green-600' },
            ].map(s => (
              <div key={s.label} className="bg-white border border-slate-200 rounded-xl p-4">
                <div className={`text-xl font-bold ${s.color}`}>{s.value}</div>
                <div className="text-xs text-slate-500">{s.label}</div>
              </div>
            ))}
          </div>

          {/* Enquiry List */}
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-slate-900">Customer Enquiries</h2>
            <button onClick={fetchData} className="px-3 py-2 text-sm border border-slate-200 rounded-lg hover:bg-slate-50 flex items-center gap-1.5">
              <RefreshCw size={14} /> Refresh
            </button>
          </div>

          {prospects.length === 0 ? (
            <div className="bg-white border border-slate-200 rounded-xl p-12 text-center text-slate-400">
              <UserPlus size={32} className="mx-auto mb-3 opacity-50" />
              <p className="font-medium">No enquiries yet</p>
              <p className="text-sm">New prospect signups will appear here</p>
            </div>
          ) : (
            <div className="space-y-3">
              {prospects.map(p => (
                <div key={p.prospect_id} className="bg-white border border-slate-200 rounded-xl p-5" data-testid={`prospect-${p.prospect_id}`}>
                  <div className="flex items-start justify-between mb-3">
                    <div>
                      <div className="flex items-center gap-2 mb-1">
                        <Building2 size={15} className="text-slate-400" />
                        <span className="font-semibold text-slate-900">{p.company_name}</span>
                        <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${statusColors[p.status] || 'bg-slate-100 text-slate-600'}`}>
                          {(p.status || 'new').replace(/_/g, ' ').toUpperCase()}
                        </span>
                      </div>
                      <div className="flex items-center gap-4 text-xs text-slate-500">
                        <span className="flex items-center gap-1"><Mail size={11} /> {p.email}</span>
                        <span className="flex items-center gap-1"><Phone size={11} /> {p.phone}</span>
                        <span>{p.prospect_id}</span>
                      </div>
                    </div>
                    <div className="flex items-center gap-2 flex-shrink-0">
                      <select value={p.status}
                        onChange={e => updateProspectStatus(p.prospect_id, e.target.value)}
                        className="text-xs border border-slate-200 rounded-lg px-2 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500"
                        data-testid={`prospect-status-${p.prospect_id}`}>
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
                    <div>
                      <span className="text-slate-400">Contact:</span>
                      <span className="ml-1 text-slate-700">{p.contact_person}</span>
                    </div>
                    <div>
                      <span className="text-slate-400">Plan:</span>
                      <span className="ml-1 text-slate-700 capitalize">{p.selected_plan || 'Not selected'}</span>
                    </div>
                    <div>
                      <span className="text-slate-400">Demo:</span>
                      <span className={`ml-1 ${p.demo_completed ? 'text-green-600' : p.demo_requested ? 'text-amber-600' : 'text-slate-400'}`}>
                        {p.demo_completed ? 'Completed' : p.demo_requested ? 'Requested' : 'Not requested'}
                      </span>
                    </div>
                    <div>
                      <span className="text-slate-400">Date:</span>
                      <span className="ml-1 text-slate-700">{p.created_at ? new Date(p.created_at).toLocaleDateString('en-IN') : '—'}</span>
                    </div>
                  </div>
                  {(p.requirements && p.requirements.length > 0) && (
                    <div className="mt-3 pt-3 border-t border-slate-100">
                      <p className="text-xs text-slate-400 mb-1">Required Features:</p>
                      <div className="flex flex-wrap gap-1">
                        {p.requirements.map(r => (
                          <span key={r} className="text-[10px] bg-indigo-50 text-indigo-700 px-2 py-0.5 rounded">{r}</span>
                        ))}
                      </div>
                      {p.requirement_notes && <p className="text-xs text-slate-500 mt-1 italic">"{p.requirement_notes}"</p>}
                    </div>
                  )}
                  {p.message && (
                    <p className="text-xs text-slate-500 mt-2 italic border-l-2 border-slate-200 pl-2">"{p.message}"</p>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* Convert Modal */}
          {convertModal && (
            <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
              <div className="bg-white rounded-xl w-full max-w-lg p-6 max-h-[90vh] overflow-y-auto" data-testid="convert-modal">
                <div className="flex items-center justify-between mb-6">
                  <h3 className="text-lg font-semibold text-slate-900">Convert Prospect to Admin</h3>
                  <button onClick={() => setConvertModal(null)}><X size={20} className="text-slate-400" /></button>
                </div>
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-1">Password for new admin *</label>
                    <input type="text" value={convertData.password}
                      onChange={e => setConvertData(prev => ({ ...prev, password: e.target.value }))}
                      className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                      placeholder="Min 6 characters" data-testid="convert-password" />
                  </div>

                  {/* Plan Selection */}
                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-2">Subscription Plan *</label>
                    <div className="grid grid-cols-3 gap-2">
                      {Object.entries(PLANS).map(([id, plan]) => (
                        <button key={id} onClick={() => setConvertData(prev => ({ ...prev, plan: id }))}
                          className={`p-3 border rounded-lg text-left transition-all ${convertData.plan === id ? 'border-blue-500 bg-blue-50 ring-1 ring-blue-500' : 'border-slate-200 hover:border-slate-300'}`}
                          data-testid={`plan-select-${id}`}>
                          <p className="text-sm font-bold text-slate-900">{plan.name}</p>
                          <p className="text-xs text-blue-600 font-medium mt-0.5">
                            {convertData.billing_cycle === 'annual' ? `Rs.${Math.round(plan.annual / 12).toLocaleString('en-IN')}/mo` : `Rs.${plan.monthly.toLocaleString('en-IN')}/mo`}
                          </p>
                          <div className="text-[10px] text-slate-500 mt-1">
                            {plan.maxCompanies} co. | {plan.maxEmployees} emp
                          </div>
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Billing Cycle */}
                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-1">Billing Cycle</label>
                    <div className="flex gap-2">
                      {['monthly', 'annual'].map(cycle => (
                        <button key={cycle} onClick={() => setConvertData(prev => ({ ...prev, billing_cycle: cycle }))}
                          className={`flex-1 py-2 text-sm font-medium rounded-lg border transition-colors ${convertData.billing_cycle === cycle ? 'border-blue-500 bg-blue-50 text-blue-700' : 'border-slate-200 text-slate-600'}`}>
                          {cycle === 'annual' ? 'Annual (Save 17%)' : 'Monthly'}
                        </button>
                      ))}
                    </div>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-1">Subscription Duration</label>
                    <select value={convertData.subscription_months}
                      onChange={e => setConvertData(prev => ({ ...prev, subscription_months: parseInt(e.target.value) }))}
                      className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                      data-testid="convert-subscription">
                      <option value={1}>1 month</option>
                      <option value={3}>3 months</option>
                      <option value={6}>6 months</option>
                      <option value={12}>12 months</option>
                      <option value={24}>24 months</option>
                    </select>
                  </div>

                  {/* Plan features preview */}
                  <div className="bg-slate-50 rounded-lg p-3">
                    <p className="text-xs font-medium text-slate-500 mb-2">Included Features ({PLANS[convertData.plan]?.features.length || 0}):</p>
                    <div className="flex flex-wrap gap-1">
                      {(PLANS[convertData.plan]?.features || []).map(f => (
                        <span key={f} className="text-[10px] bg-white border border-slate-200 text-slate-700 px-2 py-0.5 rounded">{f.replace('_', ' ')}</span>
                      ))}
                    </div>
                    <div className="flex gap-4 mt-2 text-[10px] text-slate-500">
                      <span>Max Companies: <strong>{PLANS[convertData.plan]?.maxCompanies}</strong></span>
                      <span>Max Employees: <strong>{PLANS[convertData.plan]?.maxEmployees}</strong></span>
                    </div>
                  </div>

                  <button onClick={convertProspect} data-testid="convert-confirm-btn"
                    className="w-full bg-green-600 text-white py-2.5 rounded-lg font-medium hover:bg-green-700 flex items-center justify-center gap-2">
                    <ArrowRightCircle size={16} /> Convert to Admin — {PLANS[convertData.plan]?.name} Plan
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {activeTab === 'renewals' && (
        <div data-testid="renewals-section">
          {/* Renewal Stats */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
            {[
              { label: 'Pending Requests', value: renewals.stats?.pending_renewals || 0, color: 'text-amber-600' },
              { label: 'Near Expiry (30d)', value: renewals.stats?.near_expiry_count || 0, color: 'text-orange-600' },
              { label: 'Expired', value: renewals.stats?.expired_count || 0, color: 'text-red-600' },
              { label: 'Total Requests', value: renewals.stats?.total_requests || 0, color: 'text-slate-700' },
            ].map(s => (
              <div key={s.label} className="bg-white border border-slate-200 rounded-xl p-4">
                <p className="text-xs text-slate-500">{s.label}</p>
                <p className={`text-2xl font-bold ${s.color}`}>{s.value}</p>
              </div>
            ))}
          </div>

          {/* Expired Users */}
          {renewals.expired?.length > 0 && (
            <div className="mb-6">
              <h3 className="text-sm font-semibold text-red-700 mb-3 flex items-center gap-1.5"><AlertTriangle size={14} /> Expired Subscriptions</h3>
              <div className="space-y-2">
                {renewals.expired.map(u => (
                  <div key={u.username} className="bg-red-50 border border-red-200 rounded-xl p-4 flex items-center justify-between">
                    <div>
                      <p className="font-medium text-red-900">{u.name || u.username}</p>
                      <p className="text-xs text-red-700">{u.username} | {u.plan?.toUpperCase()} Plan | Tenant: {u.tenant_id}</p>
                      <p className="text-xs text-red-600 mt-1">Expired {Math.abs(u.days_left)} days ago | Was: {new Date(u.subscription_expires).toLocaleDateString('en-IN', { timeZone: 'Asia/Kolkata' })}</p>
                    </div>
                    <button onClick={() => { setProcessModal(u.username); setProcessData({ action: 'approve', plan: u.plan, subscription_months: 12, notes: '' }); }}
                      className="px-4 py-2 bg-green-600 text-white rounded-lg text-xs font-medium hover:bg-green-700" data-testid={`renew-${u.username}`}>
                      Renew
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Near Expiry Users */}
          {renewals.near_expiry?.length > 0 && (
            <div className="mb-6">
              <h3 className="text-sm font-semibold text-amber-700 mb-3 flex items-center gap-1.5"><Clock size={14} /> Expiring Within 30 Days</h3>
              <div className="space-y-2">
                {renewals.near_expiry.map(u => (
                  <div key={u.username} className="bg-amber-50 border border-amber-200 rounded-xl p-4 flex items-center justify-between">
                    <div>
                      <p className="font-medium text-amber-900">{u.name || u.username}</p>
                      <p className="text-xs text-amber-700">{u.username} | {u.plan?.toUpperCase()} Plan | Tenant: {u.tenant_id}</p>
                      <p className="text-xs text-amber-600 mt-1">{u.days_left} days left | Expires: {new Date(u.subscription_expires).toLocaleDateString('en-IN', { timeZone: 'Asia/Kolkata' })}</p>
                    </div>
                    <button onClick={() => { setProcessModal(u.username); setProcessData({ action: 'approve', plan: u.plan, subscription_months: 12, notes: '' }); }}
                      className="px-4 py-2 bg-[#2563EB] text-white rounded-lg text-xs font-medium hover:bg-[#1D4ED8]" data-testid={`extend-${u.username}`}>
                      Extend
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Renewal Requests */}
          <div className="mb-6">
            <h3 className="text-sm font-semibold text-slate-800 mb-3 flex items-center gap-1.5"><FileText size={14} /> Renewal Requests</h3>
            {(renewals.renewal_requests || []).length === 0 ? (
              <div className="bg-white border border-slate-200 rounded-xl p-8 text-center text-slate-400 text-sm">No renewal requests yet</div>
            ) : (
              <div className="space-y-2">
                {renewals.renewal_requests.map((r, i) => (
                  <div key={i} className="bg-white border border-slate-200 rounded-xl p-4">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="font-medium text-slate-900">{r.name || r.username}</p>
                        <p className="text-xs text-slate-500">{r.username} | Current: {r.current_plan?.toUpperCase()} | Interested: {r.plan_interest?.toUpperCase()}</p>
                        {r.message && <p className="text-xs text-slate-600 mt-1 italic">"{r.message}"</p>}
                        <p className="text-xs text-slate-400 mt-1">{new Date(r.created_at).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'Asia/Kolkata' })}</p>
                      </div>
                      <div className="flex items-center gap-2">
                        {r.status === 'pending' ? (
                          <>
                            <button onClick={() => { setProcessModal(r.username); setProcessData({ action: 'approve', plan: r.plan_interest || r.current_plan, subscription_months: 12, notes: '' }); }}
                              className="px-3 py-1.5 bg-green-600 text-white rounded-lg text-xs font-medium hover:bg-green-700">Approve</button>
                            <button onClick={async () => {
                              try {
                                await axios.put(`${API}/super-admin/renewals/${r.username}/process`, { action: 'reject', notes: 'Rejected by admin' }, { headers });
                                toast.success('Request rejected');
                                fetchData();
                              } catch { toast.error('Failed to reject'); }
                            }}
                              className="px-3 py-1.5 bg-red-50 text-red-600 border border-red-200 rounded-lg text-xs font-medium hover:bg-red-100">Reject</button>
                          </>
                        ) : (
                          <span className={`text-xs font-medium px-2.5 py-1 rounded-full ${r.status === 'approved' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
                            {r.status}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {renewals.expired?.length === 0 && renewals.near_expiry?.length === 0 && (renewals.renewal_requests || []).length === 0 && (
            <div className="bg-white border border-slate-200 rounded-xl p-12 text-center">
              <Check size={32} className="mx-auto text-green-500 mb-3" />
              <p className="text-slate-600 font-medium">All subscriptions are healthy</p>
              <p className="text-sm text-slate-400 mt-1">No pending renewals or near-expiry users</p>
            </div>
          )}

          {/* Process Renewal Modal */}
          {processModal && (
            <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
              <div className="bg-white rounded-2xl w-full max-w-md mx-4 p-6">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-base font-semibold text-slate-900">Process Renewal: {processModal}</h3>
                  <button onClick={() => setProcessModal(null)} className="text-slate-400 hover:text-slate-600"><X size={18} /></button>
                </div>
                <div className="space-y-4">
                  <div>
                    <label className="text-xs text-slate-600 font-medium">Plan</label>
                    <div className="flex gap-2 mt-1">
                      {['starter', 'professional', 'enterprise'].map(id => (
                        <button key={id} onClick={() => setProcessData(prev => ({ ...prev, plan: id }))}
                          className={`px-3 py-1.5 rounded-lg text-xs font-medium border ${processData.plan === id ? 'bg-[#2563EB] text-white border-[#2563EB]' : 'border-slate-200 text-slate-600 hover:bg-slate-50'}`}>
                          {PLANS[id]?.name}
                        </button>
                      ))}
                    </div>
                  </div>
                  <div>
                    <label className="text-xs text-slate-600 font-medium">Duration (months)</label>
                    <input type="number" min="1" max="60" value={processData.subscription_months}
                      onChange={e => setProcessData(prev => ({ ...prev, subscription_months: parseInt(e.target.value) || 12 }))}
                      className="w-full mt-1 px-3 py-2 border border-slate-200 rounded-lg text-sm" />
                  </div>
                  <div>
                    <label className="text-xs text-slate-600 font-medium">Notes</label>
                    <textarea value={processData.notes} onChange={e => setProcessData(prev => ({ ...prev, notes: e.target.value }))}
                      rows={2} className="w-full mt-1 px-3 py-2 border border-slate-200 rounded-lg text-sm resize-none" placeholder="Optional notes..." />
                  </div>
                  <button
                    onClick={async () => {
                      try {
                        const res = await axios.put(`${API}/super-admin/renewals/${processModal}/process`, processData, { headers });
                        if (res.data?.success) {
                          toast.success(res.data.message);
                          setProcessModal(null);
                          fetchData();
                        } else { toast.error(res.data?.error || 'Failed'); }
                      } catch { toast.error('Failed to process renewal'); }
                    }}
                    className="w-full py-2.5 bg-green-600 text-white rounded-lg font-medium text-sm hover:bg-green-700"
                    data-testid="process-renewal-btn">
                    Approve & Renew Subscription
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {activeTab === 'admins' && <>
      {/* Admin Management Header */}
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-lg font-semibold text-slate-900">Admin Management</h2>
        <div className="flex gap-2">
          <button onClick={fetchData} className="px-3 py-2 text-sm border border-slate-200 rounded-lg hover:bg-slate-50 flex items-center gap-1.5" data-testid="refresh-admins">
            <RefreshCw size={14} /> Refresh
          </button>
          <button onClick={() => setShowCreateModal(true)} className="px-4 py-2 text-sm bg-[#2563EB] text-white rounded-lg hover:bg-[#1D4ED8] flex items-center gap-1.5" data-testid="create-admin-btn">
            <Plus size={14} /> New Admin
          </button>
        </div>
      </div>

      {/* Admin List */}
      <div className="space-y-4">
        {admins.map((admin) => {
          const joinDate = admin.created_at ? new Date(admin.created_at).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' }) : 'N/A';
          const subMonths = admin.subscription_months || 12;
          const subStart = admin.subscription_start || admin.created_at || '';
          let subEndDate = 'N/A';
          let subActive = false;
          if (subStart) {
            const start = new Date(subStart);
            const end = new Date(start);
            end.setMonth(end.getMonth() + subMonths);
            subEndDate = end.toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' });
            subActive = end > new Date();
          }

          return (
          <div key={admin.username} className="bg-white border border-slate-200 rounded-xl overflow-hidden" data-testid={`admin-card-${admin.username}`}>
            {/* Admin Header */}
            <div className="p-5">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-4 flex-1 min-w-0 cursor-pointer" onClick={() => setExpandedAdmin(expandedAdmin === admin.username ? null : admin.username)}>
                  <div className={`w-3 h-3 rounded-full flex-shrink-0 ${admin.active ? 'bg-green-500' : 'bg-red-400'}`} />
                  <div className="min-w-0">
                    <div className="font-semibold text-slate-900">{admin.name || admin.username}</div>
                    <div className="text-xs text-slate-500 truncate">@{admin.username} &middot; {admin.employee_count || 0}/{admin.max_employees || 20} employees</div>
                  </div>
                </div>
                <div className="flex items-center gap-2 flex-shrink-0">
                  <span className={`text-[10px] px-2 py-0.5 rounded-full font-bold uppercase tracking-wider ${admin.plan === 'enterprise' ? 'bg-purple-50 text-purple-700' : admin.plan === 'professional' ? 'bg-blue-50 text-blue-700' : 'bg-slate-100 text-slate-600'}`}>
                    {admin.plan || 'enterprise'}
                  </span>
                  <span className="text-xs px-2.5 py-1 rounded-full bg-blue-50 text-blue-700 font-medium">
                    {admin.features?.length || 0}/{ALL_FEATURES.length} features
                  </span>
                  <button onClick={(e) => { e.stopPropagation(); toggleActive(admin.username); }} className={`px-3 py-1.5 text-xs rounded-lg font-medium flex items-center gap-1 ${admin.active ? 'bg-green-50 text-green-700 hover:bg-green-100' : 'bg-red-50 text-red-700 hover:bg-red-100'}`} data-testid={`toggle-active-${admin.username}`}>
                    {admin.active ? <ToggleRight size={14} /> : <ToggleLeft size={14} />}
                    {admin.active ? 'Active' : 'Inactive'}
                  </button>
                  <button onClick={(e) => { e.stopPropagation(); openEditAdmin(admin); }} className="p-1.5 text-slate-400 hover:text-blue-600 hover:bg-blue-50 rounded-lg" title="Edit Admin" data-testid={`edit-admin-${admin.username}`}>
                    <Pencil size={14} />
                  </button>
                  <button onClick={(e) => { e.stopPropagation(); setShowResetModal(admin.username); }} className="p-1.5 text-slate-400 hover:text-blue-600 hover:bg-blue-50 rounded-lg" title="Reset Password" data-testid={`reset-pwd-${admin.username}`}>
                    <Key size={14} />
                  </button>
                  <button onClick={(e) => { e.stopPropagation(); deleteAdmin(admin.username); }} className="p-1.5 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded-lg" title="Delete Admin" data-testid={`delete-admin-${admin.username}`}>
                    <Trash2 size={14} />
                  </button>
                  <button onClick={() => setExpandedAdmin(expandedAdmin === admin.username ? null : admin.username)} className="p-1.5 text-slate-400 hover:text-slate-600 rounded-lg" data-testid={`expand-admin-${admin.username}`}>
                    {expandedAdmin === admin.username ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                  </button>
                </div>
              </div>

              {/* Subscription Summary Row */}
              <div className="mt-3 flex flex-wrap items-center gap-3 text-xs text-slate-500">
                <span className="flex items-center gap-1"><Calendar size={12} /> Joined: {joinDate}</span>
                <span className="flex items-center gap-1"><Clock size={12} /> Plan: {subMonths} months</span>
                <span className={`flex items-center gap-1 px-2 py-0.5 rounded-full font-medium ${subActive ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-600'}`}>
                  {subActive ? 'Active' : 'Expired'} until {subEndDate}
                </span>
                {admin.companies?.length > 0 && (
                  <span className="flex items-center gap-1"><Building2 size={12} /> {admin.companies.length}/{admin.max_companies || 10} companies</span>
                )}
              </div>
            </div>

            {/* Feature Toggles (expanded) */}
            {expandedAdmin === admin.username && (
              <div className="border-t border-slate-100 p-5 bg-slate-50/50">
                <div className="flex items-center justify-between mb-4">
                  <h4 className="text-sm font-semibold text-slate-700">Feature Activation</h4>
                  <button
                    onClick={() => toggleAllFeatures(admin.username, admin.features || [])}
                    className="text-xs text-[#2563EB] hover:underline"
                  >
                    {ALL_FEATURES.every(f => (admin.features || []).includes(f.id)) ? 'Deactivate All' : 'Activate All'}
                  </button>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                  {ALL_FEATURES.map((feature) => {
                    const isActive = (admin.features || []).includes(feature.id);
                    return (
                      <div key={feature.id} className={`flex items-center justify-between p-3 rounded-lg border ${isActive ? 'bg-white border-green-200' : 'bg-slate-50 border-slate-200'}`}>
                        <div>
                          <div className="text-sm font-medium text-slate-800">{feature.label}</div>
                          <div className="text-xs text-slate-500">{feature.desc}</div>
                        </div>
                        <button
                          onClick={() => toggleFeature(admin.username, admin.features || [], feature.id)}
                          className={`p-1 rounded-lg transition-colors ${isActive ? 'text-green-600 hover:bg-green-100' : 'text-slate-400 hover:bg-slate-100'}`}
                          data-testid={`toggle-feature-${admin.username}-${feature.id}`}
                        >
                          {isActive ? <ToggleRight size={24} /> : <ToggleLeft size={24} />}
                        </button>
                      </div>
                    );
                  })}
                </div>
                {admin.companies?.length > 0 && (
                  <div className="mt-4 pt-4 border-t border-slate-200">
                    <h4 className="text-sm font-semibold text-slate-700 mb-2">Synced Companies</h4>
                    <div className="flex flex-wrap gap-2">
                      {admin.companies.map((c, i) => (
                        <span key={i} className="px-3 py-1 bg-white border border-slate-200 rounded-full text-xs font-medium text-slate-700">{c}</span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
          );
        })}
        {admins.length === 0 && (
          <div className="bg-white border border-slate-200 rounded-xl p-12 text-center text-slate-500">
            No admin accounts yet. Create one to get started.
          </div>
        )}
      </div>
      </>}

      {/* Create Admin Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" data-testid="create-admin-modal" onClick={e => { if (e.target === e.currentTarget) setShowCreateModal(false); }}>
          <div className="bg-white rounded-2xl p-6 w-full max-w-md mx-4 max-h-[90vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-lg font-semibold text-slate-900">Create New Admin</h3>
              <button onClick={() => setShowCreateModal(false)} className="text-slate-400 hover:text-slate-600"><X size={20} /></button>
            </div>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Email (Login ID)</label>
                <input
                  type="email"
                  value={newAdmin.username}
                  onChange={e => setNewAdmin({ ...newAdmin, username: e.target.value.toLowerCase().trim() })}
                  className="w-full px-4 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#2563EB]"
                  placeholder="e.g. admin@company.com"
                  data-testid="new-admin-username"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Display Name</label>
                <input
                  type="text"
                  value={newAdmin.name}
                  onChange={e => setNewAdmin({ ...newAdmin, name: e.target.value })}
                  className="w-full px-4 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#2563EB]"
                  placeholder="e.g. XYZ Traders"
                  data-testid="new-admin-name"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Password</label>
                <div className="relative">
                  <input
                    type={showPassword ? "text" : "password"}
                    value={newAdmin.password}
                    onChange={e => setNewAdmin({ ...newAdmin, password: e.target.value })}
                    className="w-full px-4 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#2563EB] pr-10"
                    placeholder="Min 4 characters"
                    data-testid="new-admin-password"
                  />
                  <button onClick={() => setShowPassword(!showPassword)} className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400">
                    {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Subscription Period</label>
                <select
                  value={newAdmin.subscription_months}
                  onChange={e => setNewAdmin({ ...newAdmin, subscription_months: parseInt(e.target.value) })}
                  className="w-full px-4 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#2563EB]"
                  data-testid="new-admin-subscription"
                >
                  <option value={1}>1 Month</option>
                  <option value={3}>3 Months</option>
                  <option value={6}>6 Months</option>
                  <option value={12}>12 Months (1 Year)</option>
                  <option value={24}>24 Months (2 Years)</option>
                  <option value={36}>36 Months (3 Years)</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">Subscription Plan *</label>
                <div className="grid grid-cols-3 gap-2">
                  {Object.entries(PLANS).map(([id, plan]) => (
                    <button key={id} onClick={() => setNewAdmin({ ...newAdmin, plan: id })}
                      className={`p-3 border rounded-lg text-left transition-all ${newAdmin.plan === id ? 'border-blue-500 bg-blue-50 ring-1 ring-blue-500' : 'border-slate-200 hover:border-slate-300'}`}
                      data-testid={`new-plan-${id}`}>
                      <p className="text-sm font-bold text-slate-900">{plan.name}</p>
                      <p className="text-xs text-blue-600 font-medium mt-0.5">
                        {newAdmin.billing_cycle === 'annual' ? `Rs.${Math.round(plan.annual / 12).toLocaleString('en-IN')}/mo` : `Rs.${plan.monthly.toLocaleString('en-IN')}/mo`}
                      </p>
                      <div className="text-[10px] text-slate-500 mt-1">
                        {plan.maxCompanies} co. | {plan.maxEmployees} emp | {plan.features.length} features
                      </div>
                    </button>
                  ))}
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Billing Cycle</label>
                <div className="flex gap-2">
                  {['monthly', 'annual'].map(cycle => (
                    <button key={cycle} onClick={() => setNewAdmin({ ...newAdmin, billing_cycle: cycle })}
                      className={`flex-1 py-2 text-sm font-medium rounded-lg border ${newAdmin.billing_cycle === cycle ? 'border-blue-500 bg-blue-50 text-blue-700' : 'border-slate-200 text-slate-600'}`}>
                      {cycle === 'annual' ? 'Annual (Save 17%)' : 'Monthly'}
                    </button>
                  ))}
                </div>
              </div>
              <div className="bg-slate-50 rounded-lg p-3">
                <p className="text-xs font-medium text-slate-500 mb-1">Plan includes:</p>
                <div className="flex flex-wrap gap-1">
                  {(PLANS[newAdmin.plan]?.features || []).map(f => (
                    <span key={f} className="text-[10px] bg-white border border-slate-200 text-slate-700 px-2 py-0.5 rounded">{f.replace('_', ' ')}</span>
                  ))}
                </div>
              </div>
            </div>
            <div className="flex justify-end gap-3 mt-6">
              <button onClick={() => setShowCreateModal(false)} className="px-4 py-2 text-sm border border-slate-200 rounded-lg hover:bg-slate-50">Cancel</button>
              <button onClick={createAdmin} className="px-4 py-2 text-sm bg-[#2563EB] text-white rounded-lg hover:bg-[#1D4ED8]" data-testid="confirm-create-admin">Create Admin</button>
            </div>
          </div>
        </div>
      )}

      {/* Edit Admin Modal */}
      {showEditModal && editAdmin && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" data-testid="edit-admin-modal" onClick={e => { if (e.target === e.currentTarget) { setShowEditModal(null); setEditAdmin(null); } }}>
          <div className="bg-white rounded-2xl p-6 w-full max-w-lg mx-4 max-h-[90vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-lg font-semibold text-slate-900">Edit Admin</h3>
              <button onClick={() => { setShowEditModal(null); setEditAdmin(null); }} className="text-slate-400 hover:text-slate-600"><X size={20} /></button>
            </div>
            <div className="space-y-4">
              <div className="p-3 bg-slate-50 rounded-lg">
                <div className="text-xs text-slate-500">Email (cannot change)</div>
                <div className="font-medium text-slate-800">{editAdmin.username}</div>
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Display Name</label>
                <input
                  type="text"
                  value={editAdmin.name}
                  onChange={e => setEditAdmin({ ...editAdmin, name: e.target.value })}
                  className="w-full px-4 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#2563EB]"
                  data-testid="edit-admin-name"
                />
              </div>

              {/* Plan Selection */}
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">Subscription Plan</label>
                <div className="grid grid-cols-3 gap-2">
                  {Object.entries(PLANS).map(([id, plan]) => (
                    <button key={id} onClick={() => setEditAdmin(prev => ({ ...prev, plan: id, features: [...plan.features] }))}
                      className={`p-3 border rounded-lg text-left transition-all ${editAdmin.plan === id ? 'border-blue-500 bg-blue-50 ring-1 ring-blue-500' : 'border-slate-200 hover:border-slate-300'}`}
                      data-testid={`edit-plan-${id}`}>
                      <p className="text-sm font-bold text-slate-900">{plan.name}</p>
                      <p className="text-xs text-blue-600 font-medium mt-0.5">
                        {editAdmin.billing_cycle === 'annual' ? `Rs.${Math.round(plan.annual / 12).toLocaleString('en-IN')}/mo` : `Rs.${plan.monthly.toLocaleString('en-IN')}/mo`}
                      </p>
                      <div className="text-[10px] text-slate-500 mt-1">
                        {plan.maxCompanies} co. | {plan.maxEmployees} emp | {plan.features.length} feat
                      </div>
                    </button>
                  ))}
                </div>
              </div>

              {/* Billing Cycle */}
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Billing Cycle</label>
                <div className="flex gap-2">
                  {['monthly', 'annual'].map(cycle => (
                    <button key={cycle} onClick={() => setEditAdmin(prev => ({ ...prev, billing_cycle: cycle }))}
                      className={`flex-1 py-2 text-sm font-medium rounded-lg border ${editAdmin.billing_cycle === cycle ? 'border-blue-500 bg-blue-50 text-blue-700' : 'border-slate-200 text-slate-600'}`}>
                      {cycle === 'annual' ? 'Annual (Save 17%)' : 'Monthly'}
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Subscription Period</label>
                <select
                  value={editAdmin.subscription_months}
                  onChange={e => setEditAdmin({ ...editAdmin, subscription_months: parseInt(e.target.value) })}
                  className="w-full px-4 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#2563EB]"
                  data-testid="edit-admin-subscription"
                >
                  <option value={1}>1 Month</option>
                  <option value={3}>3 Months</option>
                  <option value={6}>6 Months</option>
                  <option value={12}>12 Months (1 Year)</option>
                  <option value={24}>24 Months (2 Years)</option>
                  <option value={36}>36 Months (3 Years)</option>
                </select>
              </div>

              {/* Features preview */}
              <div className="bg-slate-50 rounded-lg p-3">
                <p className="text-xs font-medium text-slate-500 mb-1">Included Features ({PLANS[editAdmin.plan]?.features.length || 0}):</p>
                <div className="flex flex-wrap gap-1">
                  {(PLANS[editAdmin.plan]?.features || []).map(f => (
                    <span key={f} className="text-[10px] bg-white border border-slate-200 text-slate-700 px-2 py-0.5 rounded">{f.replace('_', ' ')}</span>
                  ))}
                </div>
              </div>
            </div>
            <div className="flex justify-end gap-3 mt-6">
              <button onClick={() => { setShowEditModal(null); setEditAdmin(null); }} className="px-4 py-2 text-sm border border-slate-200 rounded-lg hover:bg-slate-50">Cancel</button>
              <button onClick={saveEditAdmin} className="px-4 py-2 text-sm bg-[#2563EB] text-white rounded-lg hover:bg-[#1D4ED8]" data-testid="confirm-edit-admin">Save Changes</button>
            </div>
          </div>
        </div>
      )}

      {/* Reset Password Modal */}
      {showResetModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" data-testid="reset-password-modal">
          <div className="bg-white rounded-2xl p-6 w-full max-w-sm mx-4">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-slate-900">Reset Password</h3>
              <button onClick={() => { setShowResetModal(null); setResetPassword(''); }} className="text-slate-400 hover:text-slate-600"><X size={20} /></button>
            </div>
            <p className="text-sm text-slate-500 mb-4">Reset password for <strong>{showResetModal}</strong></p>
            <div className="relative">
              <input
                type={showPassword ? "text" : "password"}
                value={resetPassword}
                onChange={e => setResetPassword(e.target.value)}
                className="w-full px-4 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#2563EB] pr-10"
                placeholder="New password (min 4 chars)"
                data-testid="reset-password-input"
              />
              <button onClick={() => setShowPassword(!showPassword)} className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400">
                {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
            <div className="flex justify-end gap-3 mt-6">
              <button onClick={() => { setShowResetModal(null); setResetPassword(''); }} className="px-4 py-2 text-sm border border-slate-200 rounded-lg hover:bg-slate-50">Cancel</button>
              <button onClick={handleResetPassword} className="px-4 py-2 text-sm bg-[#2563EB] text-white rounded-lg hover:bg-[#1D4ED8]" data-testid="confirm-reset-password">Reset</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default SuperAdminDashboard;
