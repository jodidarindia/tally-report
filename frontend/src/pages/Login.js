import React, { useState } from 'react';
import axios from 'axios';
import { Lock, Loader, Eye, EyeOff } from 'lucide-react';
import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const Login = ({ onLoginSuccess }) => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);

  const handleLogin = async (e) => {
    e.preventDefault();
    if (!username.trim()) { toast.error('Please enter your User ID'); return; }
    if (!password) { toast.error('Please enter your password'); return; }

    setLoading(true);
    try {
      const response = await axios.post(`${API}/auth/login`, { username, password }, { withCredentials: true });
      if (response.data?.success) {
        const { username: uname, name, role, token } = response.data.data;
        localStorage.setItem('auth_token', token);
        localStorage.setItem('user_data', JSON.stringify({ username: uname, name, role }));
        toast.success(`Welcome, ${name || uname}!`);
        onLoginSuccess({ username: uname, name, role, token });
      } else {
        toast.error(response.data?.error || 'Login failed');
      }
    } catch (error) {
      const msg = error.response?.data?.error || 'Login failed';
      toast.error(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#F0F4FF] flex items-center justify-center p-6" data-testid="login-page">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <img src="/flowra-logo.png" alt="FLOWRA" className="h-20 mx-auto mb-4 object-contain" />
          <p className="text-slate-500 mt-1 text-sm tracking-wide">Organize. Automate. Accelerate.</p>
        </div>

        <div className="bg-white border border-indigo-100 rounded-xl p-8 shadow-lg shadow-blue-100/40">
          <h2 className="text-lg font-semibold text-slate-800 mb-6 text-center" style={{ fontFamily: 'Outfit, sans-serif' }}>Sign in to your account</h2>
          <form onSubmit={handleLogin}>
            <div className="mb-5">
              <label className="block text-sm font-medium text-slate-700 mb-2">User ID</label>
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="Enter your User ID"
                className="w-full px-4 py-3 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-slate-50/50"
                disabled={loading}
                data-testid="username-input"
                autoComplete="username"
              />
            </div>

            <div className="mb-6">
              <label className="block text-sm font-medium text-slate-700 mb-2">Password</label>
              <div className="relative">
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Enter your password"
                  className="w-full px-4 pr-12 py-3 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-slate-50/50"
                  disabled={loading}
                  data-testid="password-input"
                  autoComplete="current-password"
                />
                <button type="button" onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 transform -translate-y-1/2 text-slate-400 hover:text-slate-600" tabIndex={-1}>
                  {showPassword ? <EyeOff size={20} /> : <Eye size={20} />}
                </button>
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full btn-primary py-3 flex items-center justify-center gap-2 disabled:opacity-50 text-base font-medium"
              data-testid="login-button"
            >
              {loading ? (<><Loader className="animate-spin" size={20} />Signing in...</>) : 'Sign In'}
            </button>
          </form>
        </div>

        <p className="text-xs text-slate-400 mt-6 text-center">
          Contact your administrator if you forgot your password
        </p>
      </div>
    </div>
  );
};

export default Login;
