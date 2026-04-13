import React, { useState } from 'react';

const LoginPage = ({ onLogin, loading, onNavigate }) => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');

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
            <label className="block text-sm font-medium text-slate-700 mb-1.5">Password</label>
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
        <p className="text-center text-xs text-slate-400 mt-6">FLOWRA by Jodidar India</p>
        <p className="text-center text-[9px] text-slate-400 mt-2 max-w-lg mx-auto leading-relaxed">Tally* is the trademark of its respective owner and is not affiliated, endorsed, connected or sponsored in any way to this website, mobile application or any of our affiliate sites.</p>
      </div>
    </div>
  );
};

export default LoginPage;
