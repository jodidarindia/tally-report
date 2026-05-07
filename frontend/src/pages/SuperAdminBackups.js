import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { Database, Download, Trash2, Play, RefreshCw, CheckCircle2, AlertTriangle } from 'lucide-react';
import { toast } from 'sonner';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

/** SuperAdmin view: list / run / download / delete MongoDB backups. */
export default function SuperAdminBackups() {
  const [backups, setBackups] = useState([]);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [meta, setMeta] = useState({});

  const fetchBackups = useCallback(async () => {
    setLoading(true);
    try {
      const r = await axios.get(`${API}/super-admin/backups`);
      if (r.data?.success) {
        setBackups(r.data.data.backups || []);
        setMeta({ backup_dir: r.data.data.backup_dir, script: r.data.data.script });
      }
    } catch { /* ignore */ }
    setLoading(false);
  }, []);

  useEffect(() => { fetchBackups(); }, [fetchBackups]);

  const runBackup = async () => {
    setRunning(true);
    try {
      const r = await axios.post(`${API}/super-admin/backups/run`);
      if (r.data?.success) { toast.success('Backup completed'); fetchBackups(); }
      else toast.error(r.data?.error || 'Failed', { duration: 8000 });
    } catch (e) { toast.error(e.response?.data?.error || 'Backup failed'); }
    setRunning(false);
  };

  const downloadBackup = (filename) => {
    const token = localStorage.getItem('flowra_token');
    const url = `${API}/super-admin/backups/download/${filename}`;
    // Trigger download with auth header via fetch → blob
    fetch(url, { headers: { Authorization: `Bearer ${token}` } })
      .then(res => res.blob())
      .then(blob => {
        const a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = filename;
        a.click();
        URL.revokeObjectURL(a.href);
      })
      .catch(() => toast.error('Download failed'));
  };

  const deleteBackup = async (filename) => {
    if (!window.confirm(`Permanently delete ${filename}? This cannot be undone.`)) return;
    try {
      const r = await axios.delete(`${API}/super-admin/backups/${filename}`);
      if (r.data?.success) { toast.success('Deleted'); fetchBackups(); }
      else toast.error(r.data?.error || 'Failed');
    } catch { toast.error('Delete failed'); }
  };

  const fmtSize = (mb) => mb >= 1024 ? `${(mb/1024).toFixed(2)} GB` : `${mb} MB`;
  const fmtDate = (iso) => { try { return new Date(iso).toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' }); } catch { return iso; } };

  return (
    <div className="space-y-4" data-testid="superadmin-backups">
      {/* Header */}
      <div className="bg-white border border-slate-200 rounded-xl p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex items-start gap-3">
          <div className="w-10 h-10 rounded-lg bg-indigo-100 text-indigo-600 flex items-center justify-center flex-shrink-0">
            <Database size={20} />
          </div>
          <div>
            <h2 className="text-base sm:text-lg font-bold text-slate-900">MongoDB Backups</h2>
            <p className="text-xs text-slate-500 mt-0.5">Tier-1 — daily 02:00 IST cron, last 30 retained · Stored at <code className="text-[10px] bg-slate-100 px-1 py-0.5 rounded">{meta.backup_dir}</code></p>
          </div>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          <button onClick={fetchBackups} disabled={loading} className="flex items-center gap-1.5 px-3 py-2 text-xs border border-slate-200 rounded-lg hover:bg-slate-50 disabled:opacity-50" data-testid="refresh-backups">
            <RefreshCw size={13} className={loading ? 'animate-spin' : ''} /> Refresh
          </button>
          <button onClick={runBackup} disabled={running} className="flex items-center gap-1.5 px-3 py-2 text-xs bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50" data-testid="run-backup-now">
            <Play size={13} className={running ? 'animate-pulse' : ''} /> {running ? 'Running…' : 'Run Now'}
          </button>
        </div>
      </div>

      {/* Empty / loading / list */}
      {loading ? (
        <div className="flex items-center justify-center h-32"><div className="w-6 h-6 border-2 border-slate-200 border-t-indigo-600 rounded-full animate-spin" /></div>
      ) : backups.length === 0 ? (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-6 text-center" data-testid="no-backups">
          <AlertTriangle className="w-8 h-8 text-amber-500 mx-auto mb-2" />
          <h3 className="text-sm font-semibold text-amber-800">No backups yet</h3>
          <p className="text-xs text-amber-700 mt-1">Click <strong>Run Now</strong> to create the first backup, or wait for the 02:00 IST cron.</p>
          <p className="text-[10px] text-amber-600 mt-2 font-mono">Cron: <code>0 2 * * * {meta.script || '/app/scripts/backup_mongo.sh'}</code></p>
        </div>
      ) : (
        <div className="bg-white border border-slate-200 rounded-xl overflow-hidden" data-testid="backups-list">
          <div className="grid grid-cols-12 gap-2 px-3 py-2 border-b border-slate-100 bg-slate-50 text-[10px] uppercase font-bold text-slate-600">
            <div className="col-span-6 sm:col-span-7">Filename</div>
            <div className="col-span-3 sm:col-span-2 text-right">Size</div>
            <div className="col-span-3 sm:col-span-3 text-right">Actions</div>
          </div>
          {backups.map((b, i) => (
            <div key={i} className="grid grid-cols-12 gap-2 px-3 py-2.5 border-b border-slate-50 last:border-0 items-center text-xs" data-testid={`backup-row-${i}`}>
              <div className="col-span-6 sm:col-span-7 min-w-0">
                <div className="font-mono text-[10px] text-slate-700 truncate">{b.filename}</div>
                <div className="text-[10px] text-slate-400">{fmtDate(b.created_at)}</div>
              </div>
              <div className="col-span-3 sm:col-span-2 text-right text-slate-600 font-medium">{fmtSize(b.size_mb)}</div>
              <div className="col-span-3 sm:col-span-3 flex items-center justify-end gap-1">
                <button onClick={() => downloadBackup(b.filename)} className="p-1.5 text-indigo-600 hover:bg-indigo-50 rounded" title="Download" data-testid={`download-${i}`}><Download size={13} /></button>
                <button onClick={() => deleteBackup(b.filename)} className="p-1.5 text-red-500 hover:bg-red-50 rounded" title="Delete" data-testid={`delete-${i}`}><Trash2 size={13} /></button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Strategy callout */}
      <div className="bg-slate-50 border border-slate-200 rounded-xl p-3 text-[11px] text-slate-600">
        <div className="flex items-center gap-1.5 mb-1"><CheckCircle2 size={13} className="text-green-600" /> <strong>Tier 1 active</strong> — local pod backups</div>
        <p>Tier 2 (MongoDB Atlas point-in-time recovery, region: Mumbai) is the next step. See <code>/app/memory/DATABASE_STRATEGY.md</code>.</p>
      </div>
    </div>
  );
}
