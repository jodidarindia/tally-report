import React, { useState, useEffect, useRef } from 'react';
import {
  Menu, X, Building2, RefreshCw, ChevronDown, User, LogOut, PlayCircle
} from 'lucide-react';

const AppNavbar = ({
  user, navItems, currentPage, setCurrentPage,
  selectedFY, setSelectedFY, fyOptions,
  selectedCompany, companyMappings, onSwitchCompany,
  excludeBranches, onToggleBranches, branchPartyCount = 0,
  syncStatus, onLogout, onOpenProfile, onReplayTour,
  mobileMenuOpen, setMobileMenuOpen,
}) => {
  const [showUserMenu, setShowUserMenu] = useState(false);
  const userMenuRef = useRef(null);

  useEffect(() => {
    const handler = (e) => {
      if (userMenuRef.current && !userMenuRef.current.contains(e.target)) {
        setShowUserMenu(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  return (
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
                  onClick={() => (user?.companies || []).length > 1 && onSwitchCompany()}
                  className="text-[10px] sm:text-xs text-slate-500 hover:text-[#2563EB] flex items-center gap-1 leading-tight"
                  data-testid="company-switch-btn"
                >
                  <Building2 size={10} />
                  <span className="truncate max-w-[120px] sm:max-w-[200px]">{companyMappings[selectedCompany] || selectedCompany}</span>
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

          {/* Right: FY + Sync + Branch + User */}
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

            <div className="flex items-center gap-1.5" data-testid="branch-toggle-wrapper">
              <span className="text-[10px] text-slate-400 hidden sm:inline">Branch</span>
              <button
                onClick={onToggleBranches}
                className={`flex items-center gap-1.5 px-2 py-1 rounded-lg text-[10px] font-medium border transition-colors ${excludeBranches ? 'border-amber-200 bg-amber-50 text-amber-700' : 'border-green-200 bg-green-50 text-green-700'}`}
                title={excludeBranches
                  ? (branchPartyCount > 0
                      ? `Excluding ${branchPartyCount} branch/depot ledger(s) — click to include`
                      : 'Toggle ON but no branches detected for this company')
                  : `Branch/Depot sales included — click to exclude (${branchPartyCount} detected)`}
                data-testid="branch-toggle"
              >
                <div className={`w-6 h-3.5 rounded-full relative transition-colors ${excludeBranches ? 'bg-amber-500' : 'bg-green-500'}`}>
                  <div className={`absolute top-0.5 w-2.5 h-2.5 bg-white rounded-full shadow transition-transform ${excludeBranches ? 'translate-x-3' : 'translate-x-0.5'}`} />
                </div>
                <span className="hidden sm:inline whitespace-nowrap">{excludeBranches ? `Excluded${branchPartyCount > 0 ? ` (${branchPartyCount})` : ''}` : 'Included'}</span>
              </button>
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
                  <button onClick={() => { onOpenProfile(); setShowUserMenu(false); }} className="w-full px-4 py-2 text-left text-sm hover:bg-slate-50 flex items-center gap-2" data-testid="profile-btn">
                    <User size={14} className="text-slate-400" /> Profile & Security
                  </button>
                  {onReplayTour && (
                    <button
                      onClick={() => { onReplayTour(); setShowUserMenu(false); }}
                      className="w-full px-4 py-2 text-left text-sm hover:bg-slate-50 flex items-center gap-2"
                      data-testid="replay-tour-btn"
                    >
                      <PlayCircle size={14} className="text-slate-400" /> Replay Tour
                    </button>
                  )}
                  {(user?.companies || []).length > 1 && (
                    <button onClick={() => { onSwitchCompany(); setShowUserMenu(false); }} className="w-full px-4 py-2 text-left text-sm hover:bg-slate-50 flex items-center gap-2" data-testid="switch-company-btn">
                      <Building2 size={14} className="text-slate-400" /> Switch Company
                    </button>
                  )}
                  <hr className="my-1 border-slate-100" />
                  <button onClick={onLogout} className="w-full px-4 py-2 text-left text-sm hover:bg-red-50 text-red-600 flex items-center gap-2" data-testid="logout-btn">
                    <LogOut size={14} /> Logout
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

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
    </nav>
  );
};

export default AppNavbar;
