import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Building2, ChevronRight, Clock, Package, FileText } from 'lucide-react';
import AgentBadge from '../components/AgentBadge';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const timeAgo = (dateStr) => {
  if (!dateStr) return null;
  const d = (dateStr.includes('+') || dateStr.includes('Z') || dateStr.endsWith('00:00'))
    ? new Date(dateStr) : new Date(dateStr + 'Z');
  const diff = (Date.now() - d.getTime()) / 1000;
  if (diff < 60) return 'just now';
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
};

const CompanySelector = ({ companies, companyMappings = {}, onSelect }) => {
  const [selected, setSelected] = useState('');
  const [syncInfo, setSyncInfo] = useState({});

  useEffect(() => {
    if (companies && companies.length === 1) {
      onSelect(companies[0]);
    }
  }, [companies, onSelect]);

  useEffect(() => {
    if (!companies || companies.length <= 1) return;
    const fetchSyncStatus = async () => {
      try {
        const token = localStorage.getItem('flowra_token');
        const res = await axios.get(`${API}/sync/companies-status`, {
          headers: { Authorization: `Bearer ${token}` }
        });
        if (res.data?.success && res.data.data) {
          const map = {};
          res.data.data.forEach(c => { map[c.company_id] = c; });
          setSyncInfo(map);
        }
      } catch { /* ignore */ }
    };
    fetchSyncStatus();
  }, [companies]);

  if (!companies || companies.length <= 1) return null;

  const getDisplayName = (companyId) => companyMappings[companyId] || companyId;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" data-testid="company-selector-modal">
      <div className="bg-white rounded-2xl p-8 w-full max-w-lg mx-4">
        <div className="text-center mb-6">
          <div className="w-14 h-14 bg-blue-50 rounded-full flex items-center justify-center mx-auto mb-4">
            <Building2 size={28} className="text-[#2563EB]" />
          </div>
          <h2 className="text-xl font-bold text-slate-900">Select Company</h2>
          <p className="text-sm text-slate-500 mt-1">Choose which company data to view</p>
        </div>
        <div className="space-y-3 mb-6">
          {companies.map((companyId, idx) => {
            const info = syncInfo[companyId];
            const lastSyncAgo = info ? timeAgo(info.last_sync) : null;
            const displayName = getDisplayName(companyId);
            return (
              <button
                key={idx}
                onClick={() => setSelected(companyId)}
                className={`w-full p-4 rounded-xl border text-left transition-all ${
                  selected === companyId
                    ? 'border-[#2563EB] bg-blue-50 ring-2 ring-blue-100'
                    : 'border-slate-200 hover:border-slate-300 hover:bg-slate-50'
                }`}
                data-testid={`company-option-${idx}`}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <Building2 size={18} className={selected === companyId ? 'text-[#2563EB]' : 'text-slate-400'} />
                    <span className={`font-medium ${selected === companyId ? 'text-[#2563EB]' : 'text-slate-700'}`}>{displayName}</span>
                    {info?.agent_version && <AgentBadge agentVersion={info.agent_version} size="xs" />}
                  </div>
                  {selected === companyId && <ChevronRight size={18} className="text-[#2563EB]" />}
                </div>
                {info && (
                  <div className="flex items-center gap-4 mt-2 ml-8 text-xs text-slate-400">
                    {lastSyncAgo && (
                      <span className="flex items-center gap-1" data-testid={`company-sync-time-${idx}`}>
                        <Clock size={11} /> Synced {lastSyncAgo}
                      </span>
                    )}
                    {info.inventory_count > 0 && (
                      <span className="flex items-center gap-1">
                        <Package size={11} /> {info.inventory_count} items
                      </span>
                    )}
                    {info.sales_count > 0 && (
                      <span className="flex items-center gap-1">
                        <FileText size={11} /> {info.sales_count} vouchers
                      </span>
                    )}
                    {!lastSyncAgo && !info.inventory_count && !info.sales_count && (
                      <span>No data synced yet</span>
                    )}
                  </div>
                )}
              </button>
            );
          })}
        </div>
        <button
          onClick={() => selected && onSelect(selected)}
          disabled={!selected}
          className="w-full py-3 bg-[#2563EB] text-white rounded-xl font-medium hover:bg-[#1D4ED8] disabled:opacity-50 disabled:cursor-not-allowed"
          data-testid="confirm-company-selection"
        >
          Continue
        </button>
      </div>
    </div>
  );
};

export default CompanySelector;
