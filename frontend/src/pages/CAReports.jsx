import React, { useEffect, useState, useCallback } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import {
  FileText, Download, Loader, RefreshCw, ShieldCheck, Info,
  AlertTriangle, Landmark, Sparkles, Lock, Plus, Trash2, X,
  Bell, Upload, FileDown,
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
  const [manualRows, setManualRows] = useState([]);
  const [manualForm, setManualForm] = useState(null);   // null = closed
  const [manualSaving, setManualSaving] = useState(false);
  const [csvOpen, setCsvOpen] = useState(false);
  const [reminder, setReminder] = useState(null);

  const loadManual = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/ca-reports/manual-historicals`);
      if (res.data?.success) setManualRows(res.data.data.historicals || []);
    } catch { /* silent — non-blocking */ }
  }, []);

  const loadReminder = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/ca-reports/reminders/status`);
      if (res.data?.success) setReminder(res.data.data);
    } catch { /* silent */ }
  }, []);

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

  useEffect(() => { loadPreview(); loadManual(); loadReminder(); },
             [loadPreview, loadManual, loadReminder]);

  const openNewManual = () => {
    setManualForm({
      fy_label: '', net_sales: '', purchases: '', sga_expenses: '',
      depreciation: '', interest: '', provision_for_tax: '',
      sundry_creditors: '', receivables_domestic: '',
      inventory_finished: '', cash_bank_balance: '',
      bank_st_borrowings: '', term_loans: '', unsecured_loans: '',
      proprietors_capital: '', reserves_surplus: '', gross_block: '',
    });
  };

  const openEditManual = (row) => setManualForm({ ...row });

  const saveManual = async () => {
    if (!manualForm?.fy_label ||
         !/^\d{4}-\d{2}$/.test(manualForm.fy_label)) {
      toast.error("Enter FY label as 'YYYY-YY' (e.g. '2020-21').");
      return;
    }
    setManualSaving(true);
    try {
      const res = await axios.post(`${API}/ca-reports/manual-historicals`,
                                     manualForm);
      if (res.data?.success) {
        toast.success(`FY ${manualForm.fy_label} saved (encrypted)`);
        setManualForm(null);
        await Promise.all([loadManual(), loadPreview()]);
      } else {
        toast.error(res.data?.error || 'Save failed');
      }
    } catch (e) {
      toast.error(e.response?.data?.error || 'Save failed');
    } finally {
      setManualSaving(false);
    }
  };

  const deleteManual = async (fy_label) => {
    if (!window.confirm(`Delete manual FY ${fy_label}?`)) return;
    try {
      const res = await axios.delete(
        `${API}/ca-reports/manual-historicals/${encodeURIComponent(fy_label)}`);
      if (res.data?.success) {
        toast.success(`FY ${fy_label} removed`);
        await Promise.all([loadManual(), loadPreview()]);
      } else toast.error(res.data?.error || 'Delete failed');
    } catch (e) {
      toast.error(e.response?.data?.error || 'Delete failed');
    }
  };

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
      // v135 — a CMA generation resets the annual reminder clock, so
      // refresh the reminder status card in the background.
      if (keyLabel.startsWith('CMA')) loadReminder();
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
      <div className="space-y-4">
        <div className="bg-white border border-slate-200 rounded-xl p-6 text-center"
               data-testid="ca-reports-empty">
          <AlertTriangle className="mx-auto text-amber-500 mb-2" size={26} />
          <div className="text-slate-700 font-medium mb-1">
            No historical data available yet.
          </div>
          <div className="text-slate-500 text-sm max-w-xl mx-auto">
            The CMA needs at least one historical FY. You can either sync a
            Tally / Busy company via the desktop agent, OR type in the audited
            numbers for a prior year in the form below.
          </div>
          <button onClick={loadPreview}
                   data-testid="btn-reload-preview"
                   className="mt-3 px-3 py-1.5 bg-[#2563EB] text-white text-sm rounded-lg">
            Retry
          </button>
        </div>
        <ManualHistoricalsSection
          rows={manualRows}
          onNew={openNewManual}
          onEdit={openEditManual}
          onDelete={deleteManual}
          onImportCsv={() => setCsvOpen(true)}
        />
        {manualForm && (
          <ManualHistoricalForm
            row={manualForm}
            setRow={setManualForm}
            onSave={saveManual}
            onCancel={() => setManualForm(null)}
            saving={manualSaving}
          />
        )}
        {csvOpen && (
          <CsvImportModal
            onClose={() => setCsvOpen(false)}
            onImported={async () => {
              setCsvOpen(false);
              await Promise.all([loadManual(), loadPreview()]);
            }}
          />
        )}
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

      {/* v135 — annual reminder status card */}
      <ReminderStatusCard status={reminder} />

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

      {/* Prior-Year Manual Entry (useful when Tally sync < 2 FYs, or when
           the CA wants to override the audited numbers) */}
      <ManualHistoricalsSection
        rows={manualRows}
        onNew={openNewManual}
        onEdit={openEditManual}
        onDelete={deleteManual}
        onImportCsv={() => setCsvOpen(true)}
      />
      {manualForm && (
        <ManualHistoricalForm
          row={manualForm}
          setRow={setManualForm}
          onSave={saveManual}
          onCancel={() => setManualForm(null)}
          saving={manualSaving}
        />
      )}
      {csvOpen && (
        <CsvImportModal
          onClose={() => setCsvOpen(false)}
          onImported={async () => {
            setCsvOpen(false);
            await Promise.all([loadManual(), loadPreview()]);
          }}
        />
      )}

      {/* Download buttons */}
      <div className="bg-white border border-slate-200 rounded-xl p-5">
        <h3 className="font-semibold text-slate-900 mb-1">
          {activeSubTab === 'cma' ? 'Download CMA' : 'Download Pitch Deck'}
        </h3>
        <div className="text-xs text-slate-500 mb-4">
          Each file carries the company name in the header, and
          &ldquo;Auto-generated by FLOWRA&rdquo; with a timestamp in the footer of
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

/* ─── Prior-Year Manual Entry ─────────────────────────────────────────── */

const ManualHistoricalsSection = ({ rows, onNew, onEdit, onDelete,
                                      onImportCsv }) => (
  <div className="bg-white border border-slate-200 rounded-xl p-5"
        data-testid="manual-historicals-section">
    <div className="flex items-start justify-between mb-3 gap-3 flex-wrap">
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          <h3 className="font-semibold text-slate-900">
            Prior-Year Manual Entry
          </h3>
          <span className="text-xs bg-emerald-50 text-emerald-700 border
                  border-emerald-200 px-2 py-0.5 rounded-full">
            Encrypted at rest
          </span>
        </div>
        <div className="text-xs text-slate-500 mt-1 max-w-2xl">
          If your Tally / Busy sync doesn&apos;t yet cover 2 historical FYs
          (typical for new deployments), type in the audited numbers for
          up to 2 prior years here. These entries merge with the Tally-
          synced FYs so your CMA ships with a complete 5-column layout
          (2 historicals + 3 projections). All monetary fields are
          Fernet-AES-128 encrypted at rest — only you (useradmin) can
          read them back.
        </div>
      </div>
      <div className="flex gap-2">
        <button onClick={onImportCsv}
                 data-testid="btn-import-csv"
                 className="flex items-center gap-1.5 px-3 py-1.5 border
                    border-slate-300 hover:bg-slate-50 text-slate-700
                    text-sm rounded-lg whitespace-nowrap">
          <Upload size={14}/> Import CSV
        </button>
        <button onClick={onNew}
                 data-testid="btn-add-manual-fy"
                 className="flex items-center gap-1.5 px-3 py-1.5 bg-[#2563EB]
                    hover:bg-[#1D4ED8] text-white text-sm rounded-lg
                    whitespace-nowrap">
          <Plus size={14}/> Add prior year
        </button>
      </div>
    </div>
    {rows.length === 0 ? (
      <div className="text-sm text-slate-400 italic py-3">
        No manual entries yet.
      </div>
    ) : (
      <div className="mt-2 border border-slate-200 rounded-lg overflow-hidden">
        <table className="w-full text-xs">
          <thead className="bg-slate-50 text-slate-600">
            <tr>
              <th className="text-left py-2 px-3">FY</th>
              <th className="text-right py-2 px-3">Net Sales</th>
              <th className="text-right py-2 px-3">Purchases</th>
              <th className="text-right py-2 px-3">Debtors</th>
              <th className="text-right py-2 px-3">Creditors</th>
              <th className="text-right py-2 px-3">Capital</th>
              <th className="py-2 px-3 w-24"></th>
            </tr>
          </thead>
          <tbody>
            {rows.map(r => (
              <tr key={r.fy_label}
                   data-testid={`manual-row-${r.fy_label}`}
                   className="border-t border-slate-100">
                <td className="py-2 px-3 font-medium text-slate-900">
                  {r.fy_label}
                </td>
                {['net_sales', 'purchases', 'receivables_domestic',
                   'sundry_creditors', 'proprietors_capital'].map(f => (
                  <td key={f} className="py-2 px-3 text-right tabular-nums text-slate-600">
                    {(Number(r[f]) || 0).toLocaleString('en-IN',
                                                          { maximumFractionDigits: 2 })}
                  </td>
                ))}
                <td className="py-2 px-3">
                  <div className="flex gap-1 justify-end">
                    <button onClick={() => onEdit(r)}
                             data-testid={`btn-edit-manual-${r.fy_label}`}
                             className="text-slate-500 hover:text-[#2563EB] text-xs px-2 py-0.5">
                      Edit
                    </button>
                    <button onClick={() => onDelete(r.fy_label)}
                             data-testid={`btn-delete-manual-${r.fy_label}`}
                             className="text-slate-500 hover:text-red-600 p-1">
                      <Trash2 size={13}/>
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    )}
  </div>
);

const MANUAL_FIELDS = [
  { section: 'P&L (from audited P&L statement)', fields: [
    ['net_sales', 'Net Sales'],
    ['purchases', 'Purchases'],
    ['sga_expenses', 'SG&A Expenses'],
    ['depreciation', 'Depreciation'],
    ['interest', 'Interest'],
    ['provision_for_tax', 'Tax provision'],
  ]},
  { section: 'Balance Sheet (from audited BS)', fields: [
    ['sundry_creditors', 'Sundry Creditors'],
    ['bank_st_borrowings', 'Bank OD / CC (ST)'],
    ['term_loans', 'Term Loans (Long)'],
    ['unsecured_loans', 'Unsecured Loans'],
    ['proprietors_capital', 'Proprietor\'s Capital'],
    ['reserves_surplus', 'Reserves & Surplus'],
    ['cash_bank_balance', 'Cash & Bank'],
    ['receivables_domestic', 'Sundry Debtors'],
    ['inventory_finished', 'Inventory'],
    ['gross_block', 'Gross Fixed Assets'],
  ]},
];

const ManualHistoricalForm = ({ row, setRow, onSave, onCancel, saving }) => (
  <div className="fixed inset-0 bg-slate-900/50 flex items-center justify-center
                    z-50 p-4"
        data-testid="manual-fy-modal">
    <div className="bg-white rounded-xl w-full max-w-3xl max-h-[90vh]
                      overflow-y-auto shadow-xl">
      <div className="sticky top-0 bg-white border-b border-slate-200 px-5 py-4
                        flex items-center justify-between">
        <div>
          <div className="font-semibold text-slate-900">
            Add / Edit Prior-Year Historical
          </div>
          <div className="text-xs text-slate-500 mt-0.5">
            All values in Rs. Lacs. Encrypted at rest. Only fields you enter
            are used — leave irrelevant ones blank.
          </div>
        </div>
        <button onClick={onCancel} className="text-slate-500 hover:text-slate-900">
          <X size={18}/>
        </button>
      </div>
      <div className="p-5 space-y-4">
        <div>
          <label className="text-xs font-medium text-slate-700 block mb-1">
            Financial year label
            <span className="text-slate-400 ml-1">(e.g. 2020-21)</span>
          </label>
          <input type="text" placeholder="2020-21" maxLength={7}
                  data-testid="manual-fy-label"
                  value={row.fy_label || ''}
                  onChange={e => setRow(p => ({...p, fy_label: e.target.value}))}
                  className="w-40 px-2.5 py-1.5 border border-slate-300 rounded-md
                      text-sm focus:outline-none focus:ring-2
                      focus:ring-[#2563EB]/30"/>
        </div>
        {MANUAL_FIELDS.map(sec => (
          <div key={sec.section}>
            <div className="text-xs font-semibold text-slate-500 mb-2 mt-3
                              uppercase tracking-wide">
              {sec.section}
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {sec.fields.map(([key, label]) => (
                <div key={key} className="flex flex-col gap-1">
                  <label className="text-xs font-medium text-slate-700">
                    {label}
                  </label>
                  <input type="number" step="0.01"
                          data-testid={`manual-field-${key}`}
                          value={row[key] ?? ''}
                          onChange={e => setRow(p => ({
                            ...p, [key]: e.target.value === '' ? '' :
                                          Number(e.target.value),
                          }))}
                          className="w-full px-2.5 py-1.5 border border-slate-300
                              rounded-md text-sm focus:outline-none
                              focus:ring-2 focus:ring-[#2563EB]/30"/>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
      <div className="sticky bottom-0 bg-white border-t border-slate-200 px-5 py-3
                        flex justify-end gap-2">
        <button onClick={onCancel}
                 data-testid="btn-cancel-manual"
                 className="px-4 py-1.5 border border-slate-300 hover:bg-slate-50
                    text-slate-700 text-sm rounded-lg">
          Cancel
        </button>
        <button onClick={onSave}
                 disabled={saving}
                 data-testid="btn-save-manual"
                 className="px-4 py-1.5 bg-[#2563EB] hover:bg-[#1D4ED8]
                    text-white text-sm rounded-lg disabled:opacity-60
                    flex items-center gap-1.5">
          {saving && <Loader className="animate-spin" size={14}/>}
          Save
        </button>
      </div>
    </div>
  </div>
);

/* ─── Annual reminder status card ─────────────────────────────────────── */

const ReminderStatusCard = ({ status }) => {
  if (!status || !status.last_generated_at) {
    return (
      <div className="bg-white border border-slate-200 rounded-xl p-4 flex
                        items-start gap-3 text-sm"
             data-testid="reminder-card">
        <Bell size={16} className="text-slate-400 mt-0.5" />
        <div>
          <div className="font-medium text-slate-800">
            Annual reminder: not yet armed
          </div>
          <div className="text-xs text-slate-500 mt-0.5">
            Generate your first CMA (PDF or Excel) and we&apos;ll email you a
            renewal nudge 60 days before the 1-year anniversary. The
            reminder resets every time you regenerate.
          </div>
        </div>
      </div>
    );
  }
  const days = status.days_until_reminder;
  const alreadySent = !!status.reminder_sent_at;
  const isDue = days !== null && days <= 0;
  const armed = !alreadySent && !isDue && days !== null;
  const tone = isDue ? 'red' : (armed ? 'blue' : 'slate');
  const bg = { red: 'bg-red-50 border-red-200 text-red-700',
                 blue: 'bg-blue-50 border-blue-200 text-blue-800',
                 slate: 'bg-slate-50 border-slate-200 text-slate-700'
               }[tone];
  const lastDate = new Date(status.last_generated_at).toLocaleDateString(
    'en-IN', { day: '2-digit', month: 'short', year: 'numeric' });
  return (
    <div className={`border rounded-xl p-4 ${bg}`}
          data-testid="reminder-card">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <Bell size={18} className="mt-0.5"/>
          <div>
            <div className="font-semibold text-sm">
              {isDue ? 'CMA renewal is due — banker wants fresh numbers'
                       : (alreadySent
                            ? 'Reminder already sent for this cycle'
                            : `CMA renewal reminder armed`)}
            </div>
            <div className="text-xs mt-1 opacity-80">
              Last CMA generated on <b>{lastDate}</b> ({status.last_artifact_kind?.toUpperCase() || 'PDF'}).
              {days !== null && !alreadySent && (
                <> Nudge email will fire in <b>{Math.max(days, 0)} days</b>.</>
              )}
              {alreadySent && (
                <> Regenerate the CMA below to re-arm the annual clock.</>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

/* ─── CSV bulk import modal ───────────────────────────────────────────── */

const CsvImportModal = ({ onClose, onImported }) => {
  const [file, setFile] = useState(null);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);

  const downloadTemplate = async () => {
    try {
      const res = await axios.get(
        `${API}/ca-reports/manual-historicals/csv-template`,
        { responseType: 'blob' });
      const blob = new Blob([res.data]);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url; a.download = 'manual_historicals_template.csv'; a.click();
      window.URL.revokeObjectURL(url);
    } catch {
      toast.error('Template download failed');
    }
  };

  const runImport = async () => {
    if (!file) { toast.error('Pick a CSV file first'); return; }
    setBusy(true);
    try {
      const csv_text = await file.text();
      const res = await axios.post(
        `${API}/ca-reports/manual-historicals/import-csv`,
        { csv_text });
      if (res.data?.success) {
        setResult(res.data.data);
        const { written, errors } = res.data.data;
        if (written > 0) {
          toast.success(
            `Imported ${written} row${written === 1 ? '' : 's'}`);
        }
        if (errors?.length === 0) {
          setTimeout(onImported, 800);
        }
      } else {
        toast.error(res.data?.error || 'Import failed');
      }
    } catch (e) {
      toast.error(e.response?.data?.error || 'Import failed');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-slate-900/50 flex items-center justify-center
                      z-50 p-4"
          data-testid="csv-import-modal">
      <div className="bg-white rounded-xl w-full max-w-lg shadow-xl">
        <div className="border-b border-slate-200 px-5 py-4 flex items-center
                          justify-between">
          <div>
            <div className="font-semibold text-slate-900">
              Bulk-import prior FYs from CSV
            </div>
            <div className="text-xs text-slate-500 mt-0.5">
              Paste rows from Excel to fill years all at once
            </div>
          </div>
          <button onClick={onClose} className="text-slate-500 hover:text-slate-900">
            <X size={18}/>
          </button>
        </div>
        <div className="p-5 space-y-4">
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-3
                            text-xs text-blue-800">
            <div className="font-medium mb-1">CSV format</div>
            First column must be <code>fy_label</code> (e.g. 2020-21). Every
            other column is a numeric field name from the
            HistoricalFY schema. Leave blank cells empty.
            <button onClick={downloadTemplate}
                     data-testid="btn-download-csv-template"
                     className="flex items-center gap-1.5 mt-2 text-blue-700
                        hover:text-blue-900 font-medium">
              <FileDown size={13}/> Download blank template
            </button>
          </div>
          <div>
            <label className="text-xs font-medium text-slate-700 block mb-1">
              Pick CSV file
            </label>
            <input type="file" accept=".csv,text/csv"
                    data-testid="csv-file-input"
                    onChange={e => setFile(e.target.files?.[0] || null)}
                    className="text-sm w-full"/>
            {file && (
              <div className="text-xs text-slate-500 mt-1">
                Selected: <b>{file.name}</b> ({(file.size / 1024).toFixed(1)} KB)
              </div>
            )}
          </div>
          {result && (
            <div className="text-sm bg-slate-50 border border-slate-200
                              rounded-lg p-3"
                  data-testid="csv-import-result">
              <div className="font-medium text-slate-900">
                {result.written} row{result.written === 1 ? '' : 's'} written
                {result.errors?.length ? ` · ${result.errors.length} errors`
                                         : ''}
              </div>
              {result.errors?.length > 0 && (
                <ul className="mt-2 text-xs text-red-600 list-disc pl-5">
                  {result.errors.slice(0, 5).map((e, i) => (
                    <li key={i}>{e}</li>
                  ))}
                  {result.errors_truncated && (
                    <li className="italic">…more errors truncated</li>
                  )}
                </ul>
              )}
            </div>
          )}
        </div>
        <div className="border-t border-slate-200 px-5 py-3 flex justify-end gap-2">
          <button onClick={onClose}
                   className="px-4 py-1.5 border border-slate-300 hover:bg-slate-50
                      text-slate-700 text-sm rounded-lg">
            Close
          </button>
          <button onClick={runImport} disabled={busy || !file}
                   data-testid="btn-run-csv-import"
                   className="px-4 py-1.5 bg-[#2563EB] hover:bg-[#1D4ED8]
                      text-white text-sm rounded-lg disabled:opacity-60
                      flex items-center gap-1.5">
            {busy && <Loader className="animate-spin" size={14}/>}
            Import
          </button>
        </div>
      </div>
    </div>
  );
};

export default CAReports;
