import React from 'react';
import { Plus, Download, BadgeCheck, XCircle } from 'lucide-react';
import { formatINR, formatDate } from '../utils';

export const InvoicesTab = ({ invoices, onGenerateInvoice, onDownloadPDF, onMarkStatus }) => (
  <div data-testid="invoices-tab">
    <div className="flex items-center justify-between mb-4">
      <h2 className="text-lg font-semibold text-slate-900">Invoices</h2>
      <button onClick={onGenerateInvoice} className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 flex items-center gap-2" data-testid="generate-invoice-btn">
        <Plus size={14} /> Generate Invoice
      </button>
    </div>
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
      <div className="bg-white border border-slate-200 rounded-xl p-4">
        <div className="text-xs text-slate-500 mb-1">Total Invoiced</div>
        <div className="text-xl font-bold text-blue-600">{formatINR(invoices.total_invoiced)}</div>
      </div>
      <div className="bg-white border border-slate-200 rounded-xl p-4">
        <div className="text-xs text-slate-500 mb-1">Total Invoices</div>
        <div className="text-xl font-bold text-slate-900">{invoices.total}</div>
      </div>
      <div className="bg-white border border-slate-200 rounded-xl p-4">
        <div className="text-xs text-slate-500 mb-1">Paid</div>
        <div className="text-xl font-bold text-emerald-600">{invoices.paid_count}</div>
      </div>
      <div className="bg-white border border-slate-200 rounded-xl p-4">
        <div className="text-xs text-slate-500 mb-1">Unpaid</div>
        <div className="text-xl font-bold text-red-600">{invoices.unpaid_count}</div>
      </div>
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
            {invoices.invoices?.map((inv, i) => (
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
                  <div className="flex items-center justify-center gap-1">
                    <button onClick={() => onDownloadPDF(inv.invoice_id)} className="p-1.5 text-slate-400 hover:text-blue-600 hover:bg-blue-50 rounded-lg" title="Download PDF" data-testid={`download-invoice-${i}`}>
                      <Download size={14} />
                    </button>
                    {inv.status === 'unpaid' && (
                      <button onClick={() => onMarkStatus(inv.invoice_id, 'paid')} className="p-1.5 text-slate-400 hover:text-emerald-600 hover:bg-emerald-50 rounded-lg" title="Mark Paid" data-testid={`mark-paid-${i}`}>
                        <BadgeCheck size={14} />
                      </button>
                    )}
                    {inv.status === 'paid' && (
                      <button onClick={() => onMarkStatus(inv.invoice_id, 'unpaid')} className="p-1.5 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded-lg" title="Mark Unpaid">
                        <XCircle size={14} />
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
            {(!invoices.invoices || invoices.invoices.length === 0) && (
              <tr><td colSpan={6} className="py-8 text-center text-slate-400">No invoices generated yet</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  </div>
);
