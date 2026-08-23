import React, { useMemo, useState } from 'react';
import axios from 'axios';
import { FileText, Pencil, ArrowUpCircle, Mail, X, Loader2 } from 'lucide-react';
import { PLANS, formatINR, formatDate } from '../utils';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

/* ── Payment-status helper ───────────────────────────────────────────
 * Derives a Paid / Partially Paid / Pending / Unpaid label per admin
 * by comparing what they've paid against what they were billed. Falls
 * back to Unpaid when the admin has no billing history yet.
 */
const paymentStatusFor = (admin) => {
  const paid = Number(admin.total_paid || 0);
  const billed = Number(admin.total_billed || 0);
  if (billed <= 0) return { label: 'Unpaid', tone: 'bg-slate-100 text-slate-500' };
  if (paid <= 0) return { label: 'Pending', tone: 'bg-amber-100 text-amber-700' };
  if (paid + 1 < billed) return { label: 'Partially Paid', tone: 'bg-orange-100 text-orange-700' };
  return { label: 'Paid', tone: 'bg-emerald-100 text-emerald-700' };
};

const SummaryCards = ({ counts }) => {
  const cards = [
    { label: 'Total Customers',    value: counts.total,    tint: 'bg-slate-50 text-slate-800',       border: 'border-slate-200' },
    { label: 'Active Subs',        value: counts.active,   tint: 'bg-emerald-50 text-emerald-700',   border: 'border-emerald-200' },
    { label: 'Trial Users',        value: counts.trial,    tint: 'bg-cyan-50 text-cyan-800',         border: 'border-cyan-200' },
    { label: 'Expiring Soon (≤30d)', value: counts.expiring, tint: 'bg-amber-50 text-amber-800',     border: 'border-amber-200' },
    { label: 'Expired',            value: counts.expired,  tint: 'bg-rose-50 text-rose-700',         border: 'border-rose-200' },
  ];
  return (
    <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-4" data-testid="sub-summary-cards">
      {cards.map((c) => (
        <div key={c.label} className={`border ${c.border} rounded-xl p-3 ${c.tint}`}>
          <div className="text-[10px] font-semibold uppercase tracking-wide opacity-70">{c.label}</div>
          <div className="text-2xl font-bold mt-1">{c.value}</div>
        </div>
      ))}
    </div>
  );
};

export const SubscriptionsTab = ({ admins, onOpenLedger, onEditAdmin, onConvertTrial, token }) => {
  const headers = { Authorization: `Bearer ${token}` };
  const [preview, setPreview] = useState(null);       // {username, day, subject, html, loading}

  const openPreview = async (username, day) => {
    setPreview({ username, day, loading: true });
    try {
      const r = await axios.get(`${API}/super-admin/trial-reminder-preview/${encodeURIComponent(username)}/${day}`, { headers });
      if (r.data?.success) setPreview({ username, day, ...r.data.data, loading: false });
      else setPreview({ username, day, loading: false, error: r.data?.error || 'Failed to load' });
    } catch (e) {
      setPreview({ username, day, loading: false, error: e.response?.data?.error || e.message });
    }
  };
  const counts = useMemo(() => {
    let active = 0, trial = 0, expiring = 0, expired = 0;
    (admins || []).forEach((a) => {
      const start = a.subscription_start || a.created_at;
      const months = a.subscription_months || 12;
      let daysLeft = null;
      if (start) {
        const end = new Date(start); end.setMonth(end.getMonth() + months);
        daysLeft = Math.ceil((end - new Date()) / 86400000);
      }
      if (a.is_trial) trial += 1;
      if (a.active && !a.is_trial) active += 1;
      if (!a.is_trial && daysLeft !== null && daysLeft < 0) expired += 1;
      else if (!a.is_trial && daysLeft !== null && daysLeft <= 30 && daysLeft >= 0) expiring += 1;
    });
    return { total: (admins || []).length, active, trial, expiring, expired };
  }, [admins]);

  return (
    <div data-testid="subscriptions-tab">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-slate-900">Subscription Management</h2>
      </div>

      <SummaryCards counts={counts} />

      <div className="bg-white border border-slate-200 rounded-xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm" data-testid="subscriptions-table">
            <thead>
              <tr className="bg-slate-50 text-xs text-slate-500 uppercase">
                <th className="py-3 px-4 text-left">Customer</th>
                <th className="py-3 px-4 text-left">Plan</th>
                <th className="py-3 px-4 text-left">Billing</th>
                <th className="py-3 px-4 text-left">Started</th>
                <th className="py-3 px-4 text-left">Expires</th>
                <th className="py-3 px-4 text-right">Value</th>
                <th className="py-3 px-4 text-center">Status</th>
                <th className="py-3 px-4 text-center">Payment</th>
                <th className="py-3 px-4 text-center">Actions</th>
              </tr>
            </thead>
            <tbody>
              {admins.map(admin => {
                const plan = admin.plan || 'starter';
                const cycle = admin.billing_cycle || 'annual';
                const months = admin.subscription_months || 12;
                const pricing = PLANS[plan] || PLANS.starter;
                const isTrial = !!admin.is_trial;
                const value = isTrial ? 0
                  : cycle === 'annual' ? (pricing.annual || 0) * (months / 12)
                                       : (pricing.monthly || 0) * months;
                const start = admin.subscription_start || admin.created_at;
                let expires = '—'; let daysLeft = null; let isExpired = false;
                if (isTrial && admin.trial_end) {
                  expires = formatDate(admin.trial_end);
                  daysLeft = Math.ceil((new Date(admin.trial_end) - new Date()) / 86400000);
                  isExpired = daysLeft < 0;
                } else if (start) {
                  const end = new Date(start); end.setMonth(end.getMonth() + months);
                  expires = formatDate(end.toISOString());
                  daysLeft = Math.ceil((end - new Date()) / 86400000);
                  isExpired = daysLeft < 0;
                }
                const ps = paymentStatusFor(admin);
                return (
                  <tr key={admin.username} className="border-t border-slate-100 hover:bg-slate-50" data-testid={`sub-row-${admin.username}`}>
                    <td className="py-3 px-4">
                      <div className="font-medium text-slate-800">{admin.name || admin.username}</div>
                      <div className="text-xs text-slate-400">{admin.username}</div>
                    </td>
                    <td className="py-3 px-4">
                      <span className={`text-[10px] px-2 py-0.5 rounded-full font-bold uppercase ${
                        isTrial ? 'bg-cyan-100 text-cyan-800' :
                        plan === 'enterprise' ? 'bg-purple-50 text-purple-700' :
                        plan === 'professional' ? 'bg-blue-50 text-blue-700' :
                        'bg-slate-100 text-slate-600'
                      }`}>
                        {isTrial ? 'TRIAL' : plan}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-slate-600 capitalize">{isTrial ? '14 days' : `${cycle} · ${months}mo`}</td>
                    <td className="py-3 px-4 text-slate-600">{formatDate(start)}</td>
                    <td className="py-3 px-4 text-slate-600">{expires}</td>
                    <td className="py-3 px-4 text-right font-medium text-slate-800">{isTrial ? 'Free' : formatINR(value)}</td>
                    <td className="py-3 px-4 text-center">
                      {isExpired ? (
                        <span className="text-[10px] bg-red-50 text-red-700 px-2 py-0.5 rounded-full font-bold">EXPIRED</span>
                      ) : daysLeft !== null && daysLeft <= 30 ? (
                        <span className="text-[10px] bg-amber-50 text-amber-700 px-2 py-0.5 rounded-full font-bold">{daysLeft}d LEFT</span>
                      ) : admin.active ? (
                        <span className="text-[10px] bg-emerald-50 text-emerald-700 px-2 py-0.5 rounded-full font-bold">ACTIVE</span>
                      ) : (
                        <span className="text-[10px] bg-slate-100 text-slate-500 px-2 py-0.5 rounded-full font-bold">INACTIVE</span>
                      )}
                    </td>
                    <td className="py-3 px-4 text-center">
                      <span className={`text-[10px] px-2 py-0.5 rounded-full font-semibold ${ps.tone}`} data-testid={`payment-status-${admin.username}`}>
                        {ps.label}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-center">
                      <div className="flex items-center justify-center gap-1">
                        {isTrial && (
                          <>
                            <button onClick={() => onConvertTrial && onConvertTrial(admin)}
                              className="p-1.5 text-cyan-600 hover:text-cyan-800 hover:bg-cyan-50 rounded-lg"
                              title="Convert Trial → Paid" data-testid={`convert-trial-${admin.username}`}>
                              <ArrowUpCircle size={14} />
                            </button>
                            <button onClick={() => openPreview(admin.username, 8)}
                              className="p-1.5 text-slate-400 hover:text-cyan-700 hover:bg-cyan-50 rounded-lg"
                              title="Preview reminder mail" data-testid={`preview-reminder-${admin.username}`}>
                              <Mail size={14} />
                            </button>
                          </>
                        )}
                        <button onClick={() => onOpenLedger(admin.username)} className="p-1.5 text-slate-400 hover:text-blue-600 hover:bg-blue-50 rounded-lg" title="View Ledger" data-testid={`ledger-${admin.username}`}>
                          <FileText size={14} />
                        </button>
                        <button onClick={() => onEditAdmin(admin)} className="p-1.5 text-slate-400 hover:text-blue-600 hover:bg-blue-50 rounded-lg" title="Edit" data-testid={`edit-sub-${admin.username}`}>
                          <Pencil size={14} />
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Trial Reminder Preview modal — day 5 / 8 / 12 / 14 toggle */}
      {preview && (
        <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-sm flex items-center justify-center p-4"
             onClick={(e) => e.target === e.currentTarget && setPreview(null)}
             data-testid="reminder-preview-modal">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-4xl max-h-[92vh] flex flex-col border border-slate-200">
            <div className="px-5 py-3 border-b border-slate-100 flex items-center justify-between">
              <div>
                <h3 className="text-sm font-semibold text-slate-800">Preview reminder mail</h3>
                <div className="text-[11px] text-slate-500 mt-0.5">
                  Rendered for <b>{preview.username}</b> · Day <b>{preview.day}</b>
                </div>
              </div>
              <button onClick={() => setPreview(null)} className="p-1 rounded hover:bg-slate-100"
                data-testid="reminder-preview-close">
                <X size={16} className="text-slate-500" />
              </button>
            </div>

            <div className="px-5 py-2 border-b border-slate-100 flex flex-wrap gap-2 items-center">
              <span className="text-xs text-slate-500 uppercase tracking-wide font-semibold">Switch day:</span>
              {[5, 8, 12, 14].map((d) => (
                <button key={d}
                  onClick={() => openPreview(preview.username, d)}
                  className={`text-xs px-3 py-1 rounded-full border ${d === preview.day ? 'bg-cyan-600 text-white border-cyan-600' : 'text-slate-600 border-slate-200 hover:bg-slate-50'}`}
                  data-testid={`preview-day-${d}`}>
                  Day {d}
                </button>
              ))}
              {preview.subject && (
                <div className="ml-auto text-xs text-slate-600 truncate max-w-[50%]" title={preview.subject}>
                  <span className="text-slate-400">Subject:</span> {preview.subject}
                </div>
              )}
            </div>

            <div className="flex-1 overflow-hidden bg-slate-50">
              {preview.loading ? (
                <div className="flex items-center justify-center h-full text-slate-500 text-sm">
                  <Loader2 className="animate-spin mr-2" size={16} /> Rendering…
                </div>
              ) : preview.error ? (
                <div className="p-6 text-rose-700 text-sm">{preview.error}</div>
              ) : (
                <iframe
                  title="Reminder preview"
                  srcDoc={preview.html}
                  className="w-full h-full min-h-[540px] bg-white"
                  sandbox=""
                  data-testid="reminder-preview-iframe"
                />
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
