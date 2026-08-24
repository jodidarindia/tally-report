import React, { useMemo, useState } from 'react';
import { AlertTriangle, Clock, Sparkles } from 'lucide-react';

export const RenewalsTab = ({ renewals, onRenew }) => {
  const [filter, setFilter] = useState('all'); // iter-122 clickable summary
  const cards = [
    { id: 'all',      label: 'Total Requests',   value: renewals.stats?.total_requests || 0,     color: 'text-slate-700' },
    { id: 'pending',  label: 'Pending',          value: renewals.stats?.pending_renewals || 0,   color: 'text-amber-600' },
    { id: 'trials',   label: 'Active Trials',    value: renewals.stats?.active_trials_count || 0, color: 'text-cyan-600' },
    { id: 'expiring', label: 'Near Expiry',      value: renewals.stats?.near_expiry_count || 0,  color: 'text-orange-600' },
    { id: 'expired',  label: 'Expired',          value: renewals.stats?.expired_count || 0,      color: 'text-red-600' },
  ];

  const showExpired = useMemo(() => filter === 'all' || filter === 'expired', [filter]);
  const showNear    = useMemo(() => filter === 'all' || filter === 'expiring', [filter]);
  const showTrials  = useMemo(() => filter === 'all' || filter === 'trials', [filter]);

  return (
  <div data-testid="renewals-tab">
    <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-6">
      {cards.map(s => {
        const active = filter === s.id;
        const clickable = ['all', 'expiring', 'expired', 'trials'].includes(s.id);
        return (
          <button
            key={s.id}
            type="button"
            disabled={!clickable}
            onClick={() => setFilter(active ? 'all' : s.id)}
            className={`bg-white border rounded-xl p-4 text-left transition-all ${active ? 'border-blue-500 ring-2 ring-blue-200 shadow-md' : 'border-slate-200'} ${clickable ? 'hover:shadow-sm cursor-pointer' : 'cursor-default opacity-90'}`}
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
            {/* iter-123: no more Convert CTA — SuperAdmin uses Edit which
                triggers Razorpay checkout inside the admin edit modal. */}
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
