import React from 'react';
import { FileText, Pencil } from 'lucide-react';
import { PLANS, formatINR, formatDate } from '../utils';

export const SubscriptionsTab = ({ admins, onOpenLedger, onEditAdmin }) => (
  <div data-testid="subscriptions-tab">
    <div className="flex items-center justify-between mb-4">
      <h2 className="text-lg font-semibold text-slate-900">Subscription Management</h2>
    </div>
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
              <th className="py-3 px-4 text-center">Actions</th>
            </tr>
          </thead>
          <tbody>
            {admins.map(admin => {
              const plan = admin.plan || 'enterprise';
              const cycle = admin.billing_cycle || 'annual';
              const months = admin.subscription_months || 12;
              const pricing = PLANS[plan] || PLANS.enterprise;
              const value = cycle === 'annual' ? pricing.annual * (months / 12) : pricing.monthly * months;
              const start = admin.subscription_start || admin.created_at;
              let expires = '—'; let daysLeft = null; let isExpired = false;
              if (start) {
                const end = new Date(start); end.setMonth(end.getMonth() + months);
                expires = formatDate(end.toISOString());
                daysLeft = Math.ceil((end - new Date()) / 86400000);
                isExpired = daysLeft < 0;
              }
              return (
                <tr key={admin.username} className="border-t border-slate-100 hover:bg-slate-50" data-testid={`sub-row-${admin.username}`}>
                  <td className="py-3 px-4">
                    <div className="font-medium text-slate-800">{admin.name || admin.username}</div>
                    <div className="text-xs text-slate-400">{admin.username}</div>
                  </td>
                  <td className="py-3 px-4">
                    <span className={`text-[10px] px-2 py-0.5 rounded-full font-bold uppercase ${plan === 'enterprise' ? 'bg-purple-50 text-purple-700' : plan === 'professional' ? 'bg-blue-50 text-blue-700' : 'bg-slate-100 text-slate-600'}`}>
                      {plan}
                    </span>
                  </td>
                  <td className="py-3 px-4 text-slate-600 capitalize">{cycle} · {months}mo</td>
                  <td className="py-3 px-4 text-slate-600">{formatDate(start)}</td>
                  <td className="py-3 px-4 text-slate-600">{expires}</td>
                  <td className="py-3 px-4 text-right font-medium text-slate-800">{formatINR(value)}</td>
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
                    <div className="flex items-center justify-center gap-1">
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
  </div>
);
