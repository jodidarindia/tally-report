import React, { useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

/* iter-167: shown right after signing in with a temporary password.
   No sidebar / nav access until the admin picks a strong new password. */
export default function ForceChangePasswordScreen({ user, token, onDone, onLogout }) {
  const [current, setCurrent] = useState('');
  const [newPw, setNewPw] = useState('');
  const [confirm, setConfirm] = useState('');
  const [busy, setBusy] = useState(false);

  const validate = () => {
    if (!current) return 'Enter your temporary password';
    if (!newPw || newPw.length < 8) return 'New password must be at least 8 characters';
    if (!/[A-Z]/.test(newPw) || !/[a-z]/.test(newPw) || !/[0-9]/.test(newPw))
      return 'Use at least one uppercase, one lowercase and one number';
    if (newPw === current) return 'Pick a different password from the temporary one';
    if (newPw !== confirm) return 'New passwords do not match';
    return null;
  };

  const submit = async (e) => {
    e.preventDefault();
    const err = validate();
    if (err) { toast.error(err); return; }
    setBusy(true);
    try {
      const r = await axios.post(
        `${API}/auth/change-password`,
        { current_password: current, new_password: newPw },
        { headers: { Authorization: `Bearer ${token}` } },
      );
      if (r.data?.success) {
        toast.success('Password updated. Signing you in...');
        onDone();
      } else {
        toast.error(r.data?.error || 'Could not change password');
      }
    } catch (err) {
      toast.error(err.response?.data?.error || 'Network error');
    } finally { setBusy(false); }
  };

  return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-6">
          <img src="/flowra-logo.png" alt="FLOWRA" className="h-14 mx-auto mb-2"/>
          <h1 className="text-2xl font-bold text-slate-900">Set your new password</h1>
          <p className="text-sm text-slate-500 mt-1">
            You signed in with a temporary password. Choose a new one to continue.
          </p>
        </div>
        <form onSubmit={submit} className="bg-white rounded-2xl border border-slate-200 p-6 space-y-4" data-testid="force-change-password-form">
          <div className="rounded-md bg-blue-50 border border-blue-200 px-3 py-2 text-[11px] text-blue-800">
            Signed in as <b>{user?.username}</b>. This one-time step is required after a password reset.
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1.5">Temporary password (from email)</label>
            <input type="password" value={current} onChange={e => setCurrent(e.target.value)}
              className="w-full px-4 py-2.5 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#2563EB]"
              autoFocus data-testid="force-change-current"/>
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1.5">New password</label>
            <input type="password" value={newPw} onChange={e => setNewPw(e.target.value)}
              className="w-full px-4 py-2.5 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#2563EB]"
              placeholder="Min 8 chars · 1 upper · 1 lower · 1 digit"
              data-testid="force-change-new"/>
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1.5">Confirm new password</label>
            <input type="password" value={confirm} onChange={e => setConfirm(e.target.value)}
              className="w-full px-4 py-2.5 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#2563EB]"
              data-testid="force-change-confirm"/>
          </div>
          <button type="submit" disabled={busy}
            className="w-full py-2.5 bg-[#2563EB] text-white rounded-lg font-medium hover:bg-[#1D4ED8] disabled:opacity-50 transition-colors"
            data-testid="force-change-submit">
            {busy ? 'Updating…' : 'Update password and continue'}
          </button>
          <button type="button" onClick={onLogout}
            className="w-full text-sm text-slate-500 hover:text-slate-700 py-1"
            data-testid="force-change-logout">
            Sign out
          </button>
        </form>
      </div>
    </div>
  );
}
