import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { Headphones, X, Send, Loader2, MessageSquare, Plus } from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

/**
 * SupportWidget — floating bottom-right button that opens a slide-out
 * panel where tenant users can raise a ticket or continue an existing
 * thread. SuperAdmin replies land in the same thread.
 */
export const SupportWidget = ({ token }) => {
  const [open, setOpen] = useState(false);
  const [tickets, setTickets] = useState([]);
  const [active, setActive] = useState(null);  // full ticket object
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState({ subject: '', message: '', priority: 'normal' });
  const [reply, setReply] = useState('');
  const [busy, setBusy] = useState(false);

  const headers = { Authorization: `Bearer ${token}` };

  const load = useCallback(async () => {
    try {
      const r = await axios.get(`${API}/support/tickets`, { headers });
      setTickets(r.data?.data?.tickets || []);
    } catch { /* silent — widget is best-effort */ }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  useEffect(() => { if (open) load(); }, [open, load]);

  const createTicket = async () => {
    if (!form.subject.trim() || !form.message.trim()) {
      toast.error('Subject and message required'); return;
    }
    setBusy(true);
    try {
      const r = await axios.post(`${API}/support/tickets`, form, { headers });
      if (r.data?.success) {
        toast.success('Ticket created');
        setCreating(false);
        setForm({ subject: '', message: '', priority: 'normal' });
        load();
      } else toast.error(r.data?.error || 'Failed to create ticket');
    } catch (e) { toast.error(e.response?.data?.error || 'Failed'); }
    finally { setBusy(false); }
  };

  const sendReply = async () => {
    if (!reply.trim() || !active) return;
    setBusy(true);
    try {
      const r = await axios.post(`${API}/support/tickets/${active.ticket_id}/messages`,
        { message: reply }, { headers });
      if (r.data?.success) {
        setActive(r.data.data);
        setReply('');
        load();
      } else toast.error(r.data?.error || 'Failed');
    } catch (e) { toast.error(e.response?.data?.error || 'Failed'); }
    finally { setBusy(false); }
  };

  if (!token) return null;
  return (
    <>
      <button
        onClick={() => setOpen((o) => !o)}
        data-testid="support-widget-toggle"
        className="fixed bottom-6 right-6 z-40 bg-blue-600 hover:bg-blue-700 text-white rounded-full p-3.5 shadow-xl hover:shadow-2xl transition-all"
        title="Support">
        <Headphones size={20} />
      </button>

      {open && (
        <div className="fixed bottom-24 right-6 z-50 bg-white rounded-2xl shadow-2xl border border-slate-200 w-96 max-h-[600px] flex flex-col" data-testid="support-widget-panel">
          <div className="px-4 py-3 border-b border-slate-100 flex items-center justify-between bg-blue-50">
            <div className="flex items-center gap-2">
              <MessageSquare size={16} className="text-blue-600" />
              <h3 className="text-sm font-semibold text-slate-800">
                {active ? 'Ticket #' + (active.ticket_id || '').slice(0, 8) : creating ? 'New Support Ticket' : 'Support'}
              </h3>
            </div>
            <button onClick={() => { if (active) setActive(null); else if (creating) setCreating(false); else setOpen(false); }}
              className="p-1 rounded hover:bg-slate-200" data-testid="support-widget-close">
              <X size={16} className="text-slate-500" />
            </button>
          </div>

          <div className="flex-1 overflow-y-auto p-4">
            {creating ? (
              <div className="space-y-3">
                <div>
                  <label className="block text-xs font-medium text-slate-600 mb-1">Subject *</label>
                  <input value={form.subject} onChange={(e) => setForm({ ...form, subject: e.target.value })}
                    className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm"
                    placeholder="What's happening?"
                    data-testid="support-form-subject" />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-600 mb-1">Priority</label>
                  <select value={form.priority} onChange={(e) => setForm({ ...form, priority: e.target.value })}
                    className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm"
                    data-testid="support-form-priority">
                    <option value="low">Low</option>
                    <option value="normal">Normal</option>
                    <option value="high">High</option>
                    <option value="urgent">Urgent</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-600 mb-1">Describe the issue *</label>
                  <textarea value={form.message} onChange={(e) => setForm({ ...form, message: e.target.value })}
                    rows={5} className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm"
                    placeholder="Steps to reproduce, screenshots you can share, anything that helps us help you faster."
                    data-testid="support-form-message" />
                </div>
              </div>
            ) : active ? (
              <div className="space-y-3">
                <div className="bg-slate-50 border border-slate-200 rounded-lg p-3">
                  <div className="text-sm font-semibold text-slate-800 mb-1">{active.subject}</div>
                  <div className="text-[10px] text-slate-500 uppercase tracking-wide">
                    Status: {active.status} · Priority: {active.priority}
                  </div>
                </div>
                {(active.messages || []).map((m) => (
                  <div key={m.message_id} className={`p-3 rounded-lg text-sm ${m.author_role === 'super_admin' ? 'bg-blue-50 border border-blue-100' : 'bg-slate-50'}`}>
                    <div className="text-[10px] font-semibold uppercase tracking-wide text-slate-500 mb-1">
                      {m.author_role === 'super_admin' ? 'FLOWRA Support' : (m.author_name || m.author_username || 'You')}
                      <span className="ml-2 text-slate-400 font-normal">
                        {m.created_at ? new Date(m.created_at).toLocaleString() : ''}
                      </span>
                    </div>
                    <div className="text-slate-700 whitespace-pre-wrap">{m.body}</div>
                  </div>
                ))}
              </div>
            ) : tickets.length === 0 ? (
              <div className="text-center text-sm text-slate-500 py-8">
                No tickets yet. Click <b>New Ticket</b> to raise your first issue — we typically reply within a few hours during working days.
              </div>
            ) : (
              <div className="space-y-2">
                {tickets.map((t) => (
                  <button key={t.ticket_id} onClick={() => setActive(t)}
                    data-testid={`support-ticket-${t.ticket_id}`}
                    className="w-full text-left p-3 border border-slate-200 rounded-lg hover:bg-slate-50">
                    <div className="flex justify-between items-start">
                      <div>
                        <div className="text-sm font-medium text-slate-800 line-clamp-1">{t.subject}</div>
                        <div className="text-[10px] text-slate-500 mt-0.5">
                          {(t.messages || []).length} message{(t.messages || []).length === 1 ? '' : 's'}
                        </div>
                      </div>
                      <span className={`text-[10px] px-2 py-0.5 rounded-full font-semibold ${
                        t.status === 'open' ? 'bg-amber-100 text-amber-800' :
                        t.status === 'pending' ? 'bg-blue-100 text-blue-800' :
                        'bg-emerald-100 text-emerald-800'
                      }`}>{t.status}</span>
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>

          <div className="p-3 border-t border-slate-100 bg-slate-50">
            {active ? (
              <div className="flex gap-2">
                <input value={reply} onChange={(e) => setReply(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && sendReply()}
                  placeholder="Type your reply…"
                  className="flex-1 px-3 py-2 border border-slate-200 rounded-lg text-sm"
                  data-testid="support-reply-input" />
                <button onClick={sendReply} disabled={busy || !reply.trim()}
                  className="px-3 py-2 bg-blue-600 text-white rounded-lg disabled:opacity-40"
                  data-testid="support-reply-send">
                  {busy ? <Loader2 className="animate-spin" size={14} /> : <Send size={14} />}
                </button>
              </div>
            ) : creating ? (
              <button onClick={createTicket} disabled={busy}
                className="w-full py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium text-sm disabled:opacity-50"
                data-testid="support-form-submit">
                {busy ? <Loader2 className="animate-spin inline mr-2" size={14} /> : null}
                Submit ticket
              </button>
            ) : (
              <button onClick={() => setCreating(true)}
                className="w-full py-2 border-2 border-blue-600 text-blue-600 rounded-lg font-medium text-sm hover:bg-blue-50 flex items-center justify-center gap-1"
                data-testid="support-new-ticket-btn">
                <Plus size={14} /> New Ticket
              </button>
            )}
          </div>
        </div>
      )}
    </>
  );
};

export default SupportWidget;
