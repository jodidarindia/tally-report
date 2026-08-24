import React, { useMemo, useState } from 'react';
import { Plus, Download, BadgeCheck, XCircle } from 'lucide-react';
import { formatINR, formatDate } from '../utils';

export const InvoicesTab = ({ invoices, onGenerateInvoice, onDownloadPDF, onMarkStatus }) => {
  // iter-122: clickable summary cards filter the table below.
  const [filter, setFilter] = useState('all');

  const filtered = useMemo(() => {
    const list = invoices.invoices || [];
    if (filter === 'all') return list;
    if (filter === 'paid') return list.filter(i => i.status === 'paid');
    if (filter === 'unpaid') return list.filter(i => i.status === 'unpaid');
    return list;
  }, [invoices.invoices, filter]);

  const cards = [
    { id: 'total_amt', label: 'Total Invoiced', value: formatINR(invoices.total_invoiced), color: 'text-blue-600', click: () => setFilter('all') },
    { id: 'all',       label: 'Total Invoices', value: invoices.total, color: 'text-slate-900', click: () => setFilter('all') },
    { id: 'paid',      label: 'Paid',           value: invoices.paid_count, color: 'text-emerald-600', click: () => setFilter(filter === 'paid' ? 'all' : 'paid') },
    { id: 'unpaid',    label: 'Unpaid',         value: invoices.unpaid_count, color: 'text-red-600', click: () => setFilter(filter === 'unpaid' ? 'all' : 'unpaid') },
  ];

  return (
  <div data-testid="invoices-tab">
    <div className="flex items-center justify-between mb-4">
      <h2 className="text-lg font-semibold text-slate-900">Invoices</h2>
      <button onClick={onGenerateInvoice} className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 flex items-center gap-2" data-testid="generate-invoice-btn">
        <Plus size={14} /> Generate Invoice
      </button>
    </div>
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
      {cards.map(c => {
        const active = (c.id === filter) || (c.id === 'all' && filter === 'all' && c.id !== 'total_amt');
        return (
          <button
            key={c.id}
            type="button"
            onClick={c.click}
            className={`bg-white border rounded-xl p-4 text-left transition-all ${active ? 'border-blue-500 ring-2 ring-blue-200 shadow-md' : 'border-slate-200 hover:shadow-sm'}`}
            data-testid={`inv-card-${c.id}`}
          >
            <div className="text-xs text-slate-500 mb-1 flex items-center justify-between">
              <span>{c.label}</span>
              {active && c.id !== 'total_amt' && <span className="text-blue-600 text-[10px]">● Filtered</span>}
            </div>
            <div className={`text-xl font-bold ${c.color}`}>{c.value}</div>
          </button>
        );
      })}
    </div>
    <div className="bg-white border border-slate-200 rounded-xl overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-sm" data-testid="invoices-table">
          <thead>
            <tr className="bg-slate-50 text-xs text-slate-500 uppercase">
              <th className="py-3 px-4 text-left">Invoice #</th>
              <th className="py-3 px-4 text-left">Customer</th>
              <th className="py-3 px-4 text-right">Amount</th>
              <th className="py-3 px-4 text-left">Date</th>
              <th className="py-3 px-4 text-center">Status</th>
              <th className="py-3 px-4 text-center">Actions</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((inv, i) => (
              <tr key={i} className="border-t border-slate-100 hover:bg-slate-50" data-testid={`invoice-row-${i}`}>
                <td className="py-3 px-4 font-mono text-sm font-medium text-slate-800">{inv.invoice_number}</td>
                <td className="py-3 px-4">
                  <div className="font-medium text-slate-800">{inv.customer_name}</div>
                  <div className="text-xs text-slate-400">{inv.description?.substring(0, 40)}</div>
                </td>
                <td className="py-3 px-4 text-right font-bold text-blue-600">{formatINR(inv.amount)}</td>
                <td className="py-3 px-4 text-slate-600">{formatDate(inv.invoice_date)}</td>
                <td className="py-3 px-4 text-center">
                  <span className={`text-[10px] px-2 py-0.5 rounded-full font-bold uppercase ${inv.status === 'paid' ? 'bg-emerald-50 text-emerald-700' : inv.status === 'cancelled' ? 'bg-slate-100 text-slate-500' : 'bg-red-50 text-red-700'}`}>
                    {inv.status}
                  </span>
                </td>
                <td className="py-3 px-4 text-center">
                  <div className="flex items-center justify-center gap-1 flex-wrap">
                    <button onClick={() => onDownloadPDF(inv.invoice_id)} className="p-1.5 text-slate-400 hover:text-blue-600 hover:bg-blue-50 rounded-lg" title="Download PDF" data-testid={`download-invoice-${i}`}>
                      <Download size={14} />
                    </button>
                    {/* iter-123: toggle buttons always visible so status can
                        be flipped in either direction; disabled when the
                        current status already matches. */}
                    <button
                      onClick={() => onMarkStatus(inv.invoice_id, 'paid')}
                      disabled={inv.status === 'paid'}
                      className={`p-1.5 rounded-lg ${inv.status === 'paid' ? 'text-emerald-500 bg-emerald-50 cursor-default' : 'text-slate-400 hover:text-emerald-600 hover:bg-emerald-50'}`}
                      title={inv.status === 'paid' ? 'Already paid' : 'Mark Paid'}
                      data-testid={`mark-paid-${i}`}
                    >
                      <BadgeCheck size={14} />
                    </button>
                    <button
                      onClick={() => onMarkStatus(inv.invoice_id, 'unpaid')}
                      disabled={inv.status === 'unpaid'}
                      className={`p-1.5 rounded-lg ${inv.status === 'unpaid' ? 'text-red-500 bg-red-50 cursor-default' : 'text-slate-400 hover:text-red-600 hover:bg-red-50'}`}
                      title={inv.status === 'unpaid' ? 'Already unpaid' : 'Flip to Unpaid'}
                      data-testid={`mark-unpaid-${i}`}
                    >
                      <XCircle size={14} />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
            {(!filtered || filtered.length === 0) && (
              <tr><td colSpan={6} className="py-8 text-center text-slate-400">{filter === 'all' ? 'No invoices generated yet' : `No ${filter} invoices in this filter`}</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  </div>
  );
};
