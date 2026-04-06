import React, { useState, useEffect } from 'react';
import { BrowserRouter, Routes, Route, Link, useLocation, Navigate } from 'react-router-dom';
import axios from 'axios';
import { BarChart3, Package, TrendingUp, Bot, FileText, Settings, Menu, X, Users, Activity, Zap, LogOut } from 'lucide-react';
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

const Navigation = ({ userEmail, onLogout }) => {
  const [isConnected, setIsConnected] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const location = useLocation();

  useEffect(() => {
    checkTallyStatus();
  }, []);

  const checkTallyStatus = async () => {
    try {
      const response = await axios.get(`${API}/tally/status`);
      setIsConnected(response.data?.data?.is_connected || false);
    } catch (error) {
      console.error('Error checking Tally status:', error);
    }
  };

  const navItems = [
    { path: '/', icon: BarChart3, label: 'Dashboard' },
    { path: '/inventory', icon: Package, label: 'Inventory' },
    { path: '/sales', icon: TrendingUp, label: 'Sales' },
    { path: '/crm', icon: Users, label: 'CRM' },
    { path: '/analytics', icon: Activity, label: 'Analytics' },
    { path: '/ai-reports', icon: Zap, label: 'AI Reports' },
    { path: '/salesman', icon: Users, label: 'Salesman' },
    { path: '/setup', icon: Settings, label: 'Setup' }
  ];

  return (
    <nav className="nav-header" data-testid="main-navigation">
      <div className="max-w-7xl mx-auto px-6 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-[#064E3B] rounded-lg flex items-center justify-center">
              <BarChart3 className="text-white" size={24} />
            </div>
            <div>
              <h1 className="text-xl font-semibold text-stone-900" style={{ fontFamily: 'Outfit, sans-serif' }}>Tally Reports</h1>
              <p className="text-xs text-stone-500">AI-Powered Analytics</p>
            </div>
          </div>

          <button
            data-testid="mobile-menu-button"
            className="md:hidden text-stone-700"
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
          >
            {mobileMenuOpen ? <X size={24} /> : <Menu size={24} />}
          </button>

          <div className="hidden md:flex items-center gap-6">
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = location.pathname === item.path;
              return (
                <Link
                  key={item.path}
                  to={item.path}
                  data-testid={`nav-${item.label.toLowerCase().replace(' ', '-')}`}
                  className={`flex items-center gap-2 px-3 py-2 rounded-lg transition-colors ${
                    isActive
                      ? 'bg-[#064E3B] text-white'
                      : 'text-stone-600 hover:text-[#064E3B] hover:bg-stone-100'
                  }`}
                >
                  <Icon size={18} />
                  <span className="text-sm font-medium">{item.label}</span>
                </Link>
              );
            })}

            <div className={`status-badge ${isConnected ? 'connected' : 'disconnected'}`}>
              <span className={`w-2 h-2 rounded-full mr-2 ${isConnected ? 'bg-green-600' : 'bg-red-600'}`} />
              {isConnected ? 'Connected' : 'Disconnected'}
            </div>

            <div className="flex items-center gap-3 ml-4 pl-4 border-l border-stone-200">
              <span className="text-sm text-stone-600" data-testid="user-email">{userEmail}</span>
              <button
                onClick={onLogout}
                className="text-stone-600 hover:text-red-600 transition-colors"
                title="Logout"
                data-testid="logout-button"
              >
                <LogOut size={18} />
              </button>
            </div>
          </div>
        </div>

        {mobileMenuOpen && (
          <div className="md:hidden mt-4 pb-4 space-y-2">
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = location.pathname === item.path;
              return (
                <Link
                  key={item.path}
                  to={item.path}
                  onClick={() => setMobileMenuOpen(false)}
                  className={`flex items-center gap-3 px-4 py-3 rounded-lg transition-colors ${
                    isActive
                      ? 'bg-[#064E3B] text-white'
                      : 'text-stone-600 hover:bg-stone-100'
                  }`}
                >
                  <Icon size={20} />
                  <span className="text-sm font-medium">{item.label}</span>
                </Link>
              );
            })}
          </div>
        )}
      </div>
    </nav>
  );
};

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [userEmail, setUserEmail] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Check if user has valid session
    const sessionToken = localStorage.getItem('session_token');
    const savedEmail = localStorage.getItem('user_email');
    
    if (sessionToken && savedEmail) {
      // Verify session with backend
      axios.post(`${API}/auth/verify-session?session_token=${sessionToken}`)
        .then(response => {
          if (response.data?.success) {
            setIsAuthenticated(true);
            setUserEmail(savedEmail);
          } else {
            localStorage.removeItem('session_token');
            localStorage.removeItem('user_email');
          }
        })
        .catch(() => {
          localStorage.removeItem('session_token');
          localStorage.removeItem('user_email');
        })
        .finally(() => setLoading(false));
    } else {
      setLoading(false);
    }
  }, []);

  const handleLoginSuccess = (email, sessionToken) => {
    setIsAuthenticated(true);
    setUserEmail(email);
  };

  const handleLogout = async () => {
    const sessionToken = localStorage.getItem('session_token');
    if (sessionToken) {
      try {
        await axios.post(`${API}/auth/logout?session_token=${sessionToken}`);
      } catch (error) {
        console.error('Logout error:', error);
      }
    }
    
    localStorage.removeItem('session_token');
    localStorage.removeItem('user_email');
    setIsAuthenticated(false);
    setUserEmail('');
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

  return (
    <div className="App">
      <BrowserRouter>
        <Navigation userEmail={userEmail} onLogout={handleLogout} />
        <div className="max-w-7xl mx-auto px-6 py-8">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/inventory" element={<Inventory />} />
            <Route path="/sales" element={<Sales />} />
            <Route path="/crm" element={<CustomerCRM />} />
            <Route path="/analytics" element={<InventoryAnalytics />} />
            <Route path="/ai-reports" element={<EnhancedAIReports />} />
            <Route path="/ai-query" element={<AIQueryBuilder />} />
            <Route path="/salesman" element={<SalesmanPerformance />} />
            <Route path="/history" element={<ReportHistory />} />
            <Route path="/setup" element={<TallySetup />} />
          </Routes>
        </div>
      </BrowserRouter>
    </div>
  );
}

export default App;
