import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { X, Eye, EyeOff, User, Lock, Key, CreditCard, Calendar, Shield, AlertTriangle, Users, Plus, Trash2, Mail } from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

const formatIST = (isoStr) => {
  if (!isoStr) return 'N/A';
  try {
    const d = new Date(isoStr);
    return d.toLocaleDateString('en-IN', { day: 'numeric', month: 'long', year: 'numeric', timeZone: 'Asia/Kolkata' });
  } catch { return 'N/A'; }
};

const ProfileModal = ({ user, token, onClose }) => {
  const [activeTab, setActiveTab] = useState('profile');
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPasswords, setShowPasswords] = useState(false);
  const [loading, setLoading] = useState(false);
  const [resetUsername, setResetUsername] = useState('');
  const [resetNewPassword, setResetNewPassword] = useState('');
  const [renewalMessage, setRenewalMessage] = useState('');
  // Employee management
  const [employees, setEmployees] = useState([]);
  const [empLoading, setEmpLoading] = useState(false);
  const [newEmpEmail, setNewEmpEmail] = useState('');
  const [newEmpName, setNewEmpName] = useState('');
  const [newEmpPassword, setNewEmpPassword] = useState('');
  const [newEmpRole, setNewEmpRole] = useState('employee');

  const headers = token ? { Authorization: `Bearer ${token}` } : {};

  const fetchEmployees = async () => {
    setEmpLoading(true);
    try {
      const res = await axios.get(`${API}/auth/users`, { headers });
      if (res.data?.success) {
        setEmployees((res.data.data?.users || []).filter(u => u.role === 'employee' || u.role === 'dispatch' || u.role === 'salesman'));
      }
    } catch {}
    finally { setEmpLoading(false); }
  };

  useEffect(() => {
    if (activeTab === 'employees' && user?.role === 'admin') {
      fetchEmployees();
    }
  }, [activeTab]);

  const handleAddEmployee = async () => {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!newEmpEmail || !emailRegex.test(newEmpEmail)) {
      toast.error('Please enter a valid email address');
      return;
    }
    if (!newEmpName.trim()) { toast.error('Employee name is required'); return; }
    if (!newEmpPassword || newEmpPassword.length < 4) { toast.error('Password must be at least 4 characters'); return; }

    setLoading(true);
    try {
      const res = await axios.post(`${API}/auth/users`, {
        username: newEmpEmail.toLowerCase().trim(),
        password: newEmpPassword,
        name: newEmpName.trim(),
        role: newEmpRole
      }, { headers });
      if (res.data?.success) {
        toast.success(`Employee '${newEmpName.trim()}' added successfully`);
        setNewEmpEmail('');
        setNewEmpName('');
        setNewEmpPassword('');
        fetchEmployees();
      } else {
        toast.error(res.data?.error || 'Failed to add employee');
      }
    } catch (err) {
      toast.error(err.response?.data?.error || 'Failed to add employee');
    }
    finally { setLoading(false); }
  };

  const handleDeleteEmployee = async (username) => {
    if (!window.confirm(`Remove employee '${username}'? This action cannot be undone.`)) return;
    try {
      const res = await axios.delete(`${API}/auth/users/${username}`, { headers });
      if (res.data?.success) {
        toast.success('Employee removed');
        fetchEmployees();
      } else { toast.error(res.data?.error || 'Failed to remove'); }
    } catch { toast.error('Failed to remove employee'); }
  };

  const handleChangePassword = async () => {
    if (!currentPassword || !newPassword) { toast.error('All fields are required'); return; }
    if (newPassword.length < 4) { toast.error('New password must be at least 4 characters'); return; }
    if (newPassword !== confirmPassword) { toast.error('Passwords do not match'); return; }
    setLoading(true);
    try {
      const res = await axios.post(`${API}/auth/change-password`, { current_password: currentPassword, new_password: newPassword }, { headers });
      if (res.data?.success) {
        toast.success('Password changed successfully');
        setCurrentPassword(''); setNewPassword(''); setConfirmPassword('');
      } else { toast.error(res.data?.error || 'Failed to change password'); }
    } catch { toast.error('Failed to change password'); }
    finally { setLoading(false); }
  };

  const handleResetEmployee = async () => {
    if (!resetUsername || !resetNewPassword || resetNewPassword.length < 4) {
      toast.error('Username and new password (min 4 chars) are required'); return;
    }
    setLoading(true);
    try {
      const res = await axios.post(`${API}/auth/reset-password`, { username: resetUsername, new_password: resetNewPassword }, { headers });
      if (res.data?.success) {
        toast.success(res.data.message);
        setResetUsername(''); setResetNewPassword('');
      } else { toast.error(res.data?.error || 'Failed to reset password'); }
    } catch { toast.error('Failed to reset password'); }
    finally { setLoading(false); }
  };

  const handleRequestRenewal = async () => {
    setLoading(true);
    try {
      const res = await axios.post(`${API}/auth/request-renewal`, {
        plan_interest: user?.plan || '',
        message: renewalMessage
      }, { headers });
      if (res.data?.success) {
        toast.success(res.data.message);
        setRenewalMessage('');
      } else { toast.error(res.data?.error || 'Failed to submit renewal request'); }
    } catch { toast.error('Failed to submit renewal request'); }
    finally { setLoading(false); }
  };

  // Subscription calculations
  const subStart = user?.subscription_start;
  const subMonths = user?.subscription_months || 12;
  const subExpires = user?.subscription_expires;
  const daysLeft = user?.subscription_days_left ?? 999;
  const isExpired = daysLeft < 0;
  const isNearExpiry = daysLeft >= 0 && daysLeft <= 30;
  const maxEmployees = user?.max_employees || 20;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" data-testid="profile-modal" onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="bg-white rounded-2xl w-full max-w-lg mx-4 overflow-hidden max-h-[90vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between p-5 border-b border-slate-100">
          <h3 className="text-lg font-semibold text-slate-900">Profile & Settings</h3>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600" data-testid="profile-modal-close"><X size={20} /></button>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-slate-100 overflow-x-auto">
          <button onClick={() => setActiveTab('profile')}
            className={`px-4 py-3 text-sm font-medium border-b-2 whitespace-nowrap ${activeTab === 'profile' ? 'border-[#2563EB] text-[#2563EB]' : 'border-transparent text-slate-500 hover:text-slate-700'}`}>
            <User size={14} className="inline mr-1.5" />Profile
          </button>
          <button onClick={() => setActiveTab('password')}
            className={`px-4 py-3 text-sm font-medium border-b-2 whitespace-nowrap ${activeTab === 'password' ? 'border-[#2563EB] text-[#2563EB]' : 'border-transparent text-slate-500 hover:text-slate-700'}`}>
            <Lock size={14} className="inline mr-1.5" />Password
          </button>
          {user?.role === 'admin' && (
            <button onClick={() => setActiveTab('employees')}
              className={`px-4 py-3 text-sm font-medium border-b-2 whitespace-nowrap ${activeTab === 'employees' ? 'border-[#2563EB] text-[#2563EB]' : 'border-transparent text-slate-500 hover:text-slate-700'}`}
              data-testid="profile-tab-employees">
              <Users size={14} className="inline mr-1.5" />Employees
            </button>
          )}
          {user?.role === 'admin' && (
            <button onClick={() => setActiveTab('subscription')}
              className={`px-4 py-3 text-sm font-medium border-b-2 whitespace-nowrap ${activeTab === 'subscription' ? 'border-[#2563EB] text-[#2563EB]' : 'border-transparent text-slate-500 hover:text-slate-700'}`}
              data-testid="profile-tab-subscription">
              <CreditCard size={14} className="inline mr-1.5" />Subscription
            </button>
          )}
        </div>

        <div className="p-6">
          {activeTab === 'profile' && (
            <div className="space-y-4">
              <div className="flex items-center gap-4 p-4 bg-slate-50 rounded-xl">
                <div className="w-12 h-12 rounded-full bg-[#2563EB] text-white flex items-center justify-center text-lg font-bold">
                  {(user?.name || user?.username || 'U')[0].toUpperCase()}
                </div>
                <div>
                  <div className="font-semibold text-slate-900">{user?.name || user?.username}</div>
                  <div className="text-sm text-slate-500">@{user?.username}</div>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="p-3 bg-slate-50 rounded-lg">
                  <div className="text-xs text-slate-500">Role</div>
                  <div className="font-medium text-slate-800 capitalize">{user?.role?.replace('_', ' ')}</div>
                </div>
                <div className="p-3 bg-slate-50 rounded-lg">
                  <div className="text-xs text-slate-500">Plan</div>
                  <div className="font-medium text-slate-800 capitalize">{user?.plan || 'Enterprise'}</div>
                </div>
              </div>
              {user?.features && user.features.length > 0 && (
                <div>
                  <div className="text-xs text-slate-500 mb-2">Active Features</div>
                  <div className="flex flex-wrap gap-1.5">
                    {user.features.map(f => (
                      <span key={f} className="px-2.5 py-1 bg-green-50 text-green-700 rounded-full text-xs font-medium capitalize">{f.replace('_', ' ')}</span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {activeTab === 'password' && (
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Current Password</label>
                <div className="relative">
                  <input type={showPasswords ? "text" : "password"} value={currentPassword} onChange={e => setCurrentPassword(e.target.value)}
                    className="w-full px-4 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#2563EB] pr-10" data-testid="current-password-input" />
                  <button onClick={() => setShowPasswords(!showPasswords)} className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400">
                    {showPasswords ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">New Password</label>
                <input type={showPasswords ? "text" : "password"} value={newPassword} onChange={e => setNewPassword(e.target.value)}
                  className="w-full px-4 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#2563EB]" placeholder="Min 4 characters" data-testid="new-password-input" />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Confirm New Password</label>
                <input type={showPasswords ? "text" : "password"} value={confirmPassword} onChange={e => setConfirmPassword(e.target.value)}
                  className="w-full px-4 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#2563EB]" data-testid="confirm-password-input" />
              </div>
              <button onClick={handleChangePassword} disabled={loading}
                className="w-full py-2.5 bg-[#2563EB] text-white rounded-lg hover:bg-[#1D4ED8] disabled:opacity-50 font-medium text-sm" data-testid="save-password-btn">
                {loading ? 'Saving...' : 'Change Password'}
              </button>

              {/* Reset Employee Password (inline) */}
              {user?.role === 'admin' && (
                <div className="mt-6 pt-4 border-t border-slate-100">
                  <p className="text-xs font-semibold text-slate-600 mb-3 flex items-center gap-1.5"><Key size={12} /> Reset Employee Password</p>
                  <div className="space-y-3">
                    <input type="text" value={resetUsername} onChange={e => setResetUsername(e.target.value)}
                      className="w-full px-4 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#2563EB] text-sm" placeholder="Employee email" data-testid="reset-emp-username" />
                    <input type={showPasswords ? "text" : "password"} value={resetNewPassword} onChange={e => setResetNewPassword(e.target.value)}
                      className="w-full px-4 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#2563EB] text-sm" placeholder="New password (min 4 chars)" data-testid="reset-emp-password" />
                    <button onClick={handleResetEmployee} disabled={loading}
                      className="w-full py-2 bg-slate-800 text-white rounded-lg hover:bg-slate-700 disabled:opacity-50 font-medium text-sm" data-testid="confirm-reset-emp-btn">
                      {loading ? 'Resetting...' : 'Reset Password'}
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}

          {activeTab === 'employees' && user?.role === 'admin' && (
            <div className="space-y-4" data-testid="employee-management-section">
              {/* Employee limit info */}
              <div className="flex items-center justify-between bg-slate-50 rounded-lg p-3">
                <span className="text-sm text-slate-600">
                  Employees: <strong>{employees.length}</strong> / {maxEmployees}
                </span>
                <span className={`text-xs font-medium px-2 py-1 rounded-full ${employees.length >= maxEmployees ? 'bg-red-100 text-red-700' : 'bg-green-100 text-green-700'}`}>
                  {employees.length >= maxEmployees ? 'Limit reached' : `${maxEmployees - employees.length} slots available`}
                </span>
              </div>

              {/* Add Employee Form */}
              {employees.length < maxEmployees && (
                <div className="bg-blue-50 border border-blue-100 rounded-xl p-4">
                  <p className="text-sm font-medium text-blue-800 mb-3 flex items-center gap-1.5"><Plus size={14} /> Add Employee</p>
                  <div className="space-y-2">
                    <input type="text" value={newEmpName} onChange={e => setNewEmpName(e.target.value)}
                      placeholder="Employee full name" data-testid="emp-name-input"
                      className="w-full px-3 py-2 border border-blue-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-400 bg-white" />
                    <input type="email" value={newEmpEmail} onChange={e => setNewEmpEmail(e.target.value)}
                      placeholder="Employee email (will be their login ID)" data-testid="emp-email-input"
                      className="w-full px-3 py-2 border border-blue-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-400 bg-white" />
                    <input type="password" value={newEmpPassword} onChange={e => setNewEmpPassword(e.target.value)}
                      placeholder="Set password (min 4 characters)" data-testid="emp-password-input"
                      className="w-full px-3 py-2 border border-blue-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-400 bg-white" />
                    <select value={newEmpRole} onChange={e => setNewEmpRole(e.target.value)} data-testid="emp-role-select"
                      className="w-full px-3 py-2 border border-blue-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-400 bg-white">
                      <option value="employee">Employee (Full Access)</option>
                      <option value="dispatch">Dispatch (Terminal Only)</option>
                      <option value="salesman">Salesman (Orders Only)</option>
                    </select>
                    <button onClick={handleAddEmployee} disabled={loading}
                      className="w-full py-2 bg-[#2563EB] text-white rounded-lg text-sm font-medium hover:bg-[#1D4ED8] disabled:opacity-50"
                      data-testid="add-employee-btn">
                      {loading ? 'Adding...' : 'Add Employee'}
                    </button>
                  </div>
                </div>
              )}

              {/* Employee List */}
              {empLoading ? (
                <div className="text-center py-6 text-slate-400 text-sm">Loading employees...</div>
              ) : employees.length === 0 ? (
                <div className="text-center py-8 bg-white border border-slate-200 rounded-xl">
                  <Users size={24} className="mx-auto text-slate-300 mb-2" />
                  <p className="text-slate-500 text-sm">No employees added yet</p>
                  <p className="text-slate-400 text-xs mt-1">Add your team members above</p>
                </div>
              ) : (
                <div className="space-y-2">
                  {employees.map(emp => (
                    <div key={emp.username} className="flex items-center justify-between bg-white border border-slate-200 rounded-lg p-3">
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-full bg-slate-100 text-slate-600 flex items-center justify-center text-xs font-bold">
                          {(emp.name || emp.username || 'E')[0].toUpperCase()}
                        </div>
                        <div>
                          <p className="text-sm font-medium text-slate-900">{emp.name || emp.username}</p>
                          <p className="text-xs text-slate-500 flex items-center gap-1"><Mail size={10} /> {emp.username}</p>
                        </div>
                        {emp.role === 'dispatch' && <span className="text-[9px] bg-amber-100 text-amber-700 px-1.5 py-0.5 rounded-full font-semibold ml-1">DISPATCH</span>}
                        {emp.role === 'salesman' && <span className="text-[9px] bg-green-100 text-green-700 px-1.5 py-0.5 rounded-full font-semibold ml-1">SALESMAN</span>}
                      </div>
                      <button onClick={() => handleDeleteEmployee(emp.username)}
                        className="text-red-400 hover:text-red-600 p-1.5 hover:bg-red-50 rounded-lg"
                        data-testid={`delete-emp-${emp.username}`}>
                        <Trash2 size={14} />
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {activeTab === 'subscription' && user?.role === 'admin' && (
            <div className="space-y-4" data-testid="subscription-section">
              {/* Expiry Warning */}
              {(isExpired || isNearExpiry) && (
                <div className={`p-4 rounded-xl flex items-start gap-3 ${isExpired ? 'bg-red-50 border border-red-200' : 'bg-amber-50 border border-amber-200'}`}
                  data-testid="subscription-warning">
                  <AlertTriangle size={18} className={isExpired ? 'text-red-600 mt-0.5' : 'text-amber-600 mt-0.5'} />
                  <div>
                    <p className={`text-sm font-semibold ${isExpired ? 'text-red-900' : 'text-amber-900'}`}>
                      {isExpired ? 'Subscription Expired' : `Subscription expires in ${daysLeft} days`}
                    </p>
                    <p className={`text-xs ${isExpired ? 'text-red-700' : 'text-amber-700'}`}>
                      {isExpired ? 'Your sync and access will be disabled. Please renew immediately.' : 'Renew now to avoid any service interruption.'}
                    </p>
                  </div>
                </div>
              )}

              {/* Plan Card */}
              <div className={`p-5 rounded-xl border-2 ${
                user.plan === 'enterprise' ? 'border-purple-200 bg-purple-50/50' :
                user.plan === 'professional' ? 'border-blue-200 bg-blue-50/50' :
                'border-slate-200 bg-slate-50'
              }`}>
                <div className="flex items-center justify-between mb-3">
                  <span className={`text-xs font-bold uppercase tracking-wider px-2.5 py-1 rounded-full ${
                    user.plan === 'enterprise' ? 'bg-purple-100 text-purple-700' :
                    user.plan === 'professional' ? 'bg-blue-100 text-blue-700' :
                    'bg-slate-200 text-slate-700'
                  }`}>{(user.plan || 'enterprise').toUpperCase()} PLAN</span>
                  <Shield size={20} className="text-green-500" />
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div className="bg-white rounded-lg p-3">
                    <p className="text-[10px] text-slate-500 uppercase font-medium">Max Companies</p>
                    <p className="text-lg font-bold text-slate-900">{user.max_companies || 10}</p>
                  </div>
                  <div className="bg-white rounded-lg p-3">
                    <p className="text-[10px] text-slate-500 uppercase font-medium">Max Employees</p>
                    <p className="text-lg font-bold text-slate-900">{maxEmployees}</p>
                  </div>
                </div>
              </div>

              {/* Subscription Details */}
              <div className="space-y-3">
                <h4 className="text-sm font-semibold text-slate-800">Subscription Details</h4>
                {[
                  { label: 'Start Date', value: formatIST(subStart) },
                  { label: 'Validity', value: `${subMonths} months` },
                  { label: 'Active Features', value: `${(user.features || []).length} features enabled` },
                ].map(({ label, value }) => (
                  <div key={label} className="flex items-center justify-between py-2.5 px-3 bg-slate-50 rounded-lg">
                    <span className="text-sm text-slate-600"><Calendar size={14} className="inline mr-2 text-slate-400" />{label}</span>
                    <span className="text-sm font-medium text-slate-900">{value}</span>
                  </div>
                ))}
                <div className="flex items-center justify-between py-2.5 px-3 bg-slate-50 rounded-lg">
                  <span className="text-sm text-slate-600"><Calendar size={14} className="inline mr-2 text-slate-400" />Expires On</span>
                  <span className={`text-sm font-medium ${isExpired ? 'text-red-600' : daysLeft <= 30 ? 'text-amber-600' : 'text-green-600'}`}>
                    {formatIST(subExpires)} {subExpires ? (isExpired ? '(Expired)' : `(${daysLeft} days left)`) : ''}
                  </span>
                </div>
              </div>

              {/* Renewal Section */}
              <div className="bg-blue-50 border border-blue-100 rounded-xl p-4">
                <p className="text-sm text-blue-800 mb-2 font-medium">Need to renew or upgrade?</p>
                <textarea
                  value={renewalMessage}
                  onChange={e => setRenewalMessage(e.target.value)}
                  rows={2}
                  className="w-full px-3 py-2 border border-blue-200 rounded-lg text-sm mb-3 focus:outline-none focus:ring-2 focus:ring-blue-400 bg-white resize-none"
                  placeholder="Add a message (optional)..."
                  data-testid="renewal-message"
                />
                <button
                  className="w-full bg-[#2563EB] text-white px-6 py-2 rounded-lg text-sm font-medium hover:bg-[#1D4ED8] disabled:opacity-50"
                  data-testid="renewal-btn"
                  disabled={loading}
                  onClick={handleRequestRenewal}>
                  {loading ? 'Submitting...' : 'Request Renewal'}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default ProfileModal;
