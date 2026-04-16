import { useState, useEffect, useCallback } from 'react';
import axios from 'axios';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

const getCurrentFY = () => {
  const now = new Date();
  const month = now.getMonth();
  const year = now.getFullYear();
  return month >= 3 ? `${year}-${String(year + 1).slice(2)}` : `${year - 1}-${String(year).slice(2)}`;
};

export function useCompany(isAuthenticated) {
  const [selectedFY, setSelectedFY] = useState(getCurrentFY());
  const [selectedCompany, setSelectedCompany] = useState('');
  const [companyMappings, setCompanyMappings] = useState({});
  const [excludeBranches, setExcludeBranches] = useState(() => {
    const saved = localStorage.getItem('flowra_exclude_branches') === 'true';
    // Set header immediately on initialization (not just in useEffect)
    if (saved) {
      axios.defaults.headers.common['X-Exclude-Branches'] = 'true';
    } else {
      delete axios.defaults.headers.common['X-Exclude-Branches'];
    }
    return saved;
  });
  const [showCompanySelector, setShowCompanySelector] = useState(false);

  // Sync X-Company-ID header
  useEffect(() => {
    if (selectedCompany) {
      axios.defaults.headers.common['X-Company-ID'] = selectedCompany;
    } else {
      delete axios.defaults.headers.common['X-Company-ID'];
    }
  }, [selectedCompany]);

  // Sync X-Exclude-Branches header
  useEffect(() => {
    if (excludeBranches) {
      axios.defaults.headers.common['X-Exclude-Branches'] = 'true';
    } else {
      delete axios.defaults.headers.common['X-Exclude-Branches'];
    }
    localStorage.setItem('flowra_exclude_branches', excludeBranches ? 'true' : 'false');
  }, [excludeBranches]);

  // Auto-detect branch ledgers on company change
  useEffect(() => {
    if (selectedCompany && isAuthenticated) {
      axios.get(`${API}/settings/branch-ledgers/detect`).catch(() => {});
    }
  }, [selectedCompany, isAuthenticated]);

  const selectCompany = useCallback((company) => {
    setSelectedCompany(company);
    localStorage.setItem('flowra_company', company);
    setShowCompanySelector(false);
  }, []);

  const toggleBranches = useCallback(() => {
    setExcludeBranches(prev => {
      const next = !prev;
      if (next) {
        axios.defaults.headers.common['X-Exclude-Branches'] = 'true';
      } else {
        delete axios.defaults.headers.common['X-Exclude-Branches'];
      }
      localStorage.setItem('flowra_exclude_branches', next ? 'true' : 'false');
      return next;
    });
  }, []);

  // Initialize company state from user data (called after login / session restore)
  const initFromUser = useCallback((userData) => {
    if (userData.company_mappings) {
      const map = {};
      userData.company_mappings.forEach(m => { map[m.company_id] = m.company_name; });
      setCompanyMappings(map);
    }

    if (userData.role === 'super_admin') return;

    // Fetch latest FY
    axios.get(`${API}/sync/latest-fy`).then(fyRes => {
      if (fyRes.data?.success && fyRes.data?.data?.latest_fy) {
        setSelectedFY(fyRes.data.data.latest_fy);
      }
    }).catch(() => {});

    // Resolve company from saved preference or user's company list
    const savedCompany = localStorage.getItem('flowra_company');
    const companies = userData.companies || [];
    if (savedCompany && companies.includes(savedCompany)) {
      setSelectedCompany(savedCompany);
    } else if (companies.length > 1) {
      setShowCompanySelector(true);
    } else if (companies.length === 1) {
      setSelectedCompany(companies[0]);
      localStorage.setItem('flowra_company', companies[0]);
    }
  }, []);

  const resetCompany = useCallback(() => {
    setSelectedCompany('');
    setCompanyMappings({});
    setShowCompanySelector(false);
    localStorage.removeItem('flowra_company');
  }, []);

  return {
    selectedFY, setSelectedFY,
    selectedCompany, selectCompany, resetCompany,
    companyMappings,
    excludeBranches, toggleBranches,
    showCompanySelector, setShowCompanySelector,
    initFromUser,
  };
}
