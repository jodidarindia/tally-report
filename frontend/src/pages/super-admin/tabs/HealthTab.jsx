import React from 'react';
import { FileText } from 'lucide-react';
import { formatINR, formatDate } from '../utils';

export const HealthTab = ({ healthData, onOpenLedger }) => (
  <div data-testid="health-tab">
    <h2 className="text-lg font-semibold text-slate-900 mb-4">Customer Health Monitor</h2>
    <div className="bg-white border border-slate-200 rounded-xl overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-sm" data-testid="health-table">
          <thead>
            <tr className="bg-slate-50 text-xs text-slate-500 uppercase">
              <th className="py-3 px-4 text-left">Customer</th>
              <th className="py-3 px-4 text-center">Health</th>
              <th className="py-3 px-4 text-left">Last Sync</th>
              <th className="py-3 px-4 text-right">Items</th>
              <th className="py-3 px-4 text-right">Sales</th>
              <th className="py-3 px-4 text-right">Customers</th>
              <th className="py-3 px-4 text-right">Paid</th>
              <th className="py-3 px-4 text-left">Sub Expires</th>
              <th className="py-3 px-4 text-center">Actions</th>
            </tr>
          </thead>
          <tbody>
            {healthData.map((h, i) => {
              const statusColors = { active: 'bg-emerald-50 text-emerald-700', moderate: 'bg-amber-50 text-amber-700', inactive: 'bg-red-50 text-red-700', never_synced: 'bg-slate-100 text-slate-500' };
              const sb = h.staff_breakdown || {};
              const sbBits = [
                sb.salesman ? `${sb.salesman} sm` : null,
                sb.dispatch ? `${sb.dispatch} dp` : null,
                sb.employee ? `${sb.employee} emp` : null,
              ].filter(Boolean).join(' · ');
              const empLabel = sbBits ? `${h.employee_count} (${sbBits})` : `${h.employee_count}`;
              return (
                <tr key={i} className="border-t border-slate-100 hover:bg-slate-50" data-testid={`health-row-${i}`}>
                  <td className="py-3 px-4">
                    <div className="font-medium text-slate-800">{h.name || h.username}</div>
                    <div className="text-xs text-slate-400" title={`${h.employee_count} non-admin users · ${sbBits || 'none'}`}>
                      {h.plan} · {empLabel} emp · {h.companies?.join(', ') || '—'}
                    </div>
                    {(h.beat_runs || h.salesman_orders || h.dispatch_cards) ? (
                      <div className="flex flex-wrap gap-1 mt-1">
                        {h.beat_runs > 0 && <span className="text-[9px] px-1.5 py-0.5 bg-purple-50 text-purple-700 rounded">Beat {h.beat_runs}</span>}
                        {h.salesman_orders > 0 && <span className="text-[9px] px-1.5 py-0.5 bg-blue-50 text-blue-700 rounded">Orders {h.salesman_orders}</span>}
                        {h.dispatch_cards > 0 && <span className="text-[9px] px-1.5 py-0.5 bg-amber-50 text-amber-700 rounded">Dispatch {h.dispatch_cards}</span>}
                      </div>
                    ) : null}
                  </td>
                  <td className="py-3 px-4 text-center">
                    <span className={`text-[10px] px-2 py-0.5 rounded-full font-bold uppercase ${statusColors[h.health_status] || 'bg-slate-100 text-slate-500'}`}>
                      {h.health_status?.replace('_', ' ')}
                    </span>
                    {h.agent_version && (
                      <div className="text-[9px] text-slate-400 mt-0.5" title="Tally desktop agent version last seen">
                        {h.agent_version}
                      </div>
                    )}
                  </td>
                  <td className="py-3 px-4 text-slate-600 text-xs">
                    {h.last_sync ? (
                      <div>
                        <div>{formatDate(h.last_sync)}</div>
                        <div className="text-slate-400">{h.days_since_sync === 0 ? 'Today' : `${h.days_since_sync}d ago`}</div>
                      </div>
                    ) : 'Never'}
                  </td>
                  <td className="py-3 px-4 text-right text-slate-700">{h.inventory_items?.toLocaleString()}</td>
                  <td className="py-3 px-4 text-right text-slate-700">{h.sales_vouchers?.toLocaleString()}</td>
                  <td className="py-3 px-4 text-right text-slate-700">{h.customers}</td>
                  <td className="py-3 px-4 text-right font-medium text-emerald-600">{formatINR(h.total_paid)}</td>
                  <td className="py-3 px-4 text-slate-600 text-xs">{formatDate(h.subscription_expires)}<br/><span className={h.days_left < 0 ? 'text-red-600 font-bold' : h.days_left <= 30 ? 'text-amber-600' : 'text-slate-400'}>{h.days_left < 0 ? `Exp ${Math.abs(h.days_left)}d` : `${h.days_left}d left`}</span></td>
                  <td className="py-3 px-4 text-center">
                    <button onClick={() => onOpenLedger(h.username)} className="p-1.5 text-slate-400 hover:text-blue-600 hover:bg-blue-50 rounded-lg" title="Ledger">
                      <FileText size={14} />
                    </button>
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
