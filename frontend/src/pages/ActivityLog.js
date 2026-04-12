import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { Clock, Filter, User, Shield, Key, ToggleRight, Trash2, Download, LogIn, RefreshCw } from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const ACTION_ICONS = {
  login: LogIn,
  login_failed: Shield,
  password_change: Key,
  password_reset: Key,
  admin_created: User,
  admin_deleted: Trash2,
  admin_toggled: ToggleRight,
  features_updated: Filter,
  data_export: Download,
};

const ACTION_COLORS = {
  login: 'bg-green-50 text-green-700',
  login_failed: 'bg-red-50 text-red-600',
  password_change: 'bg-amber-50 text-amber-700',
  password_reset: 'bg-amber-50 text-amber-700',
  admin_created: 'bg-blue-50 text-blue-700',
  admin_deleted: 'bg-red-50 text-red-600',
  admin_toggled: 'bg-purple-50 text-purple-700',
  features_updated: 'bg-indigo-50 text-indigo-700',
  data_export: 'bg-teal-50 text-teal-700',
};

const timeAgo = (ts) => {
  if (!ts) return '';
  const diff = (Date.now() - new Date(ts).getTime()) / 1000;
  if (diff < 60) return 'just now';
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  const dt = (ts.includes('+') || ts.includes('Z')) ? new Date(ts) : new Date(ts + 'Z');
  return dt.toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit', timeZone: 'Asia/Kolkata' });
};

const ActivityLog = ({ token, role }) => {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [actionFilter, setActionFilter] = useState('');
  const [actionTypes, setActionTypes] = useState([]);

  const headers = { Authorization: `Bearer ${token}` };

  const fetchLogs = useCallback(async () => {
    setLoading(true);
    try {
      const params = {};
      if (actionFilter) params.action = actionFilter;
      const res = await axios.get(`${API}/audit/logs`, { headers, params });
      if (res.data?.success) {
        setLogs(res.data.data.logs || []);
      }
    } catch { /* ignore */ }
    setLoading(false);
  }, [token, actionFilter]);

  const fetchActionTypes = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/audit/actions`, { headers });
      if (res.data?.success) {
        setActionTypes(res.data.data.actions || []);
      }
    } catch { /* ignore */ }
  }, [token]);

  useEffect(() => { fetchLogs(); fetchActionTypes(); }, [fetchLogs, fetchActionTypes]);

  return (
    <div data-testid="activity-log">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-lg font-semibold text-slate-900">Activity Log</h2>
          <p className="text-sm text-slate-500">{role === 'super_admin' ? 'All tenant activity' : 'Your tenant activity'}</p>
        </div>
        <div className="flex items-center gap-3">
          <select
            value={actionFilter}
            onChange={e => setActionFilter(e.target.value)}
            className="text-sm border border-slate-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-[#2563EB]"
            data-testid="activity-filter"
          >
            <option value="">All Actions</option>
            {actionTypes.map(a => (
              <option key={a} value={a}>{a.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}</option>
            ))}
          </select>
          <button onClick={fetchLogs} className="p-2 text-slate-400 hover:text-slate-600 hover:bg-slate-50 rounded-lg" data-testid="refresh-activity">
            <RefreshCw size={16} />
          </button>
        </div>
      </div>

      {loading ? (
        <div className="text-center py-12 text-slate-400">Loading activity...</div>
      ) : logs.length === 0 ? (
        <div className="text-center py-12 text-slate-400">No activity recorded yet</div>
      ) : (
        <div className="space-y-1">
          {logs.map((log, idx) => {
            const Icon = ACTION_ICONS[log.action] || Clock;
            const colorClass = ACTION_COLORS[log.action] || 'bg-slate-50 text-slate-600';
            return (
              <div key={idx} className="flex items-start gap-3 p-3 rounded-lg hover:bg-slate-50 transition-colors" data-testid={`activity-row-${idx}`}>
                <div className={`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 ${colorClass}`}>
                  <Icon size={14} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-medium text-sm text-slate-800">{log.actor}</span>
                    <span className="text-xs px-2 py-0.5 rounded-full bg-slate-100 text-slate-600">
                      {log.action.replace(/_/g, ' ')}
                    </span>
                    {log.target && (
                      <span className="text-xs text-slate-500">on <span className="font-medium">{log.target}</span></span>
                    )}
                  </div>
                  <div className="flex items-center gap-3 mt-0.5">
                    {log.details && <span className="text-xs text-slate-400 truncate max-w-xs">{log.details}</span>}
                    {log.ip_address && log.ip_address !== 'unknown' && (
                      <span className="text-xs text-slate-300">IP: {log.ip_address}</span>
                    )}
                  </div>
                </div>
                <span className="text-xs text-slate-400 flex-shrink-0 whitespace-nowrap">{timeAgo(log.timestamp)}</span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

export default ActivityLog;
