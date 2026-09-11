import React, { useMemo, useState } from 'react';
import { Plus, CheckCircle2, Circle, StickyNote, X } from 'lucide-react';
import { formatINR, formatDate } from '../utils';

/*  iter-131: Bank reconciliation column added.
 *  Each payment row can be flipped between "reconciled" (matched
 *  against bank statement) and unreconciled, with an optional note.
 *  Summary cards show reconciled vs unmatched totals so the SuperAdmin
 *  can quickly see how much of the received cash is verified. */
export const PaymentsTab = ({ payments, onRecordPayment, onReconcile }) => {
  const [filter, setFilter] = useState('all');    // all | reconciled | unreconciled
  const [noteFor, setNoteFor] = useState(null);   // {payment_id, note}

  const totalAmount = payments.total_amount || 0;
  const rows = payments.payments || [];
  const reconciledRows = useMemo(() => rows.filter(p => p.reconciled), [rows]);
  const unreconciledRows = useMemo(() => rows.filter(p => !p.reconciled), [rows]);
  const reconciledSum = reconciledRows.reduce((s, p) => s + (Number(p.amount) || 0), 0);
  const unreconciledSum = unreconciledRows.reduce((s, p) => s + (Number(p.amount) || 0), 0);
  const displayRows = filter === 'reconciled' ? reconciledRows
                    : filter === 'unreconciled' ? unreconciledRows
                    : rows;

  const summaryCards = [
    { id: 'all',           label: 'Total Collected',   value: totalAmount,      valueClass: 'text-emerald-600' },
    { id: 'reconciled',    label: 'Reconciled',        value: reconciledSum,    valueClass: 'text-blue-600',  count: reconciledRows.length },
    { id: 'unreconciled',  label: 'Unmatched',         value: unreconciledSum,  valueClass: 'text-amber-600', count: unreconciledRows.length },
    { id: 'txn',           label: 'Transactions',      value: rows.length,      valueClass: 'text-slate-900', raw: true },
  ];

  const flipReconciled = (p, checked, note) => {
    onReconcile?.(p.payment_id, checked, note);
  };

  return (
    <div data-testid="payments-tab">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-slate-900">Payment Ledger</h2>
        <button onClick={onRecordPayment} className="px-4 py-2 bg-emerald-600 text-white rounded-lg text-sm font-medium hover:bg-emerald-700 flex items-center gap-2" data-testid="record-payment-btn">
          <Plus size={14} /> Record Payment
        </button>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        {summaryCards.map(c => {
          const clickable = ['all', 'reconciled', 'unreconciled'].includes(c.id);
          const active = filter === c.id;
          return (
            <button
              key={c.id}
              type="button"
              disabled={!clickable}
              onClick={() => setFilter(active ? 'all' : c.id)}
              className={`bg-white border rounded-xl p-4 text-left transition-all ${active ? 'border-blue-500 ring-2 ring-blue-200' : 'border-slate-200'} ${clickable ? 'hover:shadow-sm cursor-pointer' : 'cursor-default'}`}
              data-testid={`payments-card-${c.id}`}>
              <div className="text-xs text-slate-500 mb-1">{c.label}</div>
              <div className={`text-xl font-bold ${c.valueClass}`}>{c.raw ? c.value : formatINR(c.value)}</div>
              {c.count !== undefined && <div className="text-[11px] text-slate-400 mt-0.5">{c.count} txn</div>}
            </button>
          );
        })}
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
                <th className="py-3 px-4 text-center">Bank Recon</th>
              </tr>
            </thead>
            <tbody>
              {displayRows.map((p, i) => (
                <tr key={p.payment_id || i} className="border-t border-slate-100 hover:bg-slate-50" data-testid={`payment-row-${i}`}>
                  <td className="py-3 px-4">
                    <div className="font-medium text-slate-800">{p.customer_name || p.customer_username}</div>
                    <div className="text-xs text-slate-400">{p.customer_username}</div>
                  </td>
                  <td className="py-3 px-4 text-right font-bold text-emerald-600">{formatINR(p.amount)}</td>
                  <td className="py-3 px-4 text-slate-600 capitalize">{(p.payment_mode || '').replace('_', ' ')}</td>
                  <td className="py-3 px-4 text-slate-600 font-mono text-xs">{p.reference_no || '—'}</td>
                  <td className="py-3 px-4 text-slate-600">{p.period_description || '—'}</td>
                  <td className="py-3 px-4 text-slate-600">{formatDate(p.payment_date)}</td>
                  <td className="py-3 px-4 text-center">
                    <div className="flex items-center justify-center gap-2">
                      <button
                        type="button"
                        onClick={() => flipReconciled(p, !p.reconciled, p.reconciliation_note || '')}
                        className={`inline-flex items-center gap-1 px-2 py-1 rounded-lg text-[11px] font-semibold border ${p.reconciled ? 'bg-blue-50 text-blue-700 border-blue-200' : 'bg-slate-50 text-slate-500 border-slate-200 hover:bg-slate-100'}`}
                        data-testid={`recon-toggle-${p.payment_id || i}`}>
                        {p.reconciled ? <><CheckCircle2 size={12} /> Reconciled</> : <><Circle size={12} /> Mark</>}
                      </button>
                      <button
                        type="button"
                        onClick={() => setNoteFor({ payment_id: p.payment_id, note: p.reconciliation_note || '', reconciled: p.reconciled })}
                        title={p.reconciliation_note || 'Add reconciliation note'}
                        className={`p-1.5 rounded-lg border ${p.reconciliation_note ? 'text-amber-600 bg-amber-50 border-amber-200' : 'text-slate-400 border-slate-200 hover:bg-slate-50'}`}
                        data-testid={`recon-note-${p.payment_id || i}`}>
                        <StickyNote size={12} />
                      </button>
                    </div>
                    {p.reconciled && p.reconciled_by && (
                      <div className="text-[10px] text-slate-400 mt-1">by {p.reconciled_by}</div>
                    )}
                  </td>
                </tr>
              ))}
              {displayRows.length === 0 && (
                <tr><td colSpan={7} className="py-8 text-center text-slate-400">
                  {filter === 'all' ? 'No payments recorded yet' : filter === 'reconciled' ? 'No reconciled payments yet' : 'All payments are reconciled 🎉'}
                </td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Recon note modal */}
      {noteFor && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4"
             onClick={e => e.target === e.currentTarget && setNoteFor(null)}
             data-testid="recon-note-modal">
          <div className="bg-white rounded-xl w-full max-w-md p-6">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-base font-semibold text-slate-900">Reconciliation Note</h3>
              <button onClick={() => setNoteFor(null)}><X size={18} className="text-slate-400" /></button>
            </div>
            <textarea rows={4}
              value={noteFor.note}
              onChange={e => setNoteFor(n => ({ ...n, note: e.target.value }))}
              placeholder="e.g. matched to HDFC statement line dated 15/02, ref# HDFC-98765"
              className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm"
              data-testid="recon-note-textarea" />
            <div className="flex items-center justify-between mt-4">
              <label className="flex items-center gap-2 text-sm text-slate-700">
                <input type="checkbox" checked={noteFor.reconciled}
                       onChange={e => setNoteFor(n => ({ ...n, reconciled: e.target.checked }))} />
                Mark as reconciled
              </label>
              <div className="flex gap-2">
                <button onClick={() => setNoteFor(null)} className="px-3 py-1.5 text-sm border border-slate-200 rounded-lg">Cancel</button>
                <button onClick={() => { onReconcile?.(noteFor.payment_id, !!noteFor.reconciled, noteFor.note); setNoteFor(null); }}
                        className="px-3 py-1.5 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700"
                        data-testid="recon-note-save">Save</button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
