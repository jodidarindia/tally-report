import React, { useMemo, useState } from 'react';
import { AlertTriangle, Clock, Sparkles, Inbox, CheckCircle2, XCircle, Hourglass } from 'lucide-react';

/*  Human-readable label for a renewal_request row's `status` field.
 *  Values persisted by the backend: pending / approved / approvedd
 *  (legacy typo — action + 'd'), rejected / rejectedd, processed. */
const statusMeta = (s = '') => {
  const raw = (s || '').toLowerCase();
  if (raw.startsWith('approve')) return { label: 'Approved', className: 'bg-emerald-50 text-emerald-700 border-emerald-200', Icon: CheckCircle2 };
  if (raw.startsWith('reject'))  return { label: 'Rejected', className: 'bg-red-50 text-red-700 border-red-200',           Icon: XCircle };
  if (raw === 'processed')       return { label: 'Processed', className: 'bg-blue-50 text-blue-700 border-blue-200',       Icon: CheckCircle2 };
  return { label: 'Pending', className: 'bg-amber-50 text-amber-800 border-amber-200', Icon: Hourglass };
};

const fmtDate = (iso = '') => {
  if (!iso) return '—';
  try { return new Date(iso).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' }); }
  catch { return iso.slice(0, 10); }
};

export const RenewalsTab = ({ renewals, onRenew, onProcessRenewal }) => {
  const [filter, setFilter] = useState('all'); // iter-122 clickable summary
  const cards = [
    { id: 'all',      label: 'Total Requests',   value: renewals.stats?.total_requests || 0,     color: 'text-slate-700' },
    { id: 'pending',  label: 'Pending',          value: renewals.stats?.pending_renewals || 0,   color: 'text-amber-600' },
    { id: 'trials',   label: 'Active Trials',    value: renewals.stats?.active_trials_count || 0, color: 'text-cyan-600' },
    { id: 'expiring', label: 'Near Expiry',      value: renewals.stats?.near_expiry_count || 0,  color: 'text-orange-600' },
    { id: 'expired',  label: 'Expired',          value: renewals.stats?.expired_count || 0,      color: 'text-red-600' },
  ];

  // iter-131: every card is now clickable so the SuperAdmin can drill
  // into any bucket. `all` also renders the raw renewal_requests
  // history table so admin actions taken are always visible.
  const showRequests = useMemo(() => filter === 'all' || filter === 'pending', [filter]);
  const showTrials   = useMemo(() => filter === 'all' || filter === 'trials', [filter]);
  const showNear     = useMemo(() => filter === 'all' || filter === 'expiring', [filter]);
  const showExpired  = useMemo(() => filter === 'all' || filter === 'expired', [filter]);

  const allRequests = renewals.renewal_requests || [];
  const displayRequests = filter === 'pending'
    ? allRequests.filter(r => (r.status || 'pending').toLowerCase() === 'pending')
    : allRequests;

  return (
  <div data-testid="renewals-tab">
    <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-6">
      {cards.map(s => {
        const active = filter === s.id;
        return (
          <button
            key={s.id}
            type="button"
            onClick={() => setFilter(active ? 'all' : s.id)}
            className={`bg-white border rounded-xl p-4 text-left transition-all cursor-pointer hover:shadow-sm ${active ? 'border-blue-500 ring-2 ring-blue-200 shadow-md' : 'border-slate-200'}`}
            data-testid={`renewal-card-${s.id}`}
          >
            <p className="text-xs text-slate-500 flex items-center justify-between">
              <span>{s.label}</span>
              {active && s.id !== 'all' && <span className="text-blue-600 text-[10px]">● Filtered</span>}
            </p>
            <p className={`text-xl font-bold ${s.color}`}>{s.value}</p>
          </button>
        );
      })}
    </div>

    {/* Renewal requests history — with status + action-taken columns.
        iter-131 fixed the "Total Requests card has no data" bug. */}
    {showRequests && (
      <div className="mb-6">
        <h3 className="text-sm font-semibold text-slate-700 mb-3 flex items-center gap-1.5">
          <Inbox size={14} /> {filter === 'pending' ? 'Pending Renewal Requests' : 'All Renewal Requests'}
          <span className="ml-2 text-[11px] font-normal text-slate-400">
            ({displayRequests.length})
          </span>
        </h3>
        {displayRequests.length === 0 ? (
          <div className="bg-white border border-slate-200 rounded-xl py-8 text-center text-sm text-slate-400" data-testid="no-renewal-requests">
            No renewal requests yet.
          </div>
        ) : (
          <div className="bg-white border border-slate-200 rounded-xl overflow-hidden">
            <table className="w-full text-sm" data-testid="renewal-requests-table">
              <thead className="bg-slate-50 border-b border-slate-200 text-[11px] uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="text-left px-4 py-2 font-semibold">Customer</th>
                  <th className="text-left px-4 py-2 font-semibold">Requested</th>
                  <th className="text-left px-4 py-2 font-semibold">Plan / Months</th>
                  <th className="text-left px-4 py-2 font-semibold">Status</th>
                  <th className="text-left px-4 py-2 font-semibold">Action Taken</th>
                  <th className="text-right px-4 py-2 font-semibold whitespace-nowrap">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {displayRequests.map(r => {
                  const s = statusMeta(r.status);
                  const isPending = s.label === 'Pending';
                  return (
                    <tr key={r.request_id || `${r.username}-${r.created_at}`} className="hover:bg-slate-50" data-testid={`renewal-req-${r.username}`}>
                      <td className="px-4 py-3">
                        <div className="font-medium text-slate-900">{r.name || r.username}</div>
                        <div className="text-[11px] text-slate-500">{r.username}</div>
                      </td>
                      <td className="px-4 py-3 text-xs text-slate-600">
                        {fmtDate(r.created_at || r.requested_at)}
                      </td>
                      <td className="px-4 py-3 text-xs">
                        <div className="font-medium text-slate-700 uppercase">{r.plan_interest || r.plan || r.current_plan || '—'}</div>
                        <div className="text-slate-400">{r.subscription_months ? `${r.subscription_months}m` : (r.current_expires ? `Expires ${fmtDate(r.current_expires)}` : '—')} {r.billing_cycle || ''}</div>
                      </td>
                      <td className="px-4 py-3">
                        <span className={`inline-flex items-center gap-1 text-[11px] px-2 py-1 rounded-full font-semibold border ${s.className}`}>
                          <s.Icon size={10} /> {s.label}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-xs">
                        {isPending ? (
                          <span className="text-slate-400 italic">Awaiting action</span>
                        ) : (
                          <div>
                            <div className="text-slate-700">
                              {r.processed_by ? <>By <b>{r.processed_by}</b></> : 'System'}
                            </div>
                            <div className="text-slate-400">{fmtDate(r.processed_at)}</div>
                            {r.admin_notes && (
                              <div className="text-slate-500 italic mt-0.5 max-w-xs truncate" title={r.admin_notes}>
                                “{r.admin_notes}”
                              </div>
                            )}
                          </div>
                        )}
                      </td>
                      <td className="px-4 py-3 text-right">
                        {isPending && onProcessRenewal && (
                          <div className="flex gap-1 justify-end">
                            <button onClick={() => onProcessRenewal(r, 'approve')}
                              className="px-2 py-1 text-[11px] bg-green-600 text-white rounded hover:bg-green-700"
                              data-testid={`approve-renewal-${r.username}`}>Approve</button>
                            <button onClick={() => onProcessRenewal(r, 'reject')}
                              className="px-2 py-1 text-[11px] border border-red-200 text-red-600 rounded hover:bg-red-50"
                              data-testid={`reject-renewal-${r.username}`}>Reject</button>
                          </div>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    )}

    {showTrials && renewals.active_trials?.length > 0 && (
      <div className="mb-6">
        <h3 className="text-sm font-semibold text-cyan-700 mb-3 flex items-center gap-1.5"><Sparkles size={14} /> Active Trials</h3>
        {renewals.active_trials.map(u => (
          <div key={u.username} className="bg-cyan-50 border border-cyan-200 rounded-xl p-4 flex items-center justify-between mb-2" data-testid={`trial-row-${u.username}`}>
            <div>
              <p className="font-medium text-cyan-900">{u.name || u.username}</p>
              <p className="text-xs text-cyan-700">{u.username} · 14-day Free Trial</p>
              <p className="text-xs text-cyan-600 mt-1">{u.days_left} days left</p>
            </div>
            <button onClick={() => onRenew(u)}
              className="px-4 py-2 bg-cyan-600 text-white rounded-lg text-xs font-medium hover:bg-cyan-700 flex items-center gap-1"
              data-testid={`edit-trial-${u.username}`}>
              Edit &amp; Convert
            </button>
          </div>
        ))}
      </div>
    )}

    {showExpired && renewals.expired?.length > 0 && (
      <div className="mb-6">
        <h3 className="text-sm font-semibold text-red-700 mb-3 flex items-center gap-1.5"><AlertTriangle size={14} /> Expired</h3>
        {renewals.expired.map(u => (
          <div key={u.username} className="bg-red-50 border border-red-200 rounded-xl p-4 flex items-center justify-between mb-2">
            <div>
              <p className="font-medium text-red-900">{u.name || u.username}</p>
              <p className="text-xs text-red-700">{u.username} | {u.plan?.toUpperCase()}</p>
              <p className="text-xs text-red-600 mt-1">Expired {Math.abs(u.days_left)} days ago</p>
            </div>
            <button onClick={() => onRenew(u)}
              className="px-4 py-2 bg-green-600 text-white rounded-lg text-xs font-medium hover:bg-green-700" data-testid={`renew-${u.username}`}>Renew</button>
          </div>
        ))}
      </div>
    )}
    {showNear && renewals.near_expiry?.length > 0 && (
      <div className="mb-6">
        <h3 className="text-sm font-semibold text-amber-700 mb-3 flex items-center gap-1.5"><Clock size={14} /> Expiring Soon</h3>
        {renewals.near_expiry.map(u => (
          <div key={u.username} className="bg-amber-50 border border-amber-200 rounded-xl p-4 flex items-center justify-between mb-2">
            <div>
              <p className="font-medium text-amber-900">{u.name || u.username}</p>
              <p className="text-xs text-amber-700">{u.username} | {u.plan?.toUpperCase()}</p>
              <p className="text-xs text-amber-600 mt-1">{u.days_left} days left</p>
            </div>
            <button onClick={() => onRenew(u)}
              className="px-4 py-2 bg-green-600 text-white rounded-lg text-xs font-medium hover:bg-green-700">Renew</button>
          </div>
        ))}
      </div>
    )}
  </div>
  );
};
