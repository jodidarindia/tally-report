import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { Tag, Plus, X, Save, RotateCcw, Info } from 'lucide-react';
import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

/**
 * Per-tenant configurable creditor-group list.
 *
 * Some Tally tenants use custom group names ("Dealer Deposit", "MP Distributor",
 * "Local Vendor", etc.) instead of the reserved "Sundry Creditors" group. This
 * panel lets the admin pick which group names should be treated as creditors
 * across CA Corner, Balance Sheet, and the new /api/creditors endpoint —
 * without re-syncing or editing Tally masters.
 */
const CreditorGroupsPanel = () => {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [selected, setSelected] = useState([]);
  const [available, setAvailable] = useState([]);
  const [defaults, setDefaults] = useState([]);
  const [filter, setFilter] = useState('');

  const fetchConfig = useCallback(async () => {
    setLoading(true);
    try {
      const r = await axios.get(`${API}/creditors/config`);
      if (r.data?.success) {
        setSelected(r.data.data.creditor_groups || []);
        setAvailable(r.data.data.available_groups || []);
        setDefaults(r.data.data.defaults || []);
      } else {
        toast.error(r.data?.error || 'Could not load creditor groups');
      }
    } catch (e) {
      toast.error('Failed to load creditor groups');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchConfig(); }, [fetchConfig]);

  const addGroup = (g) => {
    if (!g || selected.includes(g)) return;
    setSelected([...selected, g]);
  };

  const removeGroup = (g) => setSelected(selected.filter(x => x !== g));

  const restoreDefaults = () => setSelected([...defaults]);

  const save = async () => {
    setSaving(true);
    try {
      const r = await axios.post(`${API}/creditors/config`, { creditor_groups: selected });
      if (r.data?.success) {
        toast.success(`Saved ${selected.length} creditor groups`);
        fetchConfig();
      } else {
        toast.error(r.data?.error || 'Save failed');
      }
    } catch (e) {
      toast.error('Save failed');
    } finally {
      setSaving(false);
    }
  };

  const filteredAvailable = filter
    ? available.filter(g => g.toLowerCase().includes(filter.toLowerCase()) && !selected.includes(g))
    : available.filter(g => !selected.includes(g));

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-5" data-testid="creditor-groups-panel">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Tag size={18} className="text-purple-600" />
          <h3 className="text-base font-semibold text-slate-800">Creditor Groups</h3>
        </div>
        <button
          onClick={restoreDefaults}
          className="text-xs text-slate-500 hover:text-slate-800 flex items-center gap-1"
          data-testid="creditor-groups-restore-defaults"
        >
          <RotateCcw size={12} /> Restore defaults
        </button>
      </div>

      <div className="bg-blue-50 border border-blue-200 rounded-lg px-3 py-2 mb-4 flex gap-2 items-start">
        <Info size={14} className="text-blue-600 mt-0.5 shrink-0" />
        <p className="text-xs text-blue-900 leading-relaxed">
          Pick which Tally <span className="font-medium">parent groups</span> should count as creditors.
          Defaults work for most setups. If your Tally uses custom names like <span className="font-mono text-[11px] bg-white px-1 rounded">Dealer Deposit</span> or
          <span className="font-mono text-[11px] bg-white px-1 rounded ml-1">Local Vendor</span>, add them here. Updates apply instantly — no re-sync needed.
        </p>
      </div>

      {loading ? (
        <p className="text-sm text-slate-500 py-6 text-center">Loading…</p>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Selected (left) */}
          <div>
            <p className="text-xs font-medium text-slate-600 mb-2">
              Counted as creditors ({selected.length})
            </p>
            <div className="border border-slate-200 rounded-lg p-2 min-h-[180px] max-h-[280px] overflow-y-auto" data-testid="creditor-groups-selected">
              {selected.length === 0 && (
                <p className="text-xs text-slate-400 italic py-4 text-center">No groups selected — Sundry Creditors is implied</p>
              )}
              {selected.map(g => (
                <div
                  key={g}
                  className="flex items-center justify-between bg-purple-50 border border-purple-200 rounded-md px-2 py-1.5 mb-1.5 group"
                  data-testid={`creditor-group-selected-${g.replace(/\s+/g, '-').toLowerCase()}`}
                >
                  <span className="text-sm text-slate-800 truncate">{g}</span>
                  <button
                    onClick={() => removeGroup(g)}
                    className="text-slate-400 hover:text-red-600 transition-colors"
                    aria-label={`Remove ${g}`}
                  >
                    <X size={14} />
                  </button>
                </div>
              ))}
            </div>
          </div>

          {/* Available (right) */}
          <div>
            <p className="text-xs font-medium text-slate-600 mb-2">
              Available groups in your Tally ({filteredAvailable.length})
            </p>
            <input
              type="text"
              placeholder="Search…"
              value={filter}
              onChange={e => setFilter(e.target.value)}
              className="w-full text-sm border border-slate-200 rounded-md px-2 py-1.5 mb-2 focus:outline-none focus:ring-2 focus:ring-purple-200"
              data-testid="creditor-groups-search"
            />
            <div className="border border-slate-200 rounded-lg p-2 min-h-[140px] max-h-[240px] overflow-y-auto" data-testid="creditor-groups-available">
              {filteredAvailable.length === 0 && (
                <p className="text-xs text-slate-400 italic py-4 text-center">
                  {filter ? 'No matches' : 'All groups already added'}
                </p>
              )}
              {filteredAvailable.map(g => (
                <button
                  key={g}
                  onClick={() => addGroup(g)}
                  className="w-full flex items-center justify-between text-left text-sm text-slate-700 hover:bg-slate-50 px-2 py-1.5 rounded-md mb-0.5 group"
                  data-testid={`creditor-group-available-${g.replace(/\s+/g, '-').toLowerCase()}`}
                >
                  <span className="truncate">{g}</span>
                  <Plus size={14} className="text-slate-300 group-hover:text-purple-600" />
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      <div className="mt-4 pt-3 border-t border-slate-100 flex justify-end gap-2">
        <button
          onClick={fetchConfig}
          className="text-xs text-slate-600 hover:text-slate-900 px-3 py-1.5"
          data-testid="creditor-groups-refresh"
        >
          Discard
        </button>
        <button
          onClick={save}
          disabled={saving}
          className="bg-purple-600 hover:bg-purple-700 disabled:opacity-50 text-white text-xs font-medium px-4 py-1.5 rounded-md flex items-center gap-1.5"
          data-testid="creditor-groups-save"
        >
          <Save size={12} /> {saving ? 'Saving…' : 'Save'}
        </button>
      </div>
    </div>
  );
};

export default CreditorGroupsPanel;
