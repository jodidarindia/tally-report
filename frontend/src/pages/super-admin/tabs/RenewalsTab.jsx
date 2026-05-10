import React from 'react';
import { AlertTriangle, Clock } from 'lucide-react';

export const RenewalsTab = ({ renewals, onRenew }) => (
  <div data-testid="renewals-tab">
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
      {[
        { label: 'Pending', value: renewals.stats?.pending_renewals || 0, color: 'text-amber-600' },
        { label: 'Near Expiry', value: renewals.stats?.near_expiry_count || 0, color: 'text-orange-600' },
        { label: 'Expired', value: renewals.stats?.expired_count || 0, color: 'text-red-600' },
        { label: 'Total Requests', value: renewals.stats?.total_requests || 0, color: 'text-slate-700' },
      ].map(s => (
        <div key={s.label} className="bg-white border border-slate-200 rounded-xl p-4">
          <p className="text-xs text-slate-500">{s.label}</p>
          <p className={`text-xl font-bold ${s.color}`}>{s.value}</p>
        </div>
      ))}
    </div>
    {renewals.expired?.length > 0 && (
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
    {renewals.near_expiry?.length > 0 && (
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
