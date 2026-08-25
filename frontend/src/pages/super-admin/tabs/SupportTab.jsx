import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { Inbox, Send, RefreshCw, Mail, User, MessageSquare, Clock, Filter, ExternalLink } from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

const STATUS_STYLES = {
  open:      'bg-blue-50 text-blue-700 border-blue-200',
  in_progress: 'bg-amber-50 text-amber-800 border-amber-200',
  waiting:   'bg-violet-50 text-violet-700 border-violet-200',
  closed:    'bg-emerald-50 text-emerald-700 border-emerald-200',
};

export const SupportTab = ({ token }) => {
  const headers = { Authorization: `Bearer ${token}` };
  const [tickets, setTickets] = useState([]);
  const [stats, setStats] = useState({ total: 0, open: 0, in_progress: 0, closed: 0, inbound: 0 });
  const [filter, setFilter] = useState('all');
  const [loading, setLoading] = useState(true);
  const [active, setActive] = useState(null);   // full ticket for detail pane
  const [reply, setReply] = useState('');
  const [replying, setReplying] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const r = await axios.get(`${API}/super-admin/support/tickets`, { headers });
      if (r.data?.success) {
        const list = r.data.data.tickets || [];
        setTickets(list);
        setStats({
          total: list.length,
          open: list.filter(t => t.status === 'open').length,
          in_progress: list.filter(t => t.status === 'in_progress').length,
          closed: list.filter(t => t.status === 'closed').length,
          inbound: list.filter(t => t.source === 'inbound_email').length,
        });
      }
    } catch { toast.error('Failed to load tickets'); }
    setLoading(false);
  };
  useEffect(() => { load(); }, []);   // eslint-disable-line

  const filtered = tickets.filter(t => {
    if (filter === 'all') return true;
    if (filter === 'inbound') return t.source === 'inbound_email';
    return t.status === filter;
  });

  const sendReply = async () => {
    if (!active || !reply.trim()) return;
    setReplying(true);
    try {
      const r = await axios.post(
        `${API}/support/tickets/${active.ticket_id}/messages`,
        { message: reply.trim() },
        { headers },
      );
      if (r.data?.success) {
        toast.success('Reply sent');
        setReply('');
        // The super-admin list endpoint returns each ticket with the
        // full messages array — reload and re-select the same row so
        // the just-sent reply shows up in the detail pane.
        const listR = await axios.get(`${API}/super-admin/support/tickets`, { headers });
        if (listR.data?.success) {
          const list = listR.data.data.tickets || [];
          setTickets(list);
          const refreshed = list.find(t => t.ticket_id === active.ticket_id);
          if (refreshed) setActive(refreshed);
        }
      } else toast.error(r.data?.error || 'Send failed');
    } catch (e) { toast.error(e.response?.data?.error || 'Send failed'); }
    setReplying(false);
  };

  const changeStatus = async (ticketId, status) => {
    try {
      const r = await axios.put(`${API}/support/tickets/${ticketId}/status`, { status }, { headers });
      if (r.data?.success) {
        toast.success(`Marked ${status.replace('_', ' ')}`);
        // Optimistic swap so the detail pane reflects immediately.
        setActive(a => (a ? { ...a, status } : a));
        load();
      } else toast.error(r.data?.error || 'Failed');
    } catch { toast.error('Failed'); }
  };

  return (
    <div data-testid="support-tab">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-lg font-semibold text-slate-900 flex items-center gap-2">
            <Inbox size={18} className="text-blue-600" /> Support Tickets
          </h2>
          <p className="text-xs text-slate-500 mt-0.5">
            Inbound emails to <b>support@flowralive.in</b> land here via the Resend Inbound webhook
            (endpoint: <code className="bg-slate-100 px-1 rounded">POST /api/support/inbound-email</code>).
            Tenants can also open tickets from the in-app Support widget.
          </p>
        </div>
        <button onClick={load} className="px-3 py-1.5 text-sm border border-slate-200 rounded-lg hover:bg-slate-50 flex items-center gap-1.5" data-testid="refresh-tickets">
          <RefreshCw size={14} /> Refresh
        </button>
      </div>

      {/* iter-125: clickable summary cards */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-6">
        {[
          { id: 'all',         label: 'Total',       value: stats.total,       color: 'text-slate-900' },
          { id: 'open',        label: 'Open',        value: stats.open,        color: 'text-blue-600' },
          { id: 'in_progress', label: 'In-Progress', value: stats.in_progress, color: 'text-amber-600' },
          { id: 'closed',      label: 'Closed',      value: stats.closed,      color: 'text-emerald-600' },
          { id: 'inbound',     label: 'From Email',  value: stats.inbound,     color: 'text-violet-600' },
        ].map(c => {
          const isActive = filter === c.id;
          return (
            <button key={c.id} type="button" onClick={() => setFilter(isActive ? 'all' : c.id)}
              className={`bg-white border rounded-xl p-4 text-left transition-all ${isActive ? 'border-blue-500 ring-2 ring-blue-200 shadow-md' : 'border-slate-200 hover:shadow-sm'}`}
              data-testid={`support-card-${c.id}`}>
              <div className="text-xs text-slate-500 flex items-center justify-between">
                <span>{c.label}</span>
                {isActive && c.id !== 'all' && <span className="text-blue-600 text-[10px]">● Filtered</span>}
              </div>
              <div className={`text-xl font-bold ${c.color}`}>{c.value}</div>
            </button>
          );
        })}
      </div>

      <div className="grid md:grid-cols-3 gap-4">
        {/* Ticket list */}
        <div className="md:col-span-1 bg-white border border-slate-200 rounded-xl divide-y divide-slate-100 max-h-[70vh] overflow-y-auto">
          {loading && <p className="p-6 text-sm text-slate-400">Loading…</p>}
          {!loading && filtered.length === 0 && (
            <p className="p-6 text-sm text-slate-400 text-center">
              <Mail size={24} className="mx-auto mb-2 opacity-40" />
              No tickets in this filter yet.
            </p>
          )}
          {filtered.map(t => (
            <button key={t.ticket_id} onClick={() => setActive(t)}
              className={`w-full text-left p-3 hover:bg-slate-50 ${active?.ticket_id === t.ticket_id ? 'bg-blue-50/50' : ''}`}
              data-testid={`support-row-${t.ticket_id}`}>
              <div className="flex items-center gap-2 mb-1">
                <span className={`text-[10px] px-2 py-0.5 rounded-full border font-semibold uppercase ${STATUS_STYLES[t.status] || 'bg-slate-100 text-slate-600 border-slate-200'}`}>{t.status?.replace('_',' ')}</span>
                {t.source === 'inbound_email' && (
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-violet-100 text-violet-700 font-semibold uppercase" title="Came via email">✉ Email</span>
                )}
                <span className="text-[10px] text-slate-400 ml-auto">{(t.updated_at || '').slice(0,10)}</span>
              </div>
              <h4 className="text-sm font-medium text-slate-900 truncate">{t.subject}</h4>
              <p className="text-xs text-slate-500 truncate mt-0.5">
                <User size={10} className="inline mr-1" />{t.creator_name || t.creator_username || 'guest'}
              </p>
            </button>
          ))}
        </div>

        {/* Detail pane */}
        <div className="md:col-span-2 bg-white border border-slate-200 rounded-xl p-5 min-h-[300px]">
          {!active ? (
            <div className="h-full flex items-center justify-center text-center text-slate-400 py-16">
              <div>
                <MessageSquare size={28} className="mx-auto mb-2 opacity-40" />
                <p className="text-sm">Select a ticket to view the conversation and reply.</p>
              </div>
            </div>
          ) : (
            <div>
              <div className="flex items-center justify-between mb-3">
                <div>
                  <h3 className="text-base font-semibold text-slate-900">{active.subject}</h3>
                  <p className="text-xs text-slate-500 mt-1 flex items-center gap-2">
                    <span className="flex items-center gap-1"><User size={11} /> {active.creator_name || active.creator_username}</span>
                    <span>·</span>
                    <span className="flex items-center gap-1"><Clock size={11} /> {(active.created_at || '').replace('T',' ').slice(0,16)}</span>
                    <span>·</span>
                    <span className="font-mono text-[11px] bg-slate-100 px-1.5 py-0.5 rounded">{active.ticket_id?.slice(-8)}</span>
                  </p>
                </div>
                <div className="flex items-center gap-1">
                  {['open', 'in_progress', 'waiting', 'closed'].map(s => (
                    <button key={s} onClick={() => changeStatus(active.ticket_id, s)} disabled={active.status === s}
                      className={`text-[10px] px-2 py-1 rounded border ${active.status === s ? 'border-blue-500 bg-blue-50 text-blue-700' : 'border-slate-200 text-slate-500 hover:bg-slate-50'}`}
                      data-testid={`ticket-status-${s}`}>
                      {s.replace('_',' ')}
                    </button>
                  ))}
                </div>
              </div>

              <div className="border border-slate-100 rounded-lg divide-y divide-slate-100 max-h-[45vh] overflow-y-auto">
                {(active.messages || []).map(m => (
                  <div key={m.message_id} className={`p-3 ${m.author_role === 'super_admin' || m.author_role === 'flowra_staff' ? 'bg-blue-50/40' : ''}`}>
                    <div className="flex items-center gap-2 mb-1 text-[11px]">
                      <span className="font-semibold text-slate-700">{m.author_name || m.author_username || 'unknown'}</span>
                      <span className={`px-1.5 py-0.5 rounded ${m.author_role === 'super_admin' || m.author_role === 'flowra_staff' ? 'bg-blue-100 text-blue-700' : 'bg-slate-100 text-slate-600'}`}>{m.author_role}</span>
                      <span className="text-slate-400 ml-auto">{(m.created_at || '').replace('T',' ').slice(0,16)}</span>
                    </div>
                    <p className="text-sm text-slate-700 whitespace-pre-wrap">{m.body}</p>
                  </div>
                ))}
                {!(active.messages || []).length && <p className="p-6 text-sm text-slate-400 text-center">No messages yet.</p>}
              </div>

              <div className="mt-4">
                <textarea rows={3} value={reply} onChange={e => setReply(e.target.value)}
                  placeholder="Reply to the customer (they'll receive it via email)…"
                  className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm resize-none focus:outline-none focus:ring-2 focus:ring-blue-100"
                  data-testid="support-reply-input" />
                <div className="flex justify-end mt-2">
                  <button onClick={sendReply} disabled={replying || !reply.trim()}
                    className="flex items-center gap-1 px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
                    data-testid="support-reply-btn">
                    <Send size={13} /> {replying ? 'Sending…' : 'Send Reply'}
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="mt-4 p-3 bg-slate-50 border border-slate-200 rounded-lg text-[11px] text-slate-500 flex items-center gap-2" data-testid="inbound-config-note">
        <Filter size={12} className="text-slate-400" />
        <span>
          <b>Inbound email routing:</b> configure your Resend domain to POST to&nbsp;
          <code className="bg-white px-1 rounded border border-slate-200">{`${(process.env.REACT_APP_BACKEND_URL || '').replace(/\/$/, '')}/api/support/inbound-email`}</code>&nbsp;
          on the <i>email.received</i> event.
          <a href="https://resend.com/docs/dashboard/webhooks/introduction" target="_blank" rel="noreferrer" className="text-blue-600 ml-1 inline-flex items-center gap-0.5">Docs <ExternalLink size={10} /></a>
        </span>
      </div>
    </div>
  );
};

export default SupportTab;
