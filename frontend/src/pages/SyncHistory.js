import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { RefreshCw, Clock, Database, CheckCircle, AlertCircle, AlertTriangle, ChevronDown, ChevronUp } from 'lucide-react';
import { toast } from 'sonner';
import AgentBadge from '../components/AgentBadge';
import { getErpLabelMarked } from '../utils/agentSource';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const DATA_TYPE_LABELS = {
  inventory: { label: 'Inventory', color: 'bg-blue-100 text-blue-700' },
  sales: { label: 'Sales', color: 'bg-emerald-100 text-emerald-700' },
  receipts: { label: 'Receipts', color: 'bg-violet-100 text-violet-700' },
  credit_notes: { label: 'Credit Notes', color: 'bg-amber-100 text-amber-700' },
  journal_vouchers: { label: 'Journals', color: 'bg-rose-100 text-rose-700' },
  stock_journals: { label: 'Stock Journals', color: 'bg-cyan-100 text-cyan-700' },
  customers: { label: 'Customers', color: 'bg-indigo-100 text-indigo-700' }
};

const SyncHistory = () => {
  const [cycles, setCycles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [expandedCycle, setExpandedCycle] = useState(null);
  const [currentStatus, setCurrentStatus] = useState(null);

  useEffect(() => {
    fetchHistory();
    fetchCurrentStatus();
  }, []);

  const fetchHistory = async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${API}/sync/history`);
      setCycles(res.data?.data?.cycles || []);
    } catch (error) {
      toast.error('Failed to load sync history');
    } finally {
      setLoading(false);
    }
  };

  const fetchCurrentStatus = async () => {
    try {
      const [syncRes, tallyRes] = await Promise.all([
        axios.get(`${API}/sync/status`).catch(() => null),
        axios.get(`${API}/tally/status`).catch(() => null)
      ]);
      setCurrentStatus({
        ...(syncRes?.data?.data || {}),
        is_connected: tallyRes?.data?.data?.is_connected || false,
        agent_version: tallyRes?.data?.data?.agent_version || ''
      });
    } catch (e) {
      console.error(e);
    }
  };

  const formatDate = (ts) => {
    if (!ts) return '-';
    try {
      // Normalize: treat naive timestamps (no timezone marker) as UTC
      const d = (ts.includes('+') || ts.includes('Z') || ts.endsWith('00:00'))
        ? new Date(ts) : new Date(ts + 'Z');
      return d.toLocaleString('en-IN', {
        day: '2-digit', month: 'short', year: 'numeric',
        hour: '2-digit', minute: '2-digit', second: '2-digit',
        timeZone: 'Asia/Kolkata'
      });
    } catch { return ts; }
  };

  const getTotalCount = (dataTypes) => {
    return Object.values(dataTypes || {}).reduce((sum, count) => sum + count, 0);
  };

  return (
    <div data-testid="sync-history-page">
      <div className="mb-8">
        <h1 className="text-4xl font-light tracking-tight text-slate-900" style={{ fontFamily: 'Outfit, sans-serif' }}>
          Sync History
        </h1>
        <p className="mt-2 text-base text-slate-600">Timeline of all data sync cycles from {getErpLabelMarked()}</p>
      </div>

      {/* Current Status Card */}
      {currentStatus && (
        <div className="bg-white border border-slate-200 rounded-xl p-6 mb-6" data-testid="current-sync-status">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className={`w-3 h-3 rounded-full ${currentStatus.is_connected ? 'bg-emerald-500 animate-pulse' : 'bg-red-500'}`} />
              <div>
                <div className="text-sm font-medium text-slate-900 flex items-center gap-2">
                  {currentStatus.company_name || 'Tally* Connection'}
                  {currentStatus.agent_version && <AgentBadge agentVersion={currentStatus.agent_version} size="xs" />}
                </div>
                <div className="text-xs text-slate-500">
                  Last sync: {formatDate(currentStatus.last_sync)}
                </div>
              </div>
            </div>
            <button
              onClick={() => { fetchHistory(); fetchCurrentStatus(); }}
              className="px-4 py-2 text-sm rounded-lg border border-slate-200 hover:bg-slate-50 flex items-center gap-2"
              data-testid="refresh-history-btn"
            >
              <RefreshCw size={14} /> Refresh
            </button>
          </div>
        </div>
      )}

      {/* Timeline */}
      {loading ? (
        <div className="flex items-center justify-center h-64"><div className="loading-spinner" /></div>
      ) : cycles.length === 0 ? (
        <div className="text-center py-16 text-slate-500">
          <Database size={48} className="mx-auto mb-4 opacity-30" />
          <p className="text-lg">No sync history yet</p>
          <p className="text-sm mt-2">Run the desktop agent to start syncing data from {getErpLabelMarked()}</p>
        </div>
      ) : (
        <div className="space-y-3" data-testid="sync-timeline">
          {cycles.map((cycle, idx) => {
            const isExpanded = expandedCycle === idx;
            const totalItems = getTotalCount(cycle.data_types);
            const isRecent = idx === 0;

            return (
              <div
                key={idx}
                className={`bg-white border rounded-xl overflow-hidden transition-all ${
                  cycle.had_errors
                    ? 'border-red-300 ring-1 ring-red-100'
                    : isRecent ? 'border-[#2563EB] ring-1 ring-[#2563EB]/20' : 'border-slate-200'
                }`}
                data-testid={`sync-cycle-${idx}`}
              >
                <div
                  className="flex items-center justify-between p-4 cursor-pointer hover:bg-slate-50"
                  onClick={() => setExpandedCycle(isExpanded ? null : idx)}
                >
                  <div className="flex items-center gap-4">
                    <div className={`w-10 h-10 rounded-full flex items-center justify-center ${
                      isRecent ? 'bg-[#2563EB] text-white' : 'bg-slate-100 text-slate-500'
                    }`}>
                      {isRecent ? <CheckCircle size={18} /> : <Clock size={18} />}
                    </div>
                    <div>
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-sm font-semibold text-slate-900">
                          {formatDate(cycle.timestamp)}
                        </span>
                        {isRecent && (
                          <span className="px-2 py-0.5 text-[10px] font-bold rounded-full bg-[#2563EB] text-white">LATEST</span>
                        )}
                        <span className={`px-2 py-0.5 text-[10px] font-medium rounded-full ${
                          cycle.sync_mode === 'incremental' ? 'bg-amber-100 text-amber-700' : 'bg-green-100 text-green-700'
                        }`}>
                          {cycle.sync_mode || 'full'}
                        </span>
                        {cycle.had_errors && (
                          <span
                            className="px-2 py-0.5 text-[10px] font-bold rounded-full bg-red-100 text-red-700 border border-red-200 flex items-center gap-1"
                            title={cycle.failed_phases?.length
                              ? `Failed phases: ${cycle.failed_phases.map(f => f.phase).join(', ')}`
                              : 'One or more phases failed during this sync cycle'}
                            data-testid={`cycle-incomplete-badge-${idx}`}
                          >
                            <AlertTriangle size={10} /> SYNC INCOMPLETE
                          </span>
                        )}
                      </div>
                      <div className="text-xs text-slate-500 mt-1">
                        FY {cycle.financial_year || '-'} | {totalItems.toLocaleString()} items synced | {Object.keys(cycle.data_types).length} data types
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <div className="flex gap-1.5 flex-wrap justify-end max-w-[300px]">
                      {Object.entries(cycle.data_types || {}).map(([dtype, count]) => {
                        const cfg = DATA_TYPE_LABELS[dtype] || { label: dtype, color: 'bg-slate-100 text-slate-600' };
                        return (
                          <span key={dtype} className={`px-2 py-0.5 rounded-full text-[10px] font-medium ${cfg.color}`}>
                            {cfg.label}: {count}
                          </span>
                        );
                      })}
                    </div>
                    {isExpanded ? <ChevronUp size={16} className="text-slate-400" /> : <ChevronDown size={16} className="text-slate-400" />}
                  </div>
                </div>

                {isExpanded && (
                  <div className="border-t border-slate-100 p-4 bg-slate-50">
                    {cycle.had_errors && cycle.failed_phases?.length > 0 && (
                      <div className="mb-4 bg-red-50 border border-red-200 rounded-lg p-3" data-testid={`cycle-failed-phases-${idx}`}>
                        <div className="flex items-center gap-2 text-xs font-bold text-red-700 mb-2">
                          <AlertTriangle size={12} /> Failed phases ({cycle.failed_phases.length})
                        </div>
                        <ul className="space-y-1">
                          {cycle.failed_phases.map((f, j) => (
                            <li key={j} className="text-xs text-red-700 flex items-start gap-2">
                              <span className="font-mono bg-red-100 px-1.5 py-0.5 rounded text-[10px]">{f.phase}</span>
                              <span className="text-red-600">{f.reason || 'unknown'}</span>
                              {f.count > 1 && <span className="text-red-400">×{f.count}</span>}
                            </li>
                          ))}
                        </ul>
                        <p className="text-[10px] text-red-500 mt-2">Re-run the agent — successful phases will skip via hash-match; only the failed types will retry.</p>
                      </div>
                    )}
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                      {Object.entries(cycle.data_types || {}).map(([dtype, count]) => {
                        const cfg = DATA_TYPE_LABELS[dtype] || { label: dtype, color: 'bg-slate-100 text-slate-600' };
                        return (
                          <div key={dtype} className="bg-white rounded-lg border border-slate-200 p-4 text-center">
                            <div className="text-2xl font-bold text-slate-900">{count.toLocaleString()}</div>
                            <div className={`mt-1 inline-block px-2 py-0.5 rounded-full text-xs font-medium ${cfg.color}`}>
                              {cfg.label}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                    <div className="mt-3 flex gap-4 text-xs text-slate-500 items-center">
                      <span>Company: {cycle.company_name || '-'}</span>
                      {cycle.agent_version
                        ? <AgentBadge agentVersion={cycle.agent_version} size="xs" />
                        : <span>Agent: -</span>}
                      <span>Mode: {cycle.sync_mode || 'full'}</span>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

export default SyncHistory;
