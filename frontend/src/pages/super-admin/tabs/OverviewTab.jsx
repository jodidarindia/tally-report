import React from 'react';
import { IndianRupee, TrendingUp, CircleDollarSign, AlertTriangle, Receipt, Plus } from 'lucide-react';
import { formatINR, formatDate } from '../utils';

export const OverviewTab = ({ businessData, onRecordPayment, onGenerateInvoice, onNewAdmin }) => {
  if (!businessData) return null;
  return (
    <div data-testid="overview-tab">
      {/* Revenue Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <div className="bg-gradient-to-br from-blue-600 to-blue-700 rounded-xl p-5 text-white">
          <div className="flex items-center gap-2 text-blue-200 text-xs mb-1"><IndianRupee size={14} /> Monthly Recurring</div>
          <div className="text-2xl font-bold" data-testid="mrr-value">{formatINR(businessData.mrr)}</div>
          <div className="text-blue-200 text-xs mt-1">MRR</div>
        </div>
        <div className="bg-gradient-to-br from-emerald-600 to-emerald-700 rounded-xl p-5 text-white">
          <div className="flex items-center gap-2 text-emerald-200 text-xs mb-1"><TrendingUp size={14} /> Annual Revenue</div>
          <div className="text-2xl font-bold" data-testid="arr-value">{formatINR(businessData.arr)}</div>
          <div className="text-emerald-200 text-xs mt-1">ARR</div>
        </div>
        <div className="bg-gradient-to-br from-violet-600 to-violet-700 rounded-xl p-5 text-white">
          <div className="flex items-center gap-2 text-violet-200 text-xs mb-1"><CircleDollarSign size={14} /> Collections</div>
          <div className="text-2xl font-bold" data-testid="collected-value">{formatINR(businessData.total_received)}</div>
          <div className="text-violet-200 text-xs mt-1">{businessData.collection_rate}% collected</div>
        </div>
        <div className="bg-gradient-to-br from-rose-600 to-rose-700 rounded-xl p-5 text-white">
          <div className="flex items-center gap-2 text-rose-200 text-xs mb-1"><AlertTriangle size={14} /> Outstanding</div>
          <div className="text-2xl font-bold" data-testid="outstanding-value">{formatINR(businessData.outstanding)}</div>
          <div className="text-rose-200 text-xs mt-1">Balance due</div>
        </div>
      </div>

      {/* Customer & Plan metrics — iter-124: added ACV + churn +
          separated Trials so numbers are honest to standard SaaS
          definitions. */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-3 mb-6">
        <div className="bg-white border border-slate-200 rounded-xl p-4">
          <div className="text-xs text-slate-500 mb-1">Total</div>
          <div className="text-xl font-bold text-slate-900" data-testid="total-customers">{businessData.total_customers}</div>
        </div>
        <div className="bg-white border border-slate-200 rounded-xl p-4">
          <div className="text-xs text-slate-500 mb-1">Paying</div>
          <div className="text-xl font-bold text-emerald-600" data-testid="paying-customers">{businessData.paying_customers ?? businessData.active_customers}</div>
        </div>
        <div className="bg-white border border-slate-200 rounded-xl p-4">
          <div className="text-xs text-slate-500 mb-1">Trials</div>
          <div className="text-xl font-bold text-cyan-600" data-testid="trial-customers">{businessData.trial_customers ?? 0}</div>
        </div>
        <div className="bg-white border border-slate-200 rounded-xl p-4">
          <div className="text-xs text-slate-500 mb-1" title="Monthly Recurring / paying customer">ARPU</div>
          <div className="text-xl font-bold text-blue-600" data-testid="arpu-value">{formatINR(businessData.arpu)}</div>
        </div>
        <div className="bg-white border border-slate-200 rounded-xl p-4">
          <div className="text-xs text-slate-500 mb-1" title="Average Contract Value">ACV</div>
          <div className="text-xl font-bold text-slate-800" data-testid="acv-value">{formatINR(businessData.acv ?? (businessData.paying_customers ? businessData.total_contract_value / businessData.paying_customers : 0))}</div>
        </div>
        <div className="bg-white border border-slate-200 rounded-xl p-4">
          <div className="text-xs text-slate-500 mb-1" title="Total Contract Value across active paying customers">TCV</div>
          <div className="text-xl font-bold text-slate-900" data-testid="tcv-value">{formatINR(businessData.total_contract_value)}</div>
        </div>
        <div className="bg-white border border-slate-200 rounded-xl p-4">
          <div className="text-xs text-slate-500 mb-1" title="Churned / (Paying + Churned)">Churn %</div>
          <div className="text-xl font-bold text-rose-600" data-testid="churn-rate">{(businessData.churn_rate ?? 0).toFixed(1)}%</div>
        </div>
      </div>

      {/* Plan Distribution + Recent Payments */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
        <div className="bg-white border border-slate-200 rounded-xl p-5">
          <h3 className="text-sm font-semibold text-slate-900 mb-4">Plan Distribution</h3>
          {Object.entries(businessData.plan_distribution || {}).map(([plan, count]) => {
            const total = (businessData.paying_customers ?? businessData.active_customers) || 1;
            const pct = Math.round((count / total) * 100);
            const colors = { starter: 'bg-slate-400', professional: 'bg-blue-500', enterprise: 'bg-purple-500' };
            return (
              <div key={plan} className="mb-3">
                <div className="flex items-center justify-between text-sm mb-1">
                  <span className="capitalize font-medium">{plan}</span>
                  <span className="text-slate-500">{count} ({pct}%)</span>
                </div>
                <div className="w-full bg-slate-100 rounded-full h-2">
                  <div className={`${colors[plan] || 'bg-blue-500'} h-2 rounded-full transition-all`} style={{ width: `${pct}%` }} />
                </div>
              </div>
            );
          })}
        </div>
        <div className="bg-white border border-slate-200 rounded-xl p-5">
          <h3 className="text-sm font-semibold text-slate-900 mb-4">Recent Payments</h3>
          {businessData.recent_payments?.length === 0 ? (
            <p className="text-sm text-slate-400 text-center py-4">No payments recorded yet</p>
          ) : (
            <div className="space-y-3">
              {businessData.recent_payments?.map((p, i) => (
                <div key={i} className="flex items-center justify-between py-2 border-b border-slate-50 last:border-0">
                  <div>
                    <div className="text-sm font-medium text-slate-800">{p.customer_name || p.customer_username}</div>
                    <div className="text-xs text-slate-400">{formatDate(p.payment_date)} · {p.payment_mode?.replace('_', ' ')}</div>
                  </div>
                  <div className="text-sm font-bold text-emerald-600">{formatINR(p.amount)}</div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Quick Actions */}
      <div className="flex flex-wrap gap-3">
        <button onClick={onRecordPayment} className="px-4 py-2.5 bg-emerald-600 text-white rounded-lg text-sm font-medium hover:bg-emerald-700 flex items-center gap-2" data-testid="quick-record-payment">
          <IndianRupee size={16} /> Record Payment
        </button>
        <button onClick={onGenerateInvoice} className="px-4 py-2.5 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 flex items-center gap-2" data-testid="quick-generate-invoice">
          <Receipt size={16} /> Generate Invoice
        </button>
        <button onClick={onNewAdmin} className="px-4 py-2.5 bg-slate-800 text-white rounded-lg text-sm font-medium hover:bg-slate-900 flex items-center gap-2" data-testid="quick-new-admin">
          <Plus size={16} /> New Customer
        </button>
      </div>
    </div>
  );
};
