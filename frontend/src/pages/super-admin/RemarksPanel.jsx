import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { MessageSquare, Send, Clock, Tag as TagIcon } from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

const TAG_STYLES = {
  'Follow-up': 'bg-blue-50 text-blue-700 border-blue-200',
  'Callback':  'bg-cyan-50 text-cyan-700 border-cyan-200',
  'Objection': 'bg-amber-50 text-amber-700 border-amber-200',
  'Positive':  'bg-emerald-50 text-emerald-700 border-emerald-200',
  'Negative':  'bg-red-50 text-red-700 border-red-200',
  'Info-Only': 'bg-slate-50 text-slate-600 border-slate-200',
};

/**
 * Remarks panel for prospects and leads.
 * @param {'prospect'|'lead'} targetType
 * @param {string} targetId  prospect_id for prospects, submitted_at ISO for leads
 * @param {string} token     JWT bearer token for SuperAdmin/staff
 */
export const RemarksPanel = ({ targetType, targetId, token }) => {
  const headers = { Authorization: `Bearer ${token}` };
  const [remarks, setRemarks] = useState([]);
  const [tags, setTags] = useState([]);
  const [text, setText] = useState('');
  const [tag, setTag] = useState('');
  const [loading, setLoading] = useState(false);
  const [posting, setPosting] = useState(false);

  const load = async () => {
    if (!targetId) return;
    setLoading(true);
    try {
      const r = await axios.get(`${API}/super-admin/remarks/${targetType}/${encodeURIComponent(targetId)}`, { headers });
      if (r.data?.success) {
        setRemarks(r.data.data.remarks || []);
        setTags(r.data.data.tags || []);
      }
    } catch { /* silent */ }
    setLoading(false);
  };

  useEffect(() => { load(); }, [targetType, targetId]);   // eslint-disable-line

  const submit = async () => {
    if (!text.trim()) { toast.error('Remark can\'t be empty'); return; }
    setPosting(true);
    try {
      const r = await axios.post(
        `${API}/super-admin/remarks/${targetType}/${encodeURIComponent(targetId)}`,
        { text: text.trim(), tag },
        { headers },
      );
      if (r.data?.success) {
        toast.success('Remark added');
        setText(''); setTag('');
        load();
      } else toast.error(r.data?.error || 'Failed to save');
    } catch (e) { toast.error(e.response?.data?.error || 'Failed to save'); }
    setPosting(false);
  };

  return (
    <div className="border border-slate-200 rounded-lg p-3 bg-white" data-testid={`remarks-panel-${targetType}-${targetId}`}>
      <div className="flex items-center gap-1.5 mb-2">
        <MessageSquare size={14} className="text-slate-400" />
        <span className="text-xs font-semibold text-slate-700 uppercase tracking-wide">Remarks &amp; History</span>
        <span className="text-[10px] text-slate-400 ml-auto">{remarks.length} entr{remarks.length === 1 ? 'y' : 'ies'}</span>
      </div>

      <div className="max-h-64 overflow-auto space-y-2 mb-3 pr-1" data-testid={`remarks-list-${targetType}-${targetId}`}>
        {loading && <p className="text-xs text-slate-400">Loading…</p>}
        {!loading && remarks.length === 0 && (
          <p className="text-xs text-slate-400 italic">No remarks yet. Add the first one below.</p>
        )}
        {remarks.map(r => (
          <div key={r.remark_id} className="border border-slate-100 rounded-md p-2.5 bg-slate-50/60">
            <div className="flex items-center gap-2 mb-1">
              <span className="text-[11px] font-semibold text-slate-700">{r.author_name || r.author_username}</span>
              <span className="text-[10px] text-slate-400">({r.author_role})</span>
              {r.tag && (
                <span className={`text-[9px] px-2 py-0.5 rounded-full border font-semibold uppercase ${TAG_STYLES[r.tag] || 'bg-slate-50 text-slate-500 border-slate-200'}`}>
                  <TagIcon size={9} className="inline mr-0.5 -mt-0.5" /> {r.tag}
                </span>
              )}
              <span className="ml-auto text-[10px] text-slate-400 flex items-center gap-0.5">
                <Clock size={9} /> {new Date(r.created_at).toLocaleString()}
              </span>
            </div>
            <p className="text-xs text-slate-700 leading-relaxed whitespace-pre-wrap">{r.text}</p>
          </div>
        ))}
      </div>

      <div className="space-y-2 border-t border-slate-100 pt-2.5">
        <textarea
          rows={2}
          value={text}
          onChange={e => setText(e.target.value)}
          placeholder="Add a remark…"
          className="w-full px-2.5 py-2 text-xs border border-slate-200 rounded-md resize-none focus:outline-none focus:ring-2 focus:ring-blue-100"
          data-testid={`remarks-input-${targetType}-${targetId}`}
        />
        <div className="flex items-center gap-2 flex-wrap">
          <select value={tag} onChange={e => setTag(e.target.value)}
            className="text-xs border border-slate-200 rounded-md px-2 py-1"
            data-testid={`remarks-tag-select-${targetType}-${targetId}`}>
            <option value="">No tag</option>
            {tags.map(t => <option key={t} value={t}>{t}</option>)}
          </select>
          <button onClick={submit} disabled={posting || !text.trim()}
            className="ml-auto flex items-center gap-1 px-3 py-1.5 text-xs bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50"
            data-testid={`remarks-submit-${targetType}-${targetId}`}>
            <Send size={11} /> {posting ? 'Saving…' : 'Add Remark'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default RemarksPanel;
