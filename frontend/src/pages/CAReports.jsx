import React, { useEffect, useState, useCallback } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import {
  FileText, Download, Loader, RefreshCw, ShieldCheck, Info,
  AlertTriangle, Landmark, Sparkles, Lock,
} from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

// The 10 assumption fields users can tune. Each field carries a short
// hint + a "derivation" tooltip so CAs & founders know exactly what
// FLOWRA does with the number.
const ASSUMPTION_FIELDS = [
  { key: 'sales_growth_y1', label: 'Sales growth Y1', unit: '%',
    hint: 'Default from historical CAGR' },
  { key: 'sales_growth_y2', label: 'Sales growth Y2', unit: '%' },
  { key: 'sales_growth_y3', label: 'Sales growth Y3', unit: '%' },
  { key: 'gp_margin_target_pct', label: 'Target Gross Profit margin', unit: '%',
    hint: 'Applied to projected Net Sales' },
  { key: 'debtor_days_target', label: 'Target Debtor days', unit: 'days' },
  { key: 'creditor_days_target', label: 'Target Creditor days', unit: 'days' },
  { key: 'inventory_days_target', label: 'Target Inventory days', unit: 'days' },
  { key: 'planned_capex_y1', label: 'Planned capex Y1', unit: '₹ Lacs' },
  { key: 'planned_capex_y2', label: 'Planned capex Y2', unit: '₹ Lacs' },
  { key: 'planned_capex_y3', label: 'Planned capex Y3', unit: '₹ Lacs' },
  { key: 'term_loan_repayment_y1', label: 'Term loan paydown Y1', unit: '₹ Lacs' },
  { key: 'term_loan_repayment_y2', label: 'Term loan paydown Y2', unit: '₹ Lacs' },
  { key: 'term_loan_repayment_y3', label: 'Term loan paydown Y3', unit: '₹ Lacs' },
  { key: 'proposed_cc_limit', label: 'Proposed CC/OD limit', unit: '₹ Lacs',
    hint: 'The ask you\'re making to the bank' },
];

// Bank + regulatory fields — encrypted at rest.
const BANK_FIELDS = [
  { key: 'bank_name', label: 'Bank name', unit: 'text',
    hint: 'Which bank is this CMA being submitted to?' },
  { key: 'gstin',    label: 'GSTIN',       unit: 'text' },
  { key: 'pan',      label: 'PAN',         unit: 'text' },
  { key: 'msme_regn', label: 'MSME registration', unit: 'text' },
  { key: 'existing_cc_limit', label: 'Existing CC/OD limit', unit: '₹ Lacs' },
];

const CAReports = () => {
  const [loading, setLoading] = useState(false);
  const [preview, setPreview] = useState(null);
  const [assumptions, setAssumptions] = useState({});
  const [saving, setSaving] = useState(false);
  const [activeSubTab, setActiveSubTab] = useState('cma');
  const [downloading, setDownloading] = useState('');

  const loadPreview = useCallback(async () => {
    setLoading(true);
    try {
      const res = await axios.post(`${API}/ca-reports/preview`,
                                     { n_hist: 2, n_proj: 3 });
      if (res.data?.success) {
        setPreview(res.data.data);
        setAssumptions(res.data.data.assumptions || {});
      } else {
        toast.error(res.data?.error || 'Failed to load preview');
      }
    } catch (e) {
      toast.error(e.response?.data?.error
                    || e.response?.data?.detail
                    || 'Failed to load bank-report preview');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadPreview(); }, [loadPreview]);

  const saveAssumptions = async () => {
    setSaving(true);
    try {
      const res = await axios.post(`${API}/ca-reports/assumptions`,
                                     assumptions);
      if (res.data?.success) toast.success('Assumptions saved (encrypted)');
      else toast.error(res.data?.error || 'Save failed');
    } catch (e) {
      toast.error(e.response?.data?.error || 'Save failed');
    } finally {
      setSaving(false);
    }
  };

  const generate = async (endpoint, filename, keyLabel) => {
    setDownloading(keyLabel);
    try {
      const res = await axios.post(`${API}${endpoint}`,
        { assumptions, n_hist: 2, n_proj: 3 },
        { responseType: 'blob' }
      );
      // Success path streams a binary; catch the API-shape JSON errors that
      // the guard returns.
      if (res.data instanceof Blob &&
           res.data.type.includes('application/json')) {
        const text = await res.data.text();
        try {
          const j = JSON.parse(text);
          toast.error(j?.error || j?.detail || 'Generation failed');
        } catch { toast.error('Generation failed'); }
        return;
      }
      const blob = new Blob([res.data]);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url; a.download = filename; a.click();
      window.URL.revokeObjectURL(url);
      toast.success(`${keyLabel} downloaded`);
    } catch (e) {
      toast.error(e.response?.data?.error
                    || e.response?.data?.detail
                    || 'Download failed');
    } finally {
      setDownloading('');
    }
  };

  const onFieldChange = (key, val, isNumeric) => {
    setAssumptions(prev => ({
      ...prev,
      [key]: isNumeric ? (val === '' ? '' : Number(val)) : val,
    }));
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16"
             data-testid="ca-reports-loading">
        <Loader className="animate-spin text-[#2563EB]" size={22} />
        <span className="ml-3 text-slate-500 text-sm">
          Assembling data from your Tally sync…
        </span>
      </div>
    );
  }

  if (!preview) {
    return (
      <div className="bg-white border border-slate-200 rounded-xl p-6 text-center"
             data-testid="ca-reports-empty">
        <AlertTriangle className="mx-auto text-amber-500 mb-2" size={26} />
        <div className="text-slate-700 font-medium">
          Unable to load bank-report data.
        </div>
        <button onClick={loadPreview}
                 data-testid="btn-reload-preview"
                 className="mt-3 px-3 py-1.5 bg-[#2563EB] text-white text-sm rounded-lg">
          Retry
        </button>
      </div>
    );
  }

  const { company, historicals = [], projections = [], warnings = [] } = preview;

  return (
    <div className="space-y-6" data-testid="ca-reports-panel">
      {/* Header */}
      <div className="bg-gradient-to-r from-[#0F1B4C] to-[#2563EB] text-white
                        rounded-xl p-5 flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2">
            <ShieldCheck size={20} />
            <h2 className="text-lg font-semibold">Bank & Investor Reports</h2>
            <span className="text-xs bg-white/20 px-2 py-0.5 rounded-full">
              Useradmin only
            </span>
          </div>
          <div className="text-sm mt-1 text-blue-100">
            Generate bank-submission-ready CMA and dynamic investor pitch
            decks from your live Tally / Busy data — all figures traceable,
            all sensitive inputs encrypted at rest.
          </div>
        </div>
        <div className="text-right text-xs text-blue-100 hidden md:block">
          <div>{company?.company_name}</div>
          <div className="text-blue-200/80 mt-0.5">
            {historicals.length} historical FY · {projections.length} projected FY
          </div>
        </div>
      </div>

      {warnings?.length > 0 && (
        <div className="flex items-start gap-2 bg-amber-50 border border-amber-200
                          text-amber-800 text-sm rounded-lg p-3">
          <AlertTriangle size={16} className="mt-0.5 flex-shrink-0" />
          <div>{warnings.join(' ')}</div>
        </div>
      )}

      {/* Sub-tabs */}
      <div className="bg-white border border-slate-200 rounded-xl p-1.5 flex gap-1.5">
        {[
          { id: 'cma',   label: 'CMA (Bank submission)', icon: Landmark },
          { id: 'pitch', label: 'Investor Pitch Deck',   icon: Sparkles },
        ].map(t => {
          const Icon = t.icon;
          return (
            <button key={t.id}
                     data-testid={`sub-tab-${t.id}`}
                     onClick={() => setActiveSubTab(t.id)}
                     className={`flex-1 flex items-center justify-center gap-2
                        px-4 py-2.5 rounded-lg font-medium text-sm transition-all
                        ${activeSubTab === t.id
                          ? 'bg-[#2563EB] text-white'
                          : 'text-slate-600 hover:bg-slate-50'}`}>
              <Icon size={16} />
              {t.label}
            </button>
          );
        })}
      </div>

      {/* Assumptions card */}
      <div className="bg-white border border-slate-200 rounded-xl p-5">
        <div className="flex items-center justify-between mb-3">
          <div>
            <h3 className="font-semibold text-slate-900">
              Projection Assumptions
            </h3>
            <div className="text-xs text-slate-500 mt-0.5">
              10 inputs — historical defaults are pre-filled from your Tally data.
              Edit any value; formulas re-run on every generation.
            </div>
          </div>
          <button onClick={saveAssumptions}
                   data-testid="btn-save-assumptions"
                   disabled={saving}
                   className="flex items-center gap-1.5 px-3 py-1.5 bg-white
                      border border-slate-300 hover:bg-slate-50 text-slate-700
                      text-sm rounded-lg disabled:opacity-50">
            {saving ? <Loader className="animate-spin" size={14}/>
                     : <RefreshCw size={14}/>}
            Save
          </button>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {ASSUMPTION_FIELDS.map(f => (
            <div key={f.key} className="flex flex-col gap-1">
              <label className="text-xs font-medium text-slate-700">
                {f.label}
                <span className="text-slate-400 ml-1">({f.unit})</span>
              </label>
              <input type="number" step="0.01"
                      data-testid={`assumption-${f.key}`}
                      value={assumptions[f.key] ?? ''}
                      onChange={e => onFieldChange(f.key, e.target.value, true)}
                      className="w-full px-2.5 py-1.5 border border-slate-300
                          rounded-md text-sm focus:outline-none
                          focus:ring-2 focus:ring-[#2563EB]/30"/>
              {f.hint && (
                <div className="text-[10px] text-slate-400">{f.hint}</div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Bank fields — encrypted */}
      {activeSubTab === 'cma' && (
        <div className="bg-white border border-slate-200 rounded-xl p-5">
          <div className="flex items-center gap-2 mb-3">
            <Lock size={16} className="text-emerald-600" />
            <h3 className="font-semibold text-slate-900">
              Bank & Regulatory Details
            </h3>
            <span className="text-xs bg-emerald-50 text-emerald-700 border
                    border-emerald-200 px-2 py-0.5 rounded-full">
              Fernet-AES-128 encrypted at rest
            </span>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {BANK_FIELDS.map(f => (
              <div key={f.key} className="flex flex-col gap-1">
                <label className="text-xs font-medium text-slate-700">
                  {f.label}
                  {f.unit !== 'text' &&
                    <span className="text-slate-400 ml-1">({f.unit})</span>}
                </label>
                <input type={f.unit === 'text' ? 'text' : 'number'}
                        step={f.unit === 'text' ? undefined : '0.01'}
                        data-testid={`bank-field-${f.key}`}
                        value={assumptions[f.key] ?? ''}
                        onChange={e => onFieldChange(f.key, e.target.value,
                                                        f.unit !== 'text')}
                        className="w-full px-2.5 py-1.5 border border-slate-300
                            rounded-md text-sm focus:outline-none
                            focus:ring-2 focus:ring-[#2563EB]/30"/>
                {f.hint && (
                  <div className="text-[10px] text-slate-400">{f.hint}</div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Historicals preview */}
      <details className="bg-white border border-slate-200 rounded-xl group">
        <summary className="p-4 cursor-pointer flex items-center justify-between
                              font-semibold text-slate-900">
          <span className="flex items-center gap-2">
            <Info size={16} className="text-slate-500" />
            Historical & Projection Preview (from Tally)
          </span>
          <span className="text-xs text-slate-500 group-open:hidden">
            Click to expand
          </span>
        </summary>
        <div className="border-t border-slate-100 p-4 overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-slate-500 border-b border-slate-200">
                <th className="text-left py-2 pr-3">Metric</th>
                {[...historicals, ...projections].map(fy => (
                  <th key={fy.fy_label} className="text-right py-2 px-2">
                    {fy.fy_label}
                    <div className="text-[10px] text-slate-400 font-normal">
                      {historicals.some(h => h.fy_label === fy.fy_label)
                        ? 'Actual/Est.' : 'Projected'}
                    </div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {[
                ['Net Sales', 'net_sales'],
                ['Purchases', 'purchases'],
                ['SG&A', 'sga_expenses'],
                ['Interest', 'interest'],
                ['Depreciation', 'depreciation'],
                ['Sundry Debtors', 'receivables_domestic'],
                ['Sundry Creditors', 'sundry_creditors'],
                ['Inventory (FG)', 'inventory_finished'],
                ['Term Loans', 'term_loans'],
                ['Capital', 'proprietors_capital'],
              ].map(([label, key]) => (
                <tr key={key} className="border-b border-slate-100">
                  <td className="py-1.5 pr-3 text-slate-700">{label}</td>
                  {[...historicals, ...projections].map(fy => (
                    <td key={fy.fy_label + key}
                         className="py-1.5 px-2 text-right text-slate-600 tabular-nums">
                      {(fy[key] ?? 0).toLocaleString('en-IN',
                                                       { maximumFractionDigits: 2 })}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
          <div className="text-[10px] text-slate-400 mt-2">
            All figures in Rs. Lacs. Historicals aggregate from
            sales_vouchers, purchase_vouchers, and all_ledgers — filtered
            strictly by your tenant + selected company.
          </div>
        </div>
      </details>

      {/* Download buttons */}
      <div className="bg-white border border-slate-200 rounded-xl p-5">
        <h3 className="font-semibold text-slate-900 mb-1">
          {activeSubTab === 'cma' ? 'Download CMA' : 'Download Pitch Deck'}
        </h3>
        <div className="text-xs text-slate-500 mb-4">
          Each file carries the company name in the header, and
          "Auto-generated by FLOWRA" with a timestamp in the footer of
          every page. The methodology page inside each file explains every
          formula.
        </div>
        {activeSubTab === 'cma' ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <DownloadBtn
              testid="dl-cma-pdf"
              icon={FileText}
              title="CMA Report — PDF"
              subtitle="5 forms · bank submission ready"
              disabled={downloading === 'CMA PDF'}
              busy={downloading === 'CMA PDF'}
              onClick={() => generate('/ca-reports/cma/pdf',
                                         'CMA_Report.pdf',
                                         'CMA PDF')}
            />
            <DownloadBtn
              testid="dl-cma-xlsx"
              icon={FileText}
              title="CMA Report — Excel"
              subtitle="6 sheets · editable"
              disabled={downloading === 'CMA XLSX'}
              busy={downloading === 'CMA XLSX'}
              onClick={() => generate('/ca-reports/cma/xlsx',
                                         'CMA_Report.xlsx',
                                         'CMA XLSX')}
            />
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <DownloadBtn
              testid="dl-pitch-pdf"
              icon={Sparkles}
              title="Pitch Deck — PDF"
              subtitle="16 pages · full investor deck"
              disabled={downloading === 'Pitch PDF'}
              busy={downloading === 'Pitch PDF'}
              onClick={() => generate('/ca-reports/pitch/pdf',
                                         'Pitch_Deck.pdf',
                                         'Pitch PDF')}
            />
            <DownloadBtn
              testid="dl-pitch-teaser"
              icon={FileText}
              title="Teaser — PDF"
              subtitle="10 pages · WhatsApp-friendly"
              disabled={downloading === 'Teaser PDF'}
              busy={downloading === 'Teaser PDF'}
              onClick={() => generate('/ca-reports/pitch/teaser',
                                         'Pitch_Teaser.pdf',
                                         'Teaser PDF')}
            />
            <DownloadBtn
              testid="dl-pitch-xlsx"
              icon={FileText}
              title="Projections — Excel"
              subtitle="8 sheets · editable model"
              disabled={downloading === 'Projections XLSX'}
              busy={downloading === 'Projections XLSX'}
              onClick={() => generate('/ca-reports/pitch/xlsx',
                                         'Projections.xlsx',
                                         'Projections XLSX')}
            />
          </div>
        )}
      </div>
    </div>
  );
};

const DownloadBtn = ({ testid, icon: Icon, title, subtitle, onClick,
                        disabled, busy }) => (
  <button data-testid={testid}
           onClick={onClick} disabled={disabled}
           className="flex items-start gap-3 p-4 border border-slate-200
              hover:border-[#2563EB] hover:bg-blue-50/40 rounded-lg
              text-left transition-all disabled:opacity-60
              disabled:cursor-not-allowed">
    <div className="p-2 bg-blue-50 rounded-lg text-[#2563EB]">
      {busy ? <Loader className="animate-spin" size={18}/> : <Icon size={18}/>}
    </div>
    <div className="flex-1">
      <div className="font-semibold text-slate-900 text-sm">{title}</div>
      <div className="text-xs text-slate-500 mt-0.5">{subtitle}</div>
    </div>
    <Download size={16} className="text-slate-400 mt-1" />
  </button>
);

export default CAReports;
