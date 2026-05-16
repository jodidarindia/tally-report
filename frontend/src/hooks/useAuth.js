import { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { toast } from 'sonner';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

export function useAuth() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(null);
  const [loginLoading, setLoginLoading] = useState(false);

  // Sync token to axios header
  useEffect(() => {
    if (token) {
      axios.defaults.headers.common['Authorization'] = `Bearer ${token}`;
    }
  }, [token]);

  // Restore session on mount
  useEffect(() => {
    const savedToken = localStorage.getItem('flowra_token');
    if (!savedToken) return;

    setToken(savedToken);
    axios.defaults.headers.common['Authorization'] = `Bearer ${savedToken}`;
    axios.get(`${API}/auth/me`)
      .then(res => {
        if (res.data?.success && res.data?.data) {
          const userData = res.data.data;
          setUser(userData);
          setIsAuthenticated(true);

          // SECURITY: if the saved `flowra_company` doesn't belong to this
          // user (e.g. a different account used this browser yesterday),
          // wipe it. The backend already filters by tenant_id-from-JWT so
          // no data leak is possible, but the dropdown showing a stale
          // company name from another tenant is confusing UX.
          try {
            const savedCo = localStorage.getItem('flowra_company');
            const allowed = userData.companies || [];
            if (savedCo && !allowed.includes(savedCo)) {
              localStorage.removeItem('flowra_company');
            }
          } catch (_) { /* ignore */ }
        } else {
          // Auth /me failed — purge the stale token and any UI state too.
          try {
            const stale = [];
            for (let i = 0; i < localStorage.length; i += 1) {
              const k = localStorage.key(i);
              if (k && k.startsWith('flowra_')) stale.push(k);
            }
            stale.forEach((k) => localStorage.removeItem(k));
          } catch (_) { /* ignore */ }
        }
      })
      .catch(() => {
        // Token rejected by backend — same cleanup as above.
        try {
          const stale = [];
          for (let i = 0; i < localStorage.length; i += 1) {
            const k = localStorage.key(i);
            if (k && k.startsWith('flowra_')) stale.push(k);
          }
          stale.forEach((k) => localStorage.removeItem(k));
        } catch (_) { /* ignore */ }
      });
  }, []);

  const login = useCallback(async (username, password) => {
    if (!username.trim()) { toast.error('Please enter your User ID'); return null; }
    if (!password.trim()) { toast.error('Please enter your Password'); return null; }

    setLoginLoading(true);
    try {
      // reCAPTCHA v3 token (non-blocking)
      let captchaToken = '';
      try {
        if (window.grecaptcha?.execute) {
          captchaToken = await Promise.race([
            window.grecaptcha.execute(process.env.REACT_APP_RECAPTCHA_SITE_KEY, { action: 'login' }).catch(() => ''),
            new Promise(r => setTimeout(() => r(''), 3000))
          ]) || '';
        }
      } catch { captchaToken = ''; }

      const res = await axios.post(`${API}/auth/login`, { username, password, captcha_token: captchaToken });
      if (res.data?.success) {
        const data = res.data.data;
        // Before storing the new session, purge any leftover state from a
        // previous user (selected company, branch toggle, onboarding flag,
        // etc.). Without this, the next user briefly sees the previous
        // user's company name in the dropdown until React rehydrates.
        try {
          const stale = [];
          for (let i = 0; i < localStorage.length; i += 1) {
            const k = localStorage.key(i);
            if (k && k.startsWith('flowra_') && k !== 'flowra_token') stale.push(k);
          }
          stale.forEach((k) => localStorage.removeItem(k));
          ['auth_token', 'user_data'].forEach((k) => localStorage.removeItem(k));
        } catch (_) { /* ignore localStorage failures */ }
        setToken(data.token);
        localStorage.setItem('flowra_token', data.token);
        axios.defaults.headers.common['Authorization'] = `Bearer ${data.token}`;
        setUser(data);
        setIsAuthenticated(true);
        toast.success(`Welcome, ${data.name || data.username}!`);
        return data;
      } else {
        toast.error(res.data?.error || 'Login failed');
        return null;
      }
    } catch (err) {
      toast.error(err.response?.data?.error || 'Login failed');
      return null;
    } finally {
      setLoginLoading(false);
    }
  }, []);

  const logout = useCallback(async () => {
    try { await axios.post(`${API}/auth/logout`); } catch {}
    setIsAuthenticated(false);
    setUser(null);
    setToken(null);
    // Purge EVERY flowra_* key so no UI state (selected company, exclude-
    // branches toggle, onboarding flag, dispatch role, etc.) survives across
    // a user-switch. Prevents the "logged in as A but seeing B's stale
    // company name in the dropdown" confusion reported in the field.
    try {
      const keysToClear = [];
      for (let i = 0; i < localStorage.length; i += 1) {
        const k = localStorage.key(i);
        if (k && k.startsWith('flowra_')) keysToClear.push(k);
      }
      keysToClear.forEach((k) => localStorage.removeItem(k));
      // Common legacy keys from earlier versions — clear unconditionally.
      ['auth_token', 'user_data'].forEach((k) => localStorage.removeItem(k));
    } catch (_) { /* private-mode browsers throw on localStorage */ }
    delete axios.defaults.headers.common['Authorization'];
    delete axios.defaults.headers.common['X-Exclude-Branches'];
  }, []);

  return { isAuthenticated, user, token, loginLoading, login, logout };
}
