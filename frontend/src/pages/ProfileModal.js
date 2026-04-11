import React, { useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { X, Eye, EyeOff, User, Lock, Key, CreditCard, Calendar, Shield, AlertTriangle } from 'lucide-react';

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

  const headers = token ? { Authorization: `Bearer ${token}` } : {};

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

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" data-testid="profile-modal" onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="bg-white rounded-2xl w-full max-w-lg mx-4 overflow-hidden max-h-[90vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between p-5 border-b border-slate-100">
          <h3 className="text-lg font-semibold text-slate-900">Profile & Security</h3>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600" data-testid="profile-modal-close"><X size={20} /></button>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-slate-100 overflow-x-auto">
          <button onClick={() => setActiveTab('profile')}
            className={`px-5 py-3 text-sm font-medium border-b-2 whitespace-nowrap ${activeTab === 'profile' ? 'border-[#2563EB] text-[#2563EB]' : 'border-transparent text-slate-500 hover:text-slate-700'}`}>
            <User size={14} className="inline mr-1.5" />Profile
          </button>
          <button onClick={() => setActiveTab('password')}
            className={`px-5 py-3 text-sm font-medium border-b-2 whitespace-nowrap ${activeTab === 'password' ? 'border-[#2563EB] text-[#2563EB]' : 'border-transparent text-slate-500 hover:text-slate-700'}`}>
            <Lock size={14} className="inline mr-1.5" />Change Password
          </button>
          {user?.role === 'admin' && (
            <button onClick={() => setActiveTab('reset')}
              className={`px-5 py-3 text-sm font-medium border-b-2 whitespace-nowrap ${activeTab === 'reset' ? 'border-[#2563EB] text-[#2563EB]' : 'border-transparent text-slate-500 hover:text-slate-700'}`}>
              <Key size={14} className="inline mr-1.5" />Reset Employee
            </button>
          )}
          {user?.role === 'admin' && (
            <button onClick={() => setActiveTab('subscription')}
              className={`px-5 py-3 text-sm font-medium border-b-2 whitespace-nowrap ${activeTab === 'subscription' ? 'border-[#2563EB] text-[#2563EB]' : 'border-transparent text-slate-500 hover:text-slate-700'}`}
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
                  <div className="text-xs text-slate-500">Tenant ID</div>
                  <div className="font-medium text-slate-800 text-xs">{user?.tenant_id || 'N/A'}</div>
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
            </div>
          )}

          {activeTab === 'reset' && user?.role === 'admin' && (
            <div className="space-y-4">
              <p className="text-sm text-slate-500">Reset password for any employee in your organization.</p>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Employee Username</label>
                <input type="text" value={resetUsername} onChange={e => setResetUsername(e.target.value)}
                  className="w-full px-4 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#2563EB]" placeholder="Enter employee username" data-testid="reset-emp-username" />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">New Password</label>
                <input type={showPasswords ? "text" : "password"} value={resetNewPassword} onChange={e => setResetNewPassword(e.target.value)}
                  className="w-full px-4 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#2563EB]" placeholder="Min 4 characters" data-testid="reset-emp-password" />
              </div>
              <button onClick={handleResetEmployee} disabled={loading}
                className="w-full py-2.5 bg-[#2563EB] text-white rounded-lg hover:bg-[#1D4ED8] disabled:opacity-50 font-medium text-sm" data-testid="confirm-reset-emp-btn">
                {loading ? 'Resetting...' : 'Reset Employee Password'}
              </button>
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
                    <p className="text-lg font-bold text-slate-900">{user.max_employees || 20}</p>
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
