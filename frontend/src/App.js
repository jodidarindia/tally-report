import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import './App.css';
import {
  LayoutDashboard, Package, ShoppingCart, Users, BarChart3,
  Brain, Truck, History, Settings, Lightbulb, Gift, Landmark, RefreshCw, Warehouse, GraduationCap
} from 'lucide-react';
import { toast } from 'sonner';
import { useAuth } from './hooks/useAuth';
import { useIdleTimeout } from './hooks/useIdleTimeout';
import { useCompany } from './hooks/useCompany';
import AppNavbar from './components/AppNavbar';
import SuperAdminLayout from './components/SuperAdminLayout';
import PublicRouter from './components/PublicRouter';
import PageRenderer from './components/PageRenderer';
import IdleWarningModal from './components/IdleWarningModal';
import CompanySelector from './pages/CompanySelector';
import ProfileModal from './pages/ProfileModal';
import RenewalPopup from './components/RenewalPopup';
import OnboardingTour from './components/OnboardingTour';

const WS_URL = process.env.REACT_APP_BACKEND_URL?.replace('https://', 'wss://').replace('http://', 'ws://') + '/api/ws/sync-status';

const FEATURE_NAV_MAP = {
  dashboard: { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
  sales: { id: 'sales', label: 'Sales', icon: ShoppingCart },
  crm: { id: 'crm', label: 'CRM', icon: Users },
  inventory: { id: 'inventory', label: 'Inventory', icon: Package },
  analytics: { id: 'analytics', label: 'Analytics', icon: BarChart3 },
  salesman: { id: 'salesman', label: 'Salesman', icon: Truck },
  ai_reports: { id: 'ai-reports', label: 'AI Reports', icon: Brain },
  insider: { id: 'insider', label: 'Insider Result', icon: Lightbulb },
  ca_corner: { id: 'ca-corner', label: 'CA Corner', icon: Landmark },
  dispatch: { id: 'dispatch', label: 'Dispatch', icon: Warehouse },
  sync_history: { id: 'sync-history', label: 'Sync History', icon: History },
  setup: { id: 'setup', label: 'Setup', icon: Settings },
};

function App() {
  const { isAuthenticated, user, token, loginLoading, login, logout } = useAuth();
  const company = useCompany(isAuthenticated);
  const { idleWarning, dismissWarning } = useIdleTimeout(isAuthenticated, logout);

  const [currentPage, setCurrentPage] = useState('dashboard');
  const [publicView, setPublicView] = useState('landing');
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [showProfile, setShowProfile] = useState(false);
  const [showRenewalPopup, setShowRenewalPopup] = useState(false);
  const [showOnboarding, setShowOnboarding] = useState(false);
  const [syncStatus, setSyncStatus] = useState(null);
  const [isSyncing, setIsSyncing] = useState(false);
  const wsRef = useRef(null);
  const initDoneRef = useRef(false);

  // After login / session restore: initialize company state and trigger UI side effects
  useEffect(() => {
    if (!isAuthenticated || !user) { initDoneRef.current = false; return; }
    if (initDoneRef.current) return;
    initDoneRef.current = true;

    company.initFromUser(user);

    if (user.role === 'super_admin') {
      setCurrentPage('super-admin');
      return;
    }

    if (user.role === 'dispatch') {
      setCurrentPage('dispatch');
      return;
    }

    if (user.role === 'salesman') {
      setCurrentPage('salesman-orders');
      return;
    }

    const daysLeft = user.subscription_days_left;
    if (daysLeft !== undefined && daysLeft !== null && daysLeft <= 30) {
      setShowRenewalPopup(true);
    }

    if (!user.onboarding_completed && !localStorage.getItem('flowra_onboarding_done')) {
      setTimeout(() => setShowOnboarding(true), 1500);
    }
  }, [isAuthenticated, user, company.initFromUser]);

  // Login handler (side effects handled by useEffect above)
  const handleLogin = useCallback(async (username, password) => {
    await login(username, password);
  }, [login]);

  // Logout handler — reset page FIRST so we never render a feature-locked
  // screen for the logged-out user (which previously caused the "feature not
  // activated" flash for dispatch/salesman roles on logout).
  const handleLogout = useCallback(() => {
    setCurrentPage('dashboard');
    setPublicView('landing');
    company.resetCompany();
    logout();
  }, [logout, company.resetCompany]);

  // WebSocket for sync status
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
              company_id: company.selectedCompany || ''
            }));
          }
        };
        wsRef.current.onmessage = (event) => {
          try {
            const msg = JSON.parse(event.data);
            if (msg.event === 'status_response') {
              setSyncStatus(msg.data?.sync_status);
              setIsSyncing(msg.data?.sync_status?.is_syncing || false);
            }
            if (msg.event === 'sync_started') setIsSyncing(true);
            if (msg.event === 'sync_complete' || msg.event === 'sync_error') setIsSyncing(false);
            if (msg.event === 'data_synced') toast.success(`${msg.data?.data_type}: ${msg.data?.count} items synced`);
          } catch {}
        };
        wsRef.current.onclose = () => { setTimeout(connectWs, 5000); };
      } catch {}
    };
    connectWs();
    return () => { wsRef.current?.close(); };
  }, [isAuthenticated, user?.role, company.selectedCompany]);

  // FY dropdown options
  const fyOptions = useMemo(() => {
    const yr = new Date().getFullYear();
    return Array.from({ length: 6 }, (_, i) => {
      const y = yr - i;
      return `${y}-${String(y + 1).slice(2)}`;
    });
  }, []);

  // Navigation items derived from user features
  const navItems = useMemo(() => {
    if (!user || user.role === 'super_admin') return [];
    const items = (user.features || []).map(f => FEATURE_NAV_MAP[f]).filter(Boolean);
    const setupIdx = items.findIndex(i => i.id === 'setup');
    const extras = [
      { id: 'activity', label: 'Activity', icon: History },
      { id: 'tutorials', label: 'Academy', icon: GraduationCap },
      { id: 'referral', label: 'Refer & Earn', icon: Gift },
    ];
    if (setupIdx >= 0) items.splice(setupIdx, 0, ...extras);
    else items.push(...extras);
    return items;
  }, [user]);

  // ── Unauthenticated ──
  if (!isAuthenticated) {
    return <PublicRouter view={publicView} onNavigate={setPublicView} onLogin={handleLogin} loginLoading={loginLoading} />;
  }

  // ── Company selector gate ──
  if (company.showCompanySelector && user?.role !== 'super_admin') {
    return (
      <div className="min-h-screen bg-slate-50">
        <CompanySelector companies={user?.companies || []} companyMappings={company.companyMappings} onSelect={company.selectCompany} />
      </div>
    );
  }

  // ── Super Admin ──
  if (user?.role === 'super_admin') {
    return <SuperAdminLayout user={user} token={token} onLogout={handleLogout} />;
  }

  // ── Normal User ──
  return (
    <div className="min-h-screen bg-slate-50">
      <AppNavbar
        user={user}
        navItems={navItems}
        currentPage={currentPage}
        setCurrentPage={setCurrentPage}
        selectedFY={company.selectedFY}
        setSelectedFY={company.setSelectedFY}
        fyOptions={fyOptions}
        selectedCompany={company.selectedCompany}
        companyMappings={company.companyMappings}
        onSwitchCompany={() => company.setShowCompanySelector(true)}
        excludeBranches={company.excludeBranches}
        onToggleBranches={company.toggleBranches}
        branchPartyCount={company.branchPartyCount}
        syncStatus={syncStatus}
        onLogout={handleLogout}
        onOpenProfile={() => setShowProfile(true)}
        onReplayTour={() => {
          localStorage.removeItem('flowra_onboarding_done');
          setShowOnboarding(true);
        }}
        mobileMenuOpen={mobileMenuOpen}
        setMobileMenuOpen={setMobileMenuOpen}
      />

      <main className="p-3 sm:p-6 max-w-full">
        {isSyncing && (
          <div className="mb-4 px-4 py-2.5 bg-amber-50 border border-amber-200 rounded-xl flex items-center gap-2.5" data-testid="sync-banner">
            <RefreshCw size={14} className="text-amber-600 animate-spin shrink-0" />
            <span className="text-sm text-amber-800 font-medium">Sync in progress — data is updating. Showing last synced data.</span>
          </div>
        )}
        <PageRenderer
          key={`pg-${company.selectedCompany || 'none'}`}
          currentPage={currentPage}
          user={user}
          selectedFY={company.selectedFY}
          selectedCompany={company.selectedCompany}
          excludeBranches={company.excludeBranches}
          token={token}
        />
      </main>

      <footer className="text-center py-4 text-xs text-slate-400">
        <p>&copy; {new Date().getFullYear()} JODIDAR INDIA. All rights reserved. FLOWRA is a brand owned by JODIDAR INDIA.</p>
        <p className="text-[9px] text-slate-400 mt-1 max-w-3xl mx-auto leading-relaxed" data-testid="tally-disclaimer">Tally* and Busy* are trademarks of their respective owners and are not affiliated, endorsed, connected or sponsored in any way to this website, mobile application or any of our affiliate sites. The same are used in accordance with honest practices and not used with any intention to misguide customers to take unfair advantage of the trademarks' distinct character or harm the holders' reputation.</p>
      </footer>

      {showProfile && <ProfileModal user={user} token={token} onClose={() => setShowProfile(false)} />}
      {showRenewalPopup && (
        <RenewalPopup
          daysLeft={user?.subscription_days_left}
          onDismiss={() => setShowRenewalPopup(false)}
          onOpenSubscription={() => { setShowRenewalPopup(false); setShowProfile(true); }}
        />
      )}
      {idleWarning && <IdleWarningModal onDismiss={dismissWarning} />}
      {showOnboarding && <OnboardingTour run={showOnboarding} onComplete={() => setShowOnboarding(false)} />}
    </div>
  );
}

export default App;
