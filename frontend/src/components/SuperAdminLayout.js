import React, { useState, useEffect, useRef } from 'react';
import { ChevronDown, User, Lock, LogOut } from 'lucide-react';
import SuperAdminDashboard from '../pages/SuperAdminDashboard';
import ProfileModal from '../pages/ProfileModal';

const SuperAdminLayout = ({ user, token, onLogout }) => {
  const [showProfile, setShowProfile] = useState(false);
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
    <div className="min-h-screen bg-slate-50">
      <nav className="bg-white border-b border-slate-200 sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-4 sm:px-6">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center gap-3">
              <img src="/flowra-logo.png" alt="FLOWRA" className="h-8" data-testid="navbar-logo" />
              <span className="text-lg font-bold text-slate-900">FLOWRA</span>
              <span className="px-2.5 py-0.5 rounded-full bg-red-50 text-red-700 text-xs font-semibold">Super Admin</span>
            </div>
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
                  <button onClick={onLogout} className="w-full px-4 py-2 text-left text-sm hover:bg-red-50 text-red-600 flex items-center gap-2" data-testid="logout-btn">
                    <LogOut size={14} /> Logout
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      </nav>

      <main className="p-4 sm:p-6">
        <SuperAdminDashboard token={token} />
      </main>

      <footer className="text-center py-4 text-xs text-slate-400">
        <p>&copy; {new Date().getFullYear()} JODIDAR INDIA. All rights reserved. FLOWRA is a brand owned by JODIDAR INDIA.</p>
        <p className="text-[9px] text-slate-400 mt-1 max-w-3xl mx-auto leading-relaxed" data-testid="tally-disclaimer">Tally* and Busy* are trademarks of their respective owners and are not affiliated, endorsed, connected or sponsored in any way to this website, mobile application or any of our affiliate sites. The same are used in accordance with honest practices and not used with any intention to misguide customers to take unfair advantage of the trademarks' distinct character or harm the holders' reputation.</p>
      </footer>

      {showProfile && <ProfileModal user={user} token={token} onClose={() => setShowProfile(false)} />}
    </div>
  );
};

export default SuperAdminLayout;
