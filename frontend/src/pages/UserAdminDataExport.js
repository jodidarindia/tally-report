import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Download, Shield, FileArchive, RefreshCw, CheckCircle2 } from 'lucide-react';
import toast from 'react-hot-toast';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

/** UserAdmin Data Export — DPDP right-to-portability download. */
export default function UserAdminDataExport() {
  const [counts, setCounts] = useState(null);
  const [loading, setLoading] = useState(true);
  const [downloading, setDownloading] = useState(false);

  const fetchPreview = () => {
    setLoading(true);
    axios.get(`${API}/admin/data-export/preview`)
      .then(r => { if (r.data?.success) setCounts(r.data.data); })
      .finally(() => setLoading(false));
  };

  useEffect(() => { fetchPreview(); }, []);

  const downloadZip = async () => {
    setDownloading(true);
    try {
      const token = localStorage.getItem('flowra_token');
      const res = await fetch(`${API}/admin/data-export`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) {
        toast.error('Export failed');
        setDownloading(false);
        return;
      }
      const cd = res.headers.get('Content-Disposition') || '';
      const m = cd.match(/filename="([^"]+)"/);
      const filename = m ? m[1] : `flowra_data_export_${Date.now()}.zip`;
      const blob = await res.blob();
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = filename;
      a.click();
      URL.revokeObjectURL(a.href);
      toast.success('Export downloaded');
    } catch (e) {
      toast.error(e.message || 'Download failed');
    }
    setDownloading(false);
  };

  const fmtNum = (n) => Number(n || 0).toLocaleString('en-IN');

  // Friendly labels for collection names
  const labels = {
    customers: 'Customers / Sundry Debtors',
    creditors: 'Suppliers / Sundry Creditors',
    all_ledgers: 'Tally Ledgers (master)',
    branch_ledgers: 'Branch Ledgers',
    sales_vouchers: 'Sales Invoices',
    purchase_vouchers: 'Purchase Invoices',
    credit_notes: 'Credit Notes',
    debit_notes: 'Debit Notes',
    receipt_vouchers: 'Receipts',
    payment_vouchers: 'Payments',
    journal_vouchers: 'Journals',
    contra_vouchers: 'Contra Vouchers',
    inventory_items: 'Inventory Items',
    salesman_master: 'Salesman Profiles',
    salesman_beats: 'Beat Plans',
    beat_runs: 'Beat Run History',
    salesman_orders: 'Online Orders',
    dispatch_cards: 'Dispatch Cards',
    dispatch_porters: 'Porters',
    dispatch_transporters: 'Transporters',
    profit_loss: 'P&L Snapshots',
    ai_queries: 'AI Q&A Sessions',
    ai_reports: 'AI Reports',
    questionnaires: 'Onboarding Questionnaires',
    prospects: 'Prospects',
  };

  const grouped = !counts ? {} : {
    'Sales & CRM': ['customers', 'sales_vouchers', 'credit_notes', 'receipt_vouchers'],
    'Purchases & Suppliers': ['creditors', 'purchase_vouchers', 'debit_notes', 'payment_vouchers'],
    'Inventory': ['inventory_items'],
    'Salesman Module': ['salesman_master', 'salesman_beats', 'beat_runs', 'salesman_orders'],
    'Dispatch': ['dispatch_cards', 'dispatch_porters', 'dispatch_transporters'],
    'Tally Master Data': ['all_ledgers', 'branch_ledgers', 'journal_vouchers', 'contra_vouchers', 'profit_loss'],
    'AI & Onboarding': ['ai_queries', 'ai_reports', 'questionnaires', 'prospects'],
  };

  return (
    <div className="space-y-4 max-w-3xl mx-auto" data-testid="data-export-page">
      <div className="bg-white border border-slate-200 rounded-xl p-4 sm:p-5">
        <div className="flex items-start gap-3">
          <div className="w-11 h-11 rounded-xl bg-emerald-100 text-emerald-600 flex items-center justify-center flex-shrink-0">
            <FileArchive size={22} />
          </div>
          <div className="flex-1 min-w-0">
            <h2 className="text-base sm:text-lg font-bold text-slate-900">Export Your Data</h2>
            <p className="text-xs sm:text-[13px] text-slate-600 mt-1">
              Download a complete ZIP of every record FLOWRA stores for your tenant — one JSON file per collection plus a manifest.
              You own this data; we never sell it. <strong>DPDP Act 2023 compliant.</strong>
            </p>
          </div>
        </div>

        {loading ? (
          <div className="flex items-center justify-center h-24"><div className="w-6 h-6 border-2 border-slate-200 border-t-emerald-600 rounded-full animate-spin" /></div>
        ) : counts && (
          <>
            <div className="mt-4 bg-emerald-50 border border-emerald-200 rounded-lg px-3 py-2 flex items-center justify-between">
              <div>
                <div className="text-xs text-emerald-700">Total documents in your tenant</div>
                <div className="text-xl font-bold text-emerald-800" data-testid="total-docs">{fmtNum(counts.total_documents)}</div>
              </div>
              <button onClick={fetchPreview} className="text-emerald-600 hover:bg-emerald-100 p-2 rounded-lg" title="Refresh counts" data-testid="refresh-preview"><RefreshCw size={14} /></button>
            </div>

            <div className="mt-4 space-y-3">
              {Object.entries(grouped).map(([groupName, cols]) => {
                const total = cols.reduce((s, c) => s + (counts.counts[c] || 0), 0);
                if (total === 0) return null;
                return (
                  <div key={groupName} className="border border-slate-100 rounded-lg overflow-hidden">
                    <div className="bg-slate-50 px-3 py-1.5 flex items-center justify-between">
                      <h4 className="text-[11px] uppercase font-bold tracking-wider text-slate-600">{groupName}</h4>
                      <span className="text-[11px] font-semibold text-slate-700">{fmtNum(total)} rows</span>
                    </div>
                    <div className="grid grid-cols-2 sm:grid-cols-3 gap-x-3 gap-y-1 px-3 py-2">
                      {cols.map(col => (
                        <div key={col} className="flex justify-between text-[11px]">
                          <span className="text-slate-600 truncate">{labels[col] || col}</span>
                          <span className="font-medium text-slate-800">{fmtNum(counts.counts[col] || 0)}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>

            <button
              onClick={downloadZip}
              disabled={downloading || counts.total_documents === 0}
              className="mt-4 w-full sm:w-auto flex items-center justify-center gap-2 px-5 py-2.5 bg-emerald-600 text-white text-sm font-semibold rounded-lg hover:bg-emerald-700 disabled:opacity-50"
              data-testid="download-zip-btn">
              <Download size={15} /> {downloading ? 'Preparing ZIP…' : 'Download Full Export (.zip)'}
            </button>
          </>
        )}
      </div>

      {/* Privacy & info card */}
      <div className="bg-blue-50 border border-blue-100 rounded-xl p-3 sm:p-4">
        <div className="flex items-start gap-2.5">
          <Shield size={18} className="text-blue-600 flex-shrink-0 mt-0.5" />
          <div className="text-[12px] text-blue-800 space-y-1.5">
            <p><strong>What's inside the ZIP:</strong> one <code className="bg-blue-100 px-1 rounded text-[10px]">.json</code> per collection (sales, customers, inventory, beats, etc.) + a <code className="bg-blue-100 px-1 rounded text-[10px]">manifest.json</code> with row counts and export timestamp.</p>
            <p><strong>What's NOT included:</strong> user passwords, login tokens, audit logs system-wide, or any other tenant's data — server enforces strict tenant isolation on every query.</p>
            <p><strong>Format:</strong> Plain JSON. Open in Excel via Power Query, or re-import via FLOWRA support if you ever migrate or restore.</p>
            <p className="flex items-center gap-1.5 mt-2"><CheckCircle2 size={13} className="text-blue-600" /> All exports are logged to your audit trail.</p>
          </div>
        </div>
      </div>
    </div>
  );
}
