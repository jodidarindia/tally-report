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
          setUser(res.data.data);
          setIsAuthenticated(true);
        } else {
          localStorage.removeItem('flowra_token');
        }
      })
      .catch(() => {
        localStorage.removeItem('flowra_token');
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
    localStorage.removeItem('flowra_token');
    delete axios.defaults.headers.common['Authorization'];
  }, []);

  return { isAuthenticated, user, token, loginLoading, login, logout };
}
