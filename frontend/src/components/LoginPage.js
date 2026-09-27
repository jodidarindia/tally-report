import React, { useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

const LoginPage = ({ onLogin, loading, onNavigate }) => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showForgot, setShowForgot] = useState(false);

  const handleSubmit = (e) => {
    e.preventDefault();
    onLogin(username, password);
  };

  return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center">
      <div className="w-full max-w-md p-8">
        <div className="text-center mb-8">
          <img src="/flowra-logo.png" alt="FLOWRA" className="h-16 mx-auto mb-3" data-testid="login-logo" />
          <h1 className="text-3xl font-bold text-slate-900 tracking-tight">FLOWRA</h1>
          <p className="text-slate-500 mt-1 text-sm">Organize. Automate. Accelerate.</p>
        </div>
        <form onSubmit={handleSubmit} className="bg-white rounded-2xl border border-slate-200 p-8 space-y-5">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1.5">Email</label>
            <input
              type="text" value={username} onChange={e => setUsername(e.target.value)}
              className="w-full px-4 py-2.5 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#2563EB]"
              placeholder="Enter your email"
              data-testid="username-input"
            />
          </div>
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label className="block text-sm font-medium text-slate-700">Password</label>
              <button
                type="button"
                onClick={() => setShowForgot(true)}
                className="text-xs font-medium text-[#2563EB] hover:underline"
                data-testid="forgot-password-link"
              >
                Forgot password?
              </button>
            </div>
            <input
              type="password" value={password} onChange={e => setPassword(e.target.value)}
              className="w-full px-4 py-2.5 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#2563EB]"
              placeholder="Enter your password"
              data-testid="password-input"
            />
          </div>
          <button
            type="submit" disabled={loading}
            className="w-full py-2.5 bg-[#2563EB] text-white rounded-lg font-medium hover:bg-[#1D4ED8] disabled:opacity-50 transition-colors"
            data-testid="login-button"
          >
            {loading ? 'Signing in...' : 'Sign In'}
          </button>
          <p className="text-[10px] text-slate-400 text-center mt-1">Protected by reCAPTCHA</p>
        </form>
        <div className="flex items-center justify-between mt-4">
          <button onClick={() => onNavigate('landing')} className="text-sm text-[#2563EB] hover:underline" data-testid="back-to-home">Back to Home</button>
          <button onClick={() => onNavigate('signup')} className="text-sm text-[#2563EB] hover:underline" data-testid="go-to-signup">New Customer? Sign Up</button>
        </div>
        <p className="text-center text-xs text-slate-400 mt-6">&copy; {new Date().getFullYear()} JODIDAR INDIA. FLOWRA is a brand owned by JODIDAR INDIA.</p>
        <p className="text-center text-[9px] text-slate-400 mt-2 max-w-lg mx-auto leading-relaxed" data-testid="tally-disclaimer">Tally* and Busy* are trademarks of their respective owners and are not affiliated, endorsed, connected or sponsored in any way to this website, mobile application or any of our affiliate sites. The same are used in accordance with honest practices and not used with any intention to misguide customers to take unfair advantage of the trademarks' distinct character or harm the holders' reputation.</p>
      </div>
      {showForgot && <ForgotPasswordModal onClose={() => setShowForgot(false)} />}
    </div>
  );
};

/* iter-167: Forgot-password modal — Business Admin only. */
function ForgotPasswordModal({ onClose }) {
  const [email, setEmail] = useState('');
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    if (!email.trim() || !email.includes('@')) {
      toast.error('Enter a valid email address');
      return;
    }
    setBusy(true);
    try {
      const r = await axios.post(`${API}/auth/forgot-password`, { username: email.trim().toLowerCase() });
      if (r.data?.success) {
        setDone(true);
      } else {
        toast.error(r.data?.error || 'Could not process request');
      }
    } catch (err) {
      toast.error(err.response?.data?.error || 'Network error. Please try again.');
    } finally { setBusy(false); }
  };

  return (
    <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm flex items-center justify-center z-50 p-4" data-testid="forgot-password-modal">
      <div className="bg-white rounded-2xl border border-slate-200 w-full max-w-md shadow-2xl">
        <div className="p-6 border-b border-slate-100">
          <h2 className="text-lg font-bold text-slate-900">Forgot Password</h2>
          <div className="mt-2 rounded-md bg-amber-50 border border-amber-200 px-3 py-2 text-[11px] text-amber-800" data-testid="forgot-password-disclaimer">
            <span className="font-semibold">⚠ Disclaimer:</span> Reset password facility only for Business Admin. Employees, dispatch, salesman and super admin accounts cannot be reset from this link — please ask your Business Admin.
          </div>
        </div>
        {done ? (
          <div className="p-6 space-y-4">
            <div className="rounded-lg bg-green-50 border border-green-200 p-4 text-sm text-green-800" data-testid="forgot-password-success">
              If this is a Business Admin account, a temporary password has been emailed to <b>{email}</b>. Check your inbox (and Spam folder). You'll be asked to set a new password immediately on your next sign-in.
            </div>
            <button
              onClick={onClose}
              className="w-full py-2.5 bg-[#2563EB] text-white rounded-lg font-medium hover:bg-[#1D4ED8] transition-colors"
              data-testid="forgot-password-close"
            >
              Back to Sign In
            </button>
          </div>
        ) : (
          <form onSubmit={submit} className="p-6 space-y-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1.5">Business Admin email</label>
              <input
                type="email"
                value={email}
                onChange={e => setEmail(e.target.value)}
                autoFocus
                placeholder="you@company.com"
                className="w-full px-4 py-2.5 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#2563EB]"
                data-testid="forgot-password-email"
              />
            </div>
            <div className="flex gap-2">
              <button
                type="button" onClick={onClose}
                className="flex-1 py-2.5 border border-slate-200 rounded-lg text-slate-700 font-medium hover:bg-slate-50"
                data-testid="forgot-password-cancel"
              >
                Cancel
              </button>
              <button
                type="submit" disabled={busy}
                className="flex-1 py-2.5 bg-[#2563EB] text-white rounded-lg font-medium hover:bg-[#1D4ED8] disabled:opacity-50 transition-colors"
                data-testid="forgot-password-submit"
              >
                {busy ? 'Sending…' : 'Send Temporary Password'}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}

export default LoginPage;
