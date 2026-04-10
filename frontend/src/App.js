import React, { useState, useEffect, useCallback, useRef } from 'react';
import axios from 'axios';
import { toast, Toaster } from 'sonner';
import {
  LayoutDashboard, Package, ShoppingCart, Users, BarChart3,
  Brain, Truck, History, Settings, LogOut, RefreshCw, Menu,
  X, Building2, Shield, User, Lock, ChevronDown, Lightbulb
} from 'lucide-react';
import Dashboard from './pages/Dashboard';
import Inventory from './pages/Inventory';
import Sales from './pages/Sales';
import CustomerCRM from './pages/CustomerCRM';
import InventoryAnalytics from './pages/InventoryAnalytics';
import EnhancedAIReports from './pages/EnhancedAIReports';
import SalesmanPerformance from './pages/SalesmanPerformance';
import SyncHistory from './pages/SyncHistory';
import TallySetup from './pages/TallySetup';
import SuperAdminDashboard from './pages/SuperAdminDashboard';
import CompanySelector from './pages/CompanySelector';
import ProfileModal from './pages/ProfileModal';
import ActivityLog from './pages/ActivityLog';
import InsiderResult from './pages/InsiderResult';
import LandingPage from './pages/LandingPage';
import SignupPage from './pages/SignupPage';

const API = process.env.REACT_APP_BACKEND_URL + '/api';
const WS_URL = process.env.REACT_APP_BACKEND_URL?.replace('https://', 'wss://').replace('http://', 'ws://') + '/api/ws/sync-status';

// Feature to nav mapping
const FEATURE_NAV_MAP = {
  dashboard: { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
  sales: { id: 'sales', label: 'Sales', icon: ShoppingCart },
  crm: { id: 'crm', label: 'CRM', icon: Users },
  inventory: { id: 'inventory', label: 'Inventory', icon: Package },
  analytics: { id: 'analytics', label: 'Analytics', icon: BarChart3 },
  salesman: { id: 'salesman', label: 'Salesman', icon: Truck },
  ai_reports: { id: 'ai-reports', label: 'AI Reports', icon: Brain },
  insider: { id: 'insider', label: 'Insider Result', icon: Lightbulb },
  sync_history: { id: 'sync-history', label: 'Sync History', icon: History },
  setup: { id: 'setup', label: 'Setup', icon: Settings },
};

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(null);
  const [currentPage, setCurrentPage] = useState('dashboard');
  const [selectedFY, setSelectedFY] = useState('2025-26');
  const [selectedCompany, setSelectedCompany] = useState('');
  const [showCompanySelector, setShowCompanySelector] = useState(false);
  const [syncStatus, setSyncStatus] = useState(null);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [showProfile, setShowProfile] = useState(false);
  const [showUserMenu, setShowUserMenu] = useState(false);
  const [publicView, setPublicView] = useState('landing'); // landing, login, signup
  const wsRef = useRef(null);
  const userMenuRef = useRef(null);

  // Login states
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loginLoading, setLoginLoading] = useState(false);

  // Set auth header
  useEffect(() => {
    if (token) {
      axios.defaults.headers.common['Authorization'] = `Bearer ${token}`;
    }
  }, [token]);

  // Set company header
  useEffect(() => {
    if (selectedCompany) {
      axios.defaults.headers.common['X-Company-ID'] = selectedCompany;
    } else {
      delete axios.defaults.headers.common['X-Company-ID'];
    }
  }, [selectedCompany]);

  // Check auth on mount
  useEffect(() => {
    const savedToken = localStorage.getItem('flowra_token');
    if (savedToken) {
      setToken(savedToken);
      axios.defaults.headers.common['Authorization'] = `Bearer ${savedToken}`;
      axios.get(`${API}/auth/me`).then(res => {
        if (res.data?.success && res.data?.data) {
          const userData = res.data.data;
          setUser(userData);
          setIsAuthenticated(true);
          if (userData.role === 'super_admin') {
            setCurrentPage('super-admin');
          } else {
            const savedCompany = localStorage.getItem('flowra_company');
            if (savedCompany && (userData.companies || []).includes(savedCompany)) {
              setSelectedCompany(savedCompany);
            } else if ((userData.companies || []).length > 1) {
              setShowCompanySelector(true);
            } else if ((userData.companies || []).length === 1) {
              setSelectedCompany(userData.companies[0]);
              localStorage.setItem('flowra_company', userData.companies[0]);
            }
          }
        } else {
          localStorage.removeItem('flowra_token');
        }
      }).catch(() => {
        localStorage.removeItem('flowra_token');
      });
    }
  }, []);

  // WebSocket connection
  useEffect(() => {
    if (!isAuthenticated || user?.role === 'super_admin') return;
    const connectWs = () => {
      try {
        wsRef.current = new WebSocket(WS_URL);
        wsRef.current.onopen = () => {
          if (wsRef.current?.readyState === WebSocket.OPEN) {
            wsRef.current.send(JSON.stringify({
              action: 'get_status',
              tenant_id: user?.tenant_id || '',
              company_id: selectedCompany || ''
            }));
          }
        };
        wsRef.current.onmessage = (event) => {
          try {
            const msg = JSON.parse(event.data);
            if (msg.event === 'status_response') {
              setSyncStatus(msg.data?.sync_status);
            }
            if (msg.event === 'data_synced') {
              toast.success(`${msg.data?.data_type}: ${msg.data?.count} items synced`);
            }
          } catch {}
        };
        wsRef.current.onclose = () => {
          setTimeout(connectWs, 5000);
        };
      } catch {}
    };
    connectWs();
    return () => { wsRef.current?.close(); };
  }, [isAuthenticated, user?.role, selectedCompany]);

  // Close user menu on outside click
  useEffect(() => {
    const handler = (e) => {
      if (userMenuRef.current && !userMenuRef.current.contains(e.target)) {
        setShowUserMenu(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const handleLogin = async (e) => {
    e.preventDefault();
    if (!username.trim()) { toast.error('Please enter your User ID'); return; }
    if (!password.trim()) { toast.error('Please enter your Password'); return; }
    setLoginLoading(true);
    try {
      const res = await axios.post(`${API}/auth/login`, { username, password });
      if (res.data?.success) {
        const data = res.data.data;
        setToken(data.token);
        localStorage.setItem('flowra_token', data.token);
        setUser(data);
        setIsAuthenticated(true);
        toast.success(`Welcome, ${data.name || data.username}!`);

        if (data.role === 'super_admin') {
          setCurrentPage('super-admin');
        } else {
          // Check companies
          if ((data.companies || []).length > 1) {
            setShowCompanySelector(true);
          } else if ((data.companies || []).length === 1) {
            setSelectedCompany(data.companies[0]);
            localStorage.setItem('flowra_company', data.companies[0]);
          }
        }
      } else {
        toast.error(res.data?.error || 'Login failed');
      }
    } catch (err) {
      toast.error('Login failed');
    } finally {
      setLoginLoading(false);
    }
  };

  const handleLogout = async () => {
    try { await axios.post(`${API}/auth/logout`); } catch {}
    setIsAuthenticated(false);
    setUser(null);
    setToken(null);
    setSelectedCompany('');
    setShowUserMenu(false);
    localStorage.removeItem('flowra_token');
    localStorage.removeItem('flowra_company');
    delete axios.defaults.headers.common['Authorization'];
    delete axios.defaults.headers.common['X-Company-ID'];
    setCurrentPage('dashboard');
    setUsername('');
    setPassword('');
  };

  const handleCompanySelect = (company) => {
    setSelectedCompany(company);
    localStorage.setItem('flowra_company', company);
    setShowCompanySelector(false);
  };

  const isFeatureActive = useCallback((featureId) => {
    if (!user) return false;
    if (user.role === 'super_admin') return false;
    const features = user.features || [];
    return features.includes(featureId);
  }, [user]);

  const getNavItems = useCallback(() => {
    if (!user) return [];
    if (user.role === 'super_admin') return [];
    const features = user.features || [];
    const items = features
      .map(f => FEATURE_NAV_MAP[f])
      .filter(Boolean);
    // Insert Activity after Sync History but before Setup
    const setupIdx = items.findIndex(i => i.id === 'setup');
    const activityItem = { id: 'activity', label: 'Activity', icon: History };
    if (setupIdx >= 0) {
      items.splice(setupIdx, 0, activityItem);
    } else {
      items.push(activityItem);
    }
    return items;
  }, [user]);

  // Generate FY options
  const fyOptions = [];
  const currentYear = new Date().getFullYear();
  for (let i = currentYear; i >= currentYear - 5; i--) {
    fyOptions.push(`${i}-${String(i + 1).slice(2)}`);
  }

  // Public pages (not authenticated)
  if (!isAuthenticated) {
    if (publicView === 'signup') {
      return (
        <>
          <Toaster position="top-right" richColors />
          <SignupPage
            onNavigateToLogin={() => setPublicView('login')}
            onNavigateToLanding={() => setPublicView('landing')}
          />
        </>
      );
    }

    if (publicView === 'landing') {
      return (
        <>
          <Toaster position="top-right" richColors />
          <LandingPage
            onNavigateToLogin={() => setPublicView('login')}
            onNavigateToSignup={() => setPublicView('signup')}
          />
        </>
      );
    }

    // Login page (publicView === 'login' or fallback)
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <Toaster position="top-right" richColors />
        <div className="w-full max-w-md p-8">
          <div className="text-center mb-8">
            <img src="/flowra-logo.png" alt="FLOWRA" className="h-16 mx-auto mb-3" data-testid="login-logo" />
            <h1 className="text-3xl font-bold text-slate-900 tracking-tight">FLOWRA</h1>
            <p className="text-slate-500 mt-1 text-sm">Organize. Automate. Accelerate.</p>
          </div>
          <form onSubmit={handleLogin} className="bg-white rounded-2xl border border-slate-200 p-8 space-y-5">
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
              type="submit" disabled={loginLoading}
              className="w-full py-2.5 bg-[#2563EB] text-white rounded-lg font-medium hover:bg-[#1D4ED8] disabled:opacity-50 transition-colors"
              data-testid="login-button"
            >
              {loginLoading ? 'Signing in...' : 'Sign In'}
            </button>
          </form>
          <div className="flex items-center justify-between mt-4">
            <button onClick={() => setPublicView('landing')} className="text-sm text-[#2563EB] hover:underline" data-testid="back-to-home">Back to Home</button>
            <button onClick={() => setPublicView('signup')} className="text-sm text-[#2563EB] hover:underline" data-testid="go-to-signup">New Customer? Sign Up</button>
          </div>
          <p className="text-center text-xs text-slate-400 mt-6">FLOWRA by Jodidar India</p>
        </div>
      </div>
    );
  }

  // Company selector
  if (showCompanySelector && user?.role !== 'super_admin') {
    return (
      <div className="min-h-screen bg-slate-50">
        <Toaster position="top-right" richColors />
        <CompanySelector companies={user?.companies || []} onSelect={handleCompanySelect} />
      </div>
    );
  }

  // Super Admin view
  if (user?.role === 'super_admin') {
    return (
      <div className="min-h-screen bg-slate-50">
        <Toaster position="top-right" richColors />
        {/* Super Admin Navbar */}
        <nav className="bg-white border-b border-slate-200 sticky top-0 z-40">
          <div className="max-w-7xl mx-auto px-4 sm:px-6">
            <div className="flex items-center justify-between h-16">
              <div className="flex items-center gap-3">
                <img src="/flowra-logo.png" alt="FLOWRA" className="h-8" data-testid="navbar-logo" />
                <span className="text-lg font-bold text-slate-900">FLOWRA</span>
                <span className="px-2.5 py-0.5 rounded-full bg-red-50 text-red-700 text-xs font-semibold">Super Admin</span>
              </div>
              <div className="flex items-center gap-3">
                <div className="relative" ref={userMenuRef}>
                  <button
                    onClick={() => setShowUserMenu(!showUserMenu)}
                    className="flex items-center gap-2 px-3 py-1.5 rounded-lg hover:bg-slate-50 text-sm"
                    data-testid="user-menu-btn"
                  >
                    <div className="w-7 h-7 rounded-full bg-red-600 text-white flex items-center justify-center text-xs font-bold">SA</div>
                    <span className="text-slate-700 font-medium hidden sm:inline">{user?.name || 'Super Admin'}</span>
                    <ChevronDown size={14} className="text-slate-400" />
                  </button>
                  {showUserMenu && (
                    <div className="absolute right-0 mt-1 bg-white border border-slate-200 rounded-xl shadow-lg py-1.5 w-48 z-50">
                      <button onClick={() => { setShowProfile(true); setShowUserMenu(false); }} className="w-full px-4 py-2 text-left text-sm hover:bg-slate-50 flex items-center gap-2" data-testid="profile-btn">
                        <User size={14} className="text-slate-400" /> Profile
                      </button>
                      <button onClick={() => { setShowProfile(true); setShowUserMenu(false); }} className="w-full px-4 py-2 text-left text-sm hover:bg-slate-50 flex items-center gap-2">
                        <Lock size={14} className="text-slate-400" /> Change Password
                      </button>
                      <hr className="my-1 border-slate-100" />
                      <button onClick={handleLogout} className="w-full px-4 py-2 text-left text-sm hover:bg-red-50 text-red-600 flex items-center gap-2" data-testid="logout-btn">
                        <LogOut size={14} /> Logout
                      </button>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        </nav>

        <main className="p-4 sm:p-6">
          <SuperAdminDashboard token={token} />
        </main>

        <footer className="text-center py-4 text-xs text-slate-400">
          copyright: Jodidar India
        </footer>

        {showProfile && <ProfileModal user={user} token={token} onClose={() => setShowProfile(false)} />}
      </div>
    );
  }

  // Normal admin/employee view
  const navItems = getNavItems();

  const renderFeatureGated = (featureId, component) => {
    if (isFeatureActive(featureId)) return component;
    return (
      <div className="flex items-center justify-center h-[60vh]" data-testid="feature-locked">
        <div className="text-center p-8 bg-white rounded-2xl border border-slate-200 max-w-md">
          <div className="w-16 h-16 bg-slate-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <Lock size={28} className="text-slate-400" />
          </div>
          <h3 className="text-lg font-semibold text-slate-900 mb-2">Feature Not Activated</h3>
          <p className="text-slate-500 text-sm">Subscribe for this feature. Contact your FLOWRA administrator to activate <strong className="capitalize">{featureId.replace('_', ' ')}</strong>.</p>
        </div>
      </div>
    );
  };

  const renderPage = () => {
    switch (currentPage) {
      case 'dashboard': return renderFeatureGated('dashboard', <Dashboard selectedFY={selectedFY} companyId={selectedCompany} />);
      case 'inventory': return renderFeatureGated('inventory', <Inventory selectedFY={selectedFY} companyId={selectedCompany} />);
      case 'sales': return renderFeatureGated('sales', <Sales selectedFY={selectedFY} companyId={selectedCompany} />);
      case 'crm': return renderFeatureGated('crm', <CustomerCRM selectedFY={selectedFY} companyId={selectedCompany} />);
      case 'analytics': return renderFeatureGated('analytics', <InventoryAnalytics selectedFY={selectedFY} companyId={selectedCompany} />);
      case 'ai-reports': return renderFeatureGated('ai_reports', <EnhancedAIReports selectedFY={selectedFY} companyId={selectedCompany} />);
      case 'salesman': return renderFeatureGated('salesman', <SalesmanPerformance selectedFY={selectedFY} companyId={selectedCompany} />);
      case 'sync-history': return renderFeatureGated('sync_history', <SyncHistory companyId={selectedCompany} />);
      case 'setup': return renderFeatureGated('setup', <TallySetup companyId={selectedCompany} />);
      case 'activity': return <ActivityLog token={token} role={user?.role} />;
      case 'insider': return renderFeatureGated('insider', <InsiderResult selectedFY={selectedFY} companyId={selectedCompany} />);
      default: return renderFeatureGated('dashboard', <Dashboard selectedFY={selectedFY} companyId={selectedCompany} />);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50">
      <Toaster position="top-right" richColors />

      {/* Navbar */}
      <nav className="bg-white border-b border-slate-200 sticky top-0 z-40">
        <div className="max-w-full mx-auto px-3 sm:px-6">
          <div className="flex items-center justify-between h-14">
            {/* Left: Logo + Company */}
            <div className="flex items-center gap-2 sm:gap-3">
              <button onClick={() => setMobileMenuOpen(!mobileMenuOpen)} className="md:hidden p-1.5 hover:bg-slate-100 rounded-lg">
                {mobileMenuOpen ? <X size={20} /> : <Menu size={20} />}
              </button>
              <img src="/flowra-logo.png" alt="FLOWRA" className="h-7 hidden sm:block" data-testid="navbar-logo" />
              <div className="flex flex-col">
                <span className="text-sm sm:text-base font-bold text-slate-900 leading-tight">FLOWRA</span>
                {selectedCompany && (
                  <button
                    onClick={() => (user?.companies || []).length > 1 && setShowCompanySelector(true)}
                    className="text-[10px] sm:text-xs text-slate-500 hover:text-[#2563EB] flex items-center gap-1 leading-tight"
                    data-testid="company-switch-btn"
                  >
                    <Building2 size={10} />
                    <span className="truncate max-w-[120px] sm:max-w-[200px]">{selectedCompany}</span>
                  </button>
                )}
              </div>
            </div>

            {/* Center: Nav Items */}
            <div className="hidden md:flex items-center gap-0.5 overflow-x-auto">
              {navItems.map(item => {
                const Icon = item.icon;
                const isActive = currentPage === item.id;
                return (
                  <button
                    key={item.id}
                    onClick={() => setCurrentPage(item.id)}
                    data-testid={`nav-${item.id}`}
                    className={`px-3 py-1.5 rounded-lg text-xs font-medium whitespace-nowrap flex items-center gap-1.5 transition-colors ${
                      isActive ? 'bg-[#2563EB] text-white' : 'text-slate-600 hover:bg-slate-100'
                    }`}
                  >
                    <Icon size={14} />
                    {item.label}
                  </button>
                );
              })}
            </div>

            {/* Right: FY + Sync + User */}
            <div className="flex items-center gap-2">
              <select
                value={selectedFY}
                onChange={(e) => setSelectedFY(e.target.value)}
                className="px-2 py-1 text-xs border border-slate-200 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-[#2563EB]"
                data-testid="fy-selector"
              >
                {fyOptions.map(fy => <option key={fy} value={fy}>FY {fy}</option>)}
              </select>

              <div className="flex items-center gap-1.5" data-testid="sync-indicator">
                <RefreshCw size={12} className={`${syncStatus ? 'text-green-500' : 'text-slate-300'}`} />
                <span className="text-[10px] text-slate-400 hidden sm:inline">{syncStatus?.last_sync ? 'Synced' : 'No sync'}</span>
              </div>

              <div className="relative" ref={userMenuRef}>
                <button
                  onClick={() => setShowUserMenu(!showUserMenu)}
                  className="flex items-center gap-1.5 px-2 py-1 rounded-lg hover:bg-slate-50"
                  data-testid="user-menu-btn"
                >
                  <div className="w-6 h-6 rounded-full bg-[#2563EB] text-white flex items-center justify-center text-[10px] font-bold">
                    {(user?.name || user?.username || 'U')[0].toUpperCase()}
                  </div>
                  <span className="text-xs text-slate-700 font-medium hidden sm:inline">{user?.name || user?.username}</span>
                  <ChevronDown size={12} className="text-slate-400" />
                </button>
                {showUserMenu && (
                  <div className="absolute right-0 mt-1 bg-white border border-slate-200 rounded-xl shadow-lg py-1.5 w-48 z-50">
                    <div className="px-4 py-2 border-b border-slate-100">
                      <div className="text-sm font-medium text-slate-900">{user?.name || user?.username}</div>
                      <div className="text-xs text-slate-500 capitalize">{user?.role?.replace('_', ' ')}</div>
                    </div>
                    <button onClick={() => { setShowProfile(true); setShowUserMenu(false); }} className="w-full px-4 py-2 text-left text-sm hover:bg-slate-50 flex items-center gap-2" data-testid="profile-btn">
                      <User size={14} className="text-slate-400" /> Profile & Security
                    </button>
                    {(user?.companies || []).length > 1 && (
                      <button onClick={() => { setShowCompanySelector(true); setShowUserMenu(false); }} className="w-full px-4 py-2 text-left text-sm hover:bg-slate-50 flex items-center gap-2" data-testid="switch-company-btn">
                        <Building2 size={14} className="text-slate-400" /> Switch Company
                      </button>
                    )}
                    <hr className="my-1 border-slate-100" />
                    <button onClick={handleLogout} className="w-full px-4 py-2 text-left text-sm hover:bg-red-50 text-red-600 flex items-center gap-2" data-testid="logout-btn">
                      <LogOut size={14} /> Logout
                    </button>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </nav>

      {/* Mobile Menu */}
      {mobileMenuOpen && (
        <div className="md:hidden bg-white border-b border-slate-200 px-3 py-2 space-y-1">
          {navItems.map(item => {
            const Icon = item.icon;
            const isActive = currentPage === item.id;
            return (
              <button
                key={item.id}
                onClick={() => { setCurrentPage(item.id); setMobileMenuOpen(false); }}
                data-testid={`mobile-nav-${item.id}`}
                className={`w-full px-3 py-2 rounded-lg text-sm font-medium flex items-center gap-2 ${
                  isActive ? 'bg-[#2563EB] text-white' : 'text-slate-600 hover:bg-slate-100'
                }`}
              >
                <Icon size={16} />
                {item.label}
              </button>
            );
          })}
        </div>
      )}

      {/* Main Content */}
      <main className="p-3 sm:p-6 max-w-full">
        {renderPage()}
      </main>

      {/* Footer */}
      <footer className="text-center py-4 text-xs text-slate-400">
        copyright: Jodidar India
      </footer>

      {/* Modals */}
      {showProfile && <ProfileModal user={user} token={token} onClose={() => setShowProfile(false)} />}
      {showCompanySelector && (
        <CompanySelector companies={user?.companies || []} onSelect={handleCompanySelect} />
      )}
    </div>
  );
}

export default App;
