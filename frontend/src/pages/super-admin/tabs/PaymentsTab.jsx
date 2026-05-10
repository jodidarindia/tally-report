import React from 'react';
import { Plus } from 'lucide-react';
import { formatINR, formatDate } from '../utils';

export const PaymentsTab = ({ payments, onRecordPayment }) => (
  <div data-testid="payments-tab">
    <div className="flex items-center justify-between mb-4">
      <h2 className="text-lg font-semibold text-slate-900">Payment Ledger</h2>
      <button onClick={onRecordPayment} className="px-4 py-2 bg-emerald-600 text-white rounded-lg text-sm font-medium hover:bg-emerald-700 flex items-center gap-2" data-testid="record-payment-btn">
        <Plus size={14} /> Record Payment
      </button>
    </div>
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
      <div className="bg-white border border-slate-200 rounded-xl p-4">
        <div className="text-xs text-slate-500 mb-1">Total Collected</div>
        <div className="text-xl font-bold text-emerald-600" data-testid="total-collected">{formatINR(payments.total_amount)}</div>
      </div>
      <div className="bg-white border border-slate-200 rounded-xl p-4">
        <div className="text-xs text-slate-500 mb-1">Transactions</div>
        <div className="text-xl font-bold text-slate-900">{payments.payments?.length || 0}</div>
      </div>
      {Object.entries(payments.by_mode || {}).slice(0, 2).map(([mode, amt]) => (
        <div key={mode} className="bg-white border border-slate-200 rounded-xl p-4">
          <div className="text-xs text-slate-500 mb-1 capitalize">{mode.replace('_', ' ')}</div>
          <div className="text-xl font-bold text-slate-900">{formatINR(amt)}</div>
        </div>
      ))}
    </div>
    <div className="bg-white border border-slate-200 rounded-xl overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-sm" data-testid="payments-table">
          <thead>
            <tr className="bg-slate-50 text-xs text-slate-500 uppercase">
              <th className="py-3 px-4 text-left">Customer</th>
              <th className="py-3 px-4 text-right">Amount</th>
              <th className="py-3 px-4 text-left">Mode</th>
              <th className="py-3 px-4 text-left">Reference</th>
              <th className="py-3 px-4 text-left">Period</th>
              <th className="py-3 px-4 text-left">Date</th>
            </tr>
          </thead>
          <tbody>
            {payments.payments?.map((p, i) => (
              <tr key={i} className="border-t border-slate-100 hover:bg-slate-50" data-testid={`payment-row-${i}`}>
                <td className="py-3 px-4">
                  <div className="font-medium text-slate-800">{p.customer_name || p.customer_username}</div>
                  <div className="text-xs text-slate-400">{p.customer_username}</div>
                </td>
                <td className="py-3 px-4 text-right font-bold text-emerald-600">{formatINR(p.amount)}</td>
                <td className="py-3 px-4 text-slate-600 capitalize">{(p.payment_mode || '').replace('_', ' ')}</td>
                <td className="py-3 px-4 text-slate-600 font-mono text-xs">{p.reference_no || '—'}</td>
                <td className="py-3 px-4 text-slate-600">{p.period_description || '—'}</td>
                <td className="py-3 px-4 text-slate-600">{formatDate(p.payment_date)}</td>
              </tr>
            ))}
            {(!payments.payments || payments.payments.length === 0) && (
              <tr><td colSpan={6} className="py-8 text-center text-slate-400">No payments recorded yet</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  </div>
);
