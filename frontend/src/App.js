import React, { useState, useEffect, useCallback } from 'react';
import { BrowserRouter, Routes, Route, Link, useLocation } from 'react-router-dom';
import axios from 'axios';
import { BarChart3, Package, TrendingUp, Bot, Settings, Menu, X, Users, Activity, Zap, LogOut, KeyRound, UserPlus, ChevronDown } from 'lucide-react';
import { toast } from 'sonner';
import '@/App.css';
import '@/index.css';

import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import Inventory from './pages/Inventory';
import Sales from './pages/Sales';
import AIQueryBuilder from './pages/AIQueryBuilder';
import ReportHistory from './pages/ReportHistory';
import TallySetup from './pages/TallySetup';
import CustomerCRM from './pages/CustomerCRM';
import EnhancedAIReports from './pages/EnhancedAIReports';
import InventoryAnalytics from './pages/InventoryAnalytics';
import SalesmanPerformance from './pages/SalesmanPerformance';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

// Generate FY options (current + last 4 years)
const generateFYOptions = () => {
  const now = new Date();
  const currentYear = now.getMonth() >= 3 ? now.getFullYear() : now.getFullYear() - 1;
  const options = [];
  for (let i = 0; i < 5; i++) {
    const startYear = currentYear - i;
    const endYear = (startYear + 1) % 100;
    options.push(`${startYear}-${endYear.toString().padStart(2, '0')}`);
  }
  return options;
};

const FY_OPTIONS = generateFYOptions();

// ---- Change Password Modal ----
const ChangePasswordModal = ({ onClose }) => {
  const [currentPw, setCurrentPw] = useState('');
  const [newPw, setNewPw] = useState('');
  const [confirmPw, setConfirmPw] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (newPw !== confirmPw) { toast.error('Passwords do not match'); return; }
    if (newPw.length < 4) { toast.error('Password must be at least 4 characters'); return; }
    setLoading(true);
    try {
      const token = localStorage.getItem('auth_token');
      const res = await axios.post(`${API}/auth/change-password`,
        { current_password: currentPw, new_password: newPw },
        { headers: { Authorization: `Bearer ${token}` }, withCredentials: true }
      );
      if (res.data?.success) { toast.success('Password changed!'); onClose(); }
      else { toast.error(res.data?.error || 'Failed'); }
    } catch { toast.error('Error changing password'); }
    finally { setLoading(false); }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" data-testid="change-password-modal">
      <div className="bg-white rounded-xl p-6 w-full max-w-sm mx-4">
        <h3 className="text-lg font-semibold text-stone-900 mb-4">Change Password</h3>
        <form onSubmit={handleSubmit} className="space-y-3">
          <input type="password" placeholder="Current Password" value={currentPw} onChange={e => setCurrentPw(e.target.value)}
            className="w-full px-3 py-2 border border-stone-200 rounded-lg text-sm" data-testid="current-password-input" required />
          <input type="password" placeholder="New Password" value={newPw} onChange={e => setNewPw(e.target.value)}
            className="w-full px-3 py-2 border border-stone-200 rounded-lg text-sm" data-testid="new-password-input" required />
          <input type="password" placeholder="Confirm New Password" value={confirmPw} onChange={e => setConfirmPw(e.target.value)}
            className="w-full px-3 py-2 border border-stone-200 rounded-lg text-sm" data-testid="confirm-password-input" required />
          <div className="flex gap-2 pt-2">
            <button type="button" onClick={onClose} className="flex-1 px-3 py-2 border border-stone-200 rounded-lg text-sm">Cancel</button>
            <button type="submit" disabled={loading} className="flex-1 btn-primary py-2 text-sm" data-testid="change-password-submit">
              {loading ? 'Saving...' : 'Change'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

// ---- User Management Modal (Admin) ----
const UserManagementModal = ({ onClose }) => {
  const [users, setUsers] = useState([]);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({ username: '', password: '', name: '', role: 'employee' });
  const [resetForm, setResetForm] = useState({ username: '', new_password: '' });
  const [showReset, setShowReset] = useState(null);
  const token = localStorage.getItem('auth_token');

  const fetchUsers = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/auth/users`, { headers: { Authorization: `Bearer ${token}` } });
      if (res.data?.success) setUsers(res.data.data.users || []);
    } catch { /* ignore */ }
  }, [token]);

  useEffect(() => { fetchUsers(); }, [fetchUsers]);

  const createUser = async (e) => {
    e.preventDefault();
    try {
      const res = await axios.post(`${API}/auth/users`, form, { headers: { Authorization: `Bearer ${token}` } });
      if (res.data?.success) { toast.success('User created'); setShowCreate(false); setForm({ username: '', password: '', name: '', role: 'employee' }); fetchUsers(); }
      else toast.error(res.data?.error || 'Failed');
    } catch { toast.error('Error creating user'); }
  };

  const deleteUser = async (username) => {
    if (!window.confirm(`Delete user "${username}"?`)) return;
    try {
      const res = await axios.delete(`${API}/auth/users/${username}`, { headers: { Authorization: `Bearer ${token}` } });
      if (res.data?.success) { toast.success('User deleted'); fetchUsers(); }
      else toast.error(res.data?.error);
    } catch { toast.error('Error deleting user'); }
  };

  const resetPassword = async (e) => {
    e.preventDefault();
    try {
      const res = await axios.post(`${API}/auth/reset-password`, resetForm, { headers: { Authorization: `Bearer ${token}` } });
      if (res.data?.success) { toast.success('Password reset'); setShowReset(null); }
      else toast.error(res.data?.error);
    } catch { toast.error('Error resetting password'); }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" data-testid="user-management-modal">
      <div className="bg-white rounded-xl p-6 w-full max-w-lg mx-4 max-h-[80vh] overflow-y-auto">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-stone-900">User Management</h3>
          <button onClick={onClose} className="text-stone-400 hover:text-stone-700"><X size={20} /></button>
        </div>

        <button onClick={() => setShowCreate(!showCreate)} className="btn-primary text-sm px-3 py-2 mb-4 flex items-center gap-1" data-testid="create-user-btn">
          <UserPlus size={16} /> Add User
        </button>

        {showCreate && (
          <form onSubmit={createUser} className="bg-stone-50 p-4 rounded-lg mb-4 space-y-2">
            <input type="text" placeholder="Username" value={form.username} onChange={e => setForm({ ...form, username: e.target.value })}
              className="w-full px-3 py-2 border border-stone-200 rounded-lg text-sm" data-testid="new-user-username" required />
            <input type="text" placeholder="Full Name" value={form.name} onChange={e => setForm({ ...form, name: e.target.value })}
              className="w-full px-3 py-2 border border-stone-200 rounded-lg text-sm" data-testid="new-user-name" required />
            <input type="password" placeholder="Password" value={form.password} onChange={e => setForm({ ...form, password: e.target.value })}
              className="w-full px-3 py-2 border border-stone-200 rounded-lg text-sm" data-testid="new-user-password" required />
            <select value={form.role} onChange={e => setForm({ ...form, role: e.target.value })}
              className="w-full px-3 py-2 border border-stone-200 rounded-lg text-sm" data-testid="new-user-role">
              <option value="employee">Employee</option>
              <option value="admin">Admin</option>
            </select>
            <div className="flex gap-2">
              <button type="button" onClick={() => setShowCreate(false)} className="px-3 py-2 border border-stone-200 rounded-lg text-sm">Cancel</button>
              <button type="submit" className="btn-primary px-3 py-2 text-sm" data-testid="submit-create-user">Create</button>
            </div>
          </form>
        )}

        <div className="space-y-2">
          {users.map(u => (
            <div key={u.username} className="flex items-center justify-between bg-stone-50 p-3 rounded-lg">
              <div>
                <span className="font-medium text-sm text-stone-900">{u.name || u.username}</span>
                <span className="text-xs text-stone-500 ml-2">@{u.username}</span>
                <span className={`ml-2 text-xs px-2 py-0.5 rounded-full ${u.role === 'admin' ? 'bg-amber-100 text-amber-800' : 'bg-blue-100 text-blue-800'}`}>
                  {u.role}
                </span>
              </div>
              <div className="flex gap-1">
                <button onClick={() => { setShowReset(u.username); setResetForm({ username: u.username, new_password: '' }); }}
                  className="text-xs text-stone-500 hover:text-[#064E3B] px-2 py-1" data-testid={`reset-pw-${u.username}`}>Reset PW</button>
                {u.role !== 'admin' && (
                  <button onClick={() => deleteUser(u.username)}
                    className="text-xs text-red-500 hover:text-red-700 px-2 py-1" data-testid={`delete-user-${u.username}`}>Delete</button>
                )}
              </div>
            </div>
          ))}
        </div>

        {showReset && (
          <form onSubmit={resetPassword} className="mt-4 bg-amber-50 p-4 rounded-lg space-y-2">
            <p className="text-sm font-medium">Reset password for: <span className="text-[#064E3B]">{showReset}</span></p>
            <input type="password" placeholder="New Password" value={resetForm.new_password} onChange={e => setResetForm({ ...resetForm, new_password: e.target.value })}
              className="w-full px-3 py-2 border border-stone-200 rounded-lg text-sm" data-testid="reset-password-input" required />
            <div className="flex gap-2">
              <button type="button" onClick={() => setShowReset(null)} className="px-3 py-2 border border-stone-200 rounded-lg text-sm">Cancel</button>
              <button type="submit" className="btn-primary px-3 py-2 text-sm" data-testid="submit-reset-password">Reset</button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
};

// ---- Navigation ----
const Navigation = ({ user, onLogout, selectedFY, onFYChange }) => {
  const [isConnected, setIsConnected] = useState(false);
  const [companyName, setCompanyName] = useState('');
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [showChangePassword, setShowChangePassword] = useState(false);
  const [showUserMgmt, setShowUserMgmt] = useState(false);
  const [showUserMenu, setShowUserMenu] = useState(false);
  const location = useLocation();

  useEffect(() => {
    const check = async () => {
      try {
        const res = await axios.get(`${API}/tally/status`);
        setIsConnected(res.data?.data?.is_connected || false);
        setCompanyName(res.data?.data?.company_name || '');
      } catch { /* ignore */ }
    };
    check();
    const interval = setInterval(check, 30000);
    return () => clearInterval(interval);
  }, []);

  const isAdmin = user?.role === 'admin';

  // Role-based nav: employees only see Sales, Inventory, CRM
  const allNavItems = [
    { path: '/', icon: BarChart3, label: 'Dashboard', roles: ['admin'] },
    { path: '/inventory', icon: Package, label: 'Inventory', roles: ['admin', 'employee'] },
    { path: '/sales', icon: TrendingUp, label: 'Sales', roles: ['admin', 'employee'] },
    { path: '/crm', icon: Users, label: 'CRM', roles: ['admin', 'employee'] },
    { path: '/analytics', icon: Activity, label: 'Analytics', roles: ['admin'] },
    { path: '/ai-reports', icon: Zap, label: 'AI Reports', roles: ['admin'] },
    { path: '/salesman', icon: Users, label: 'Salesman', roles: ['admin'] },
    { path: '/setup', icon: Settings, label: 'Setup', roles: ['admin'] }
  ];

  const navItems = allNavItems.filter(item => item.roles.includes(user?.role));

  return (
    <>
      <nav className="nav-header" data-testid="main-navigation">
        <div className="max-w-7xl mx-auto px-6 py-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-[#064E3B] rounded-lg flex items-center justify-center">
                <BarChart3 className="text-white" size={24} />
              </div>
              <div>
                <h1 className="text-lg font-semibold text-stone-900" style={{ fontFamily: 'Outfit, sans-serif' }}>
                  {companyName || 'Tally Reports'}
                </h1>
                <p className="text-xs text-stone-500">AI-Powered Analytics</p>
              </div>
            </div>

            <button data-testid="mobile-menu-button" className="md:hidden text-stone-700"
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}>
              {mobileMenuOpen ? <X size={24} /> : <Menu size={24} />}
            </button>

            <div className="hidden md:flex items-center gap-4">
              {navItems.map((item) => {
                const Icon = item.icon;
                const isActive = location.pathname === item.path;
                return (
                  <Link key={item.path} to={item.path}
                    data-testid={`nav-${item.label.toLowerCase().replace(' ', '-')}`}
                    className={`flex items-center gap-1.5 px-3 py-2 rounded-lg transition-colors text-sm ${
                      isActive ? 'bg-[#064E3B] text-white' : 'text-stone-600 hover:text-[#064E3B] hover:bg-stone-100'
                    }`}>
                    <Icon size={16} />
                    <span className="font-medium">{item.label}</span>
                  </Link>
                );
              })}

              {/* FY Selector */}
              <select value={selectedFY} onChange={e => onFYChange(e.target.value)}
                className="text-xs border border-stone-200 rounded-lg px-2 py-1.5 bg-white text-stone-700 focus:ring-1 focus:ring-[#064E3B]"
                data-testid="fy-selector">
                {FY_OPTIONS.map(fy => <option key={fy} value={fy}>FY {fy}</option>)}
              </select>

              <div className={`status-badge ${isConnected ? 'connected' : 'disconnected'}`} data-testid="connection-status">
                <span className={`w-2 h-2 rounded-full mr-1.5 ${isConnected ? 'bg-green-600' : 'bg-red-600'}`} />
                {isConnected ? 'Synced' : 'Not Synced'}
              </div>

              {/* User Menu */}
              <div className="relative ml-2 pl-2 border-l border-stone-200">
                <button onClick={() => setShowUserMenu(!showUserMenu)}
                  className="flex items-center gap-1.5 text-sm text-stone-600 hover:text-stone-900"
                  data-testid="user-menu-button">
                  <span className={`text-xs px-1.5 py-0.5 rounded ${isAdmin ? 'bg-amber-100 text-amber-800' : 'bg-blue-100 text-blue-800'}`}>
                    {user?.role}
                  </span>
                  <span className="font-medium">{user?.name || user?.username}</span>
                  <ChevronDown size={14} />
                </button>

                {showUserMenu && (
                  <div className="absolute right-0 top-full mt-1 w-48 bg-white border border-stone-200 rounded-lg shadow-lg z-50 py-1">
                    <button onClick={() => { setShowChangePassword(true); setShowUserMenu(false); }}
                      className="w-full text-left px-4 py-2 text-sm text-stone-700 hover:bg-stone-50 flex items-center gap-2"
                      data-testid="change-password-btn">
                      <KeyRound size={14} /> Change Password
                    </button>
                    {isAdmin && (
                      <button onClick={() => { setShowUserMgmt(true); setShowUserMenu(false); }}
                        className="w-full text-left px-4 py-2 text-sm text-stone-700 hover:bg-stone-50 flex items-center gap-2"
                        data-testid="manage-users-btn">
                        <UserPlus size={14} /> Manage Users
                      </button>
                    )}
                    <hr className="my-1 border-stone-100" />
                    <button onClick={onLogout}
                      className="w-full text-left px-4 py-2 text-sm text-red-600 hover:bg-red-50 flex items-center gap-2"
                      data-testid="logout-button">
                      <LogOut size={14} /> Logout
                    </button>
                  </div>
                )}
              </div>
            </div>
          </div>

          {mobileMenuOpen && (
            <div className="md:hidden mt-4 pb-4 space-y-2">
              <select value={selectedFY} onChange={e => onFYChange(e.target.value)}
                className="w-full text-sm border border-stone-200 rounded-lg px-3 py-2 mb-2">
                {FY_OPTIONS.map(fy => <option key={fy} value={fy}>FY {fy}</option>)}
              </select>
              {navItems.map((item) => {
                const Icon = item.icon;
                const isActive = location.pathname === item.path;
                return (
                  <Link key={item.path} to={item.path} onClick={() => setMobileMenuOpen(false)}
                    className={`flex items-center gap-3 px-4 py-3 rounded-lg transition-colors ${
                      isActive ? 'bg-[#064E3B] text-white' : 'text-stone-600 hover:bg-stone-100'
                    }`}>
                    <Icon size={20} />
                    <span className="text-sm font-medium">{item.label}</span>
                  </Link>
                );
              })}
              <div className="flex gap-2 pt-2">
                <button onClick={() => setShowChangePassword(true)} className="flex-1 text-sm border border-stone-200 rounded-lg px-3 py-2">Change Password</button>
                <button onClick={onLogout} className="flex-1 text-sm text-red-600 border border-red-200 rounded-lg px-3 py-2">Logout</button>
              </div>
            </div>
          )}
        </div>
      </nav>

      {showChangePassword && <ChangePasswordModal onClose={() => setShowChangePassword(false)} />}
      {showUserMgmt && <UserManagementModal onClose={() => setShowUserMgmt(false)} />}
    </>
  );
};

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [selectedFY, setSelectedFY] = useState(FY_OPTIONS[0]);

  useEffect(() => {
    const token = localStorage.getItem('auth_token');
    const savedUser = localStorage.getItem('user_data');

    if (token && savedUser) {
      axios.get(`${API}/auth/me`, { headers: { Authorization: `Bearer ${token}` }, withCredentials: true })
        .then(response => {
          if (response.data?.success) {
            const userData = response.data.data;
            setIsAuthenticated(true);
            setUser(userData);
            localStorage.setItem('user_data', JSON.stringify(userData));
          } else {
            localStorage.removeItem('auth_token');
            localStorage.removeItem('user_data');
          }
        })
        .catch(() => {
          localStorage.removeItem('auth_token');
          localStorage.removeItem('user_data');
        })
        .finally(() => setLoading(false));
    } else {
      setLoading(false);
    }
  }, []);

  const handleLoginSuccess = (userData) => {
    setIsAuthenticated(true);
    setUser(userData);
  };

  const handleLogout = async () => {
    const token = localStorage.getItem('auth_token');
    try {
      await axios.post(`${API}/auth/logout`, {}, { headers: { Authorization: `Bearer ${token}` }, withCredentials: true });
    } catch { /* ignore */ }
    localStorage.removeItem('auth_token');
    localStorage.removeItem('user_data');
    setIsAuthenticated(false);
    setUser(null);
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-[#FDFBF7] flex items-center justify-center">
        <div className="loading-spinner" />
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Login onLoginSuccess={handleLoginSuccess} />;
  }

  const isAdmin = user?.role === 'admin';
  const defaultRoute = isAdmin ? '/' : '/inventory';

  return (
    <div className="App">
      <BrowserRouter>
        <Navigation user={user} onLogout={handleLogout} selectedFY={selectedFY} onFYChange={setSelectedFY} />
        <div className="max-w-7xl mx-auto px-6 py-8">
          <Routes>
            <Route path="/" element={isAdmin ? <Dashboard selectedFY={selectedFY} /> : <Inventory selectedFY={selectedFY} />} />
            <Route path="/inventory" element={<Inventory selectedFY={selectedFY} />} />
            <Route path="/sales" element={<Sales selectedFY={selectedFY} />} />
            <Route path="/crm" element={<CustomerCRM user={user} selectedFY={selectedFY} />} />
            {isAdmin && <>
              <Route path="/analytics" element={<InventoryAnalytics />} />
              <Route path="/ai-reports" element={<EnhancedAIReports />} />
              <Route path="/ai-query" element={<AIQueryBuilder />} />
              <Route path="/salesman" element={<SalesmanPerformance />} />
              <Route path="/history" element={<ReportHistory />} />
              <Route path="/setup" element={<TallySetup />} />
            </>}
          </Routes>
        </div>
      </BrowserRouter>
    </div>
  );
}

export default App;
