import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import {
  Users, Shield, ToggleLeft, ToggleRight, Trash2, Key,
  Plus, ChevronDown, ChevronUp, RefreshCw, Activity,
  Lock, Eye, EyeOff, X
} from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

const ALL_FEATURES = [
  { id: 'dashboard', label: 'Dashboard', desc: 'Overview stats & charts' },
  { id: 'inventory', label: 'Inventory', desc: 'Stock management & items' },
  { id: 'sales', label: 'Sales', desc: 'Sales vouchers & analytics' },
  { id: 'crm', label: 'CRM', desc: 'Customer outstanding & behavior' },
  { id: 'analytics', label: 'Analytics', desc: 'Movement analysis & reports' },
  { id: 'ai_reports', label: 'AI Reports', desc: 'AI-powered insights' },
  { id: 'salesman', label: 'Salesman', desc: 'Salesman performance' },
  { id: 'sync_history', label: 'Sync History', desc: 'Data sync logs' },
  { id: 'setup', label: 'Setup', desc: 'Tally connection settings' },
];

const SuperAdminDashboard = ({ token }) => {
  const [stats, setStats] = useState(null);
  const [admins, setAdmins] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showResetModal, setShowResetModal] = useState(null);
  const [expandedAdmin, setExpandedAdmin] = useState(null);
  const [newAdmin, setNewAdmin] = useState({ username: '', password: '', name: '', features: [] });
  const [resetPassword, setResetPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);

  const headers = token ? { Authorization: `Bearer ${token}` } : {};

  const fetchData = useCallback(async () => {
    try {
      setLoading(true);
      const [statsRes, adminsRes] = await Promise.all([
        axios.get(`${API}/super-admin/stats`, { headers }),
        axios.get(`${API}/super-admin/admins`, { headers })
      ]);
      setStats(statsRes.data?.data);
      setAdmins(adminsRes.data?.data?.admins || []);
    } catch (err) {
      toast.error('Failed to fetch data');
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const createAdmin = async () => {
    if (!newAdmin.username || !newAdmin.password) {
      toast.error('Username and password are required');
      return;
    }
    try {
      const res = await axios.post(`${API}/super-admin/admins`, newAdmin, { headers });
      if (res.data?.success) {
        toast.success(`Admin '${newAdmin.username}' created`);
        setShowCreateModal(false);
        setNewAdmin({ username: '', password: '', name: '', features: [] });
        fetchData();
      } else {
        toast.error(res.data?.error || 'Failed to create admin');
      }
    } catch (err) {
      toast.error('Failed to create admin');
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
        setAdmins(prev => prev.map(a =>
          a.username === username ? { ...a, active: res.data.data.active } : a
        ));
        toast.success(res.data.message);
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
        {admins.map((admin) => (
          <div key={admin.username} className="bg-white border border-slate-200 rounded-xl overflow-hidden" data-testid={`admin-card-${admin.username}`}>
            {/* Admin Header */}
            <div className="p-5 flex items-center justify-between">
              <div className="flex items-center gap-4">
                <div className={`w-3 h-3 rounded-full ${admin.active ? 'bg-green-500' : 'bg-red-400'}`} />
                <div>
                  <div className="font-semibold text-slate-900">{admin.name || admin.username}</div>
                  <div className="text-xs text-slate-500">@{admin.username} &middot; Tenant: {admin.tenant_id} &middot; {admin.employee_count || 0} employees</div>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-xs px-2.5 py-1 rounded-full bg-blue-50 text-blue-700 font-medium">
                  {admin.features?.length || 0}/{ALL_FEATURES.length} features
                </span>
                <button onClick={() => toggleActive(admin.username)} className={`px-3 py-1.5 text-xs rounded-lg font-medium flex items-center gap-1 ${admin.active ? 'bg-green-50 text-green-700 hover:bg-green-100' : 'bg-red-50 text-red-700 hover:bg-red-100'}`} data-testid={`toggle-active-${admin.username}`}>
                  {admin.active ? <ToggleRight size={14} /> : <ToggleLeft size={14} />}
                  {admin.active ? 'Active' : 'Inactive'}
                </button>
                <button onClick={() => setShowResetModal(admin.username)} className="p-1.5 text-slate-400 hover:text-blue-600 hover:bg-blue-50 rounded-lg" title="Reset Password" data-testid={`reset-pwd-${admin.username}`}>
                  <Key size={14} />
                </button>
                <button onClick={() => deleteAdmin(admin.username)} className="p-1.5 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded-lg" title="Delete Admin" data-testid={`delete-admin-${admin.username}`}>
                  <Trash2 size={14} />
                </button>
                <button onClick={() => setExpandedAdmin(expandedAdmin === admin.username ? null : admin.username)} className="p-1.5 text-slate-400 hover:text-slate-600 rounded-lg" data-testid={`expand-admin-${admin.username}`}>
                  {expandedAdmin === admin.username ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                </button>
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
        ))}
        {admins.length === 0 && (
          <div className="bg-white border border-slate-200 rounded-xl p-12 text-center text-slate-500">
            No admin accounts yet. Create one to get started.
          </div>
        )}
      </div>

      {/* Create Admin Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" data-testid="create-admin-modal">
          <div className="bg-white rounded-2xl p-6 w-full max-w-md mx-4">
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-lg font-semibold text-slate-900">Create New Admin</h3>
              <button onClick={() => setShowCreateModal(false)} className="text-slate-400 hover:text-slate-600"><X size={20} /></button>
            </div>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Username</label>
                <input
                  type="text"
                  value={newAdmin.username}
                  onChange={e => setNewAdmin({ ...newAdmin, username: e.target.value })}
                  className="w-full px-4 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#2563EB]"
                  placeholder="e.g. company_xyz"
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
                <label className="block text-sm font-medium text-slate-700 mb-2">Features to Activate</label>
                <div className="grid grid-cols-2 gap-2">
                  {ALL_FEATURES.map(f => (
                    <label key={f.id} className="flex items-center gap-2 text-sm cursor-pointer">
                      <input
                        type="checkbox"
                        checked={newAdmin.features.includes(f.id)}
                        onChange={() => {
                          setNewAdmin(prev => ({
                            ...prev,
                            features: prev.features.includes(f.id)
                              ? prev.features.filter(x => x !== f.id)
                              : [...prev.features, f.id]
                          }));
                        }}
                        className="rounded border-slate-300"
                      />
                      {f.label}
                    </label>
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
