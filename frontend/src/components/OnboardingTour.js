import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { ChevronRight, ChevronLeft, X } from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

const ALL_STEPS = [
  { target: '[data-testid="nav-dashboard"]',     title: 'Dashboard',          text: 'Your business overview — sales, overdue payments, inventory health, and top customers at a glance.' },
  { target: '[data-testid="nav-sales"]',         title: 'Sales',              text: 'All sales vouchers with filters, search, and Excel export. Drill into invoices, line items, and salesman attribution.' },
  { target: '[data-testid="nav-inventory"]',     title: 'Inventory',          text: 'Stock items synced from Tally* or Busy. Use "Auto Reorder" to set smart reorder levels based on 2-month sales velocity.' },
  { target: '[data-testid="nav-crm"]',           title: 'CRM',                text: 'Customer outstanding balances, FY opening balances, targets, follow-ups, and payment behavior. Branch toggle, Excel export, ageing buckets.' },
  { target: '[data-testid="nav-analytics"]',     title: 'Analytics',          text: 'Inventory movement, below-cost sales, sales frequency, customer-item breakdown, SPIP analysis, and more.' },
  { target: '[data-testid="nav-salesman"]',      title: 'Salesman Orders',    label: 'NEW', text: 'Mobile-first order collection by salesmen with mapped customers. Approve, hold, reject, and verify pending billing against Tally invoices.' },
  { target: '[data-testid="nav-ai-reports"]',    title: 'AI Reports',         text: 'GPT-powered narrative reports — sales trends, customer insights, inventory movement, all in plain English.' },
  { target: '[data-testid="nav-insider"]',       title: 'Insider Result',     text: 'Quick AI cards on the most pressing patterns — slow movers, top customers shifting away, anomalies in payment behaviour.' },
  { target: '[data-testid="nav-ca-corner"]',     title: 'CA Corner',          label: 'NEW', text: 'Cash Flow, P&L, Balance Sheet, ledger drill-down, and AI-powered expense insights — built specifically for your Chartered Accountant.' },
  { target: '[data-testid="nav-dispatch"]',      title: 'Dispatch Terminal',  label: 'NEW', text: 'Warehouse Kanban board, LR tracking, transporter & porter settlement, Close-of-Day PDF, and pending billing verification.' },
  { target: '[data-testid="nav-sync-history"]',  title: 'Sync History',       text: 'Timeline of every sync cycle from your desktop agent — counts per data type, FY, sync mode, and which agent (Tally / Busy) ran it.' },
  { target: '[data-testid="nav-activity"]',      title: 'Activity Feed',      text: 'Audit log of who changed what — invoice edits, target updates, dispatch actions, salesman approvals.' },
  { target: '[data-testid="nav-referral"]',      title: 'Refer & Earn',       text: 'Share your referral code. Earn 3% commission on every paid subscription that signs up through you.' },
  { target: '[data-testid="nav-setup"]',         title: 'Setup',              text: 'Connect Tally* or Busy via the desktop agent and configure sync schedules. Start here if you haven\'t connected yet.' },
  { target: '[data-testid="company-switch-btn"]',title: 'Multi-Company',      text: 'Switch between your synced companies anytime. Each company has its own data, vouchers, and FYs.' },
  { target: '[data-testid="fy-selector"]',       title: 'Financial Year',     text: 'Switch between FYs. All reports, balances, and outstandings auto-filter by the selected year.' },
  { target: '[data-testid="branch-toggle"]',     title: 'Branch Filter',      text: 'Toggle to include or exclude branch ledgers from CRM outstanding balances and reports.' },
  { target: '[data-testid="sync-indicator"]',    title: 'Live Sync Status',   text: 'Green = your desktop agent is connected and syncing. Click Sync History for the full timeline.' },
  { target: '[data-testid="user-menu-btn"]',     title: 'Profile & Settings', text: 'Manage your subscription, employees, salesman accounts, password, and download your data anytime.' },
];

const OnboardingTour = ({ run, onComplete }) => {
  const [step, setStep] = useState(0);
  const [steps, setSteps] = useState([]);
  const [pos, setPos] = useState({ top: 0, left: 0, width: 0 });
  const overlayRef = useRef(null);

  // Build the active step list once when the tour starts — filter out targets that don't exist
  useEffect(() => {
    if (!run) return;
    const visible = ALL_STEPS.filter(s => document.querySelector(s.target));
    setSteps(visible);
    setStep(0);
  }, [run]);

  useEffect(() => {
    if (!run || !steps.length) return;
    const current = steps[step];
    if (!current) return;
    const el = document.querySelector(current.target);
    if (el) {
      el.scrollIntoView({ block: 'center', inline: 'center', behavior: 'smooth' });
      const rect = el.getBoundingClientRect();
      setPos({
        top: rect.bottom + window.scrollY + 12,
        left: Math.max(12, Math.min(rect.left + rect.width / 2 - 170, window.innerWidth - 352)),
        spotTop: rect.top + window.scrollY - 4,
        spotLeft: rect.left - 4,
        spotWidth: rect.width + 8,
        spotHeight: rect.height + 8,
      });
    }
  }, [step, run, steps]);

  const finish = async () => {
    try { await axios.post(`${API}/auth/complete-onboarding`); } catch { /* ignore */ }
    localStorage.setItem('flowra_onboarding_done', 'true');
    onComplete();
  };

  const next = () => { if (step < steps.length - 1) setStep(step + 1); else finish(); };
  const prev = () => { if (step > 0) setStep(step - 1); };

  if (!run || !steps.length) return null;

  const s = steps[step];
  return (
    <div ref={overlayRef} className="fixed inset-0 z-[9999]" data-testid="onboarding-overlay">
      {/* Overlay */}
      <div className="absolute inset-0 bg-black/50" onClick={finish} />

      {/* Spotlight */}
      <div className="absolute rounded-lg ring-2 ring-[#2563EB] ring-offset-2 bg-transparent pointer-events-none" style={{
        top: pos.spotTop, left: pos.spotLeft, width: pos.spotWidth, height: pos.spotHeight,
        boxShadow: '0 0 0 9999px rgba(0,0,0,0.5)',
      }} />

      {/* Tooltip */}
      <div className="absolute bg-white rounded-xl shadow-2xl p-5 w-[340px] animate-in fade-in" style={{ top: pos.top, left: pos.left }} data-testid="tour-tooltip">
        {/* Arrow */}
        <div className="absolute -top-2 left-[170px] w-4 h-4 bg-white rotate-45 rounded-sm" />

        <div className="flex items-center justify-between mb-3">
          <span className="text-[#2563EB] text-xs font-bold uppercase tracking-wider">Step {step + 1} of {steps.length}</span>
          <button onClick={finish} className="text-slate-400 hover:text-slate-600" data-testid="tour-skip"><X size={16} /></button>
        </div>
        <div className="flex items-center gap-2 mb-1.5">
          <h3 className="text-lg font-bold text-slate-900">{s.title}</h3>
          {s.label && (
            <span className="px-2 py-0.5 text-[10px] font-bold rounded-full bg-emerald-100 text-emerald-700 uppercase tracking-wider">
              {s.label}
            </span>
          )}
        </div>
        <p className="text-sm text-slate-600 leading-relaxed mb-4">{s.text}</p>
        <div className="flex items-center justify-between">
          <button onClick={finish} className="text-xs text-slate-400 hover:text-slate-600" data-testid="tour-skip-text">Skip Tour</button>
          <div className="flex gap-2">
            {step > 0 && (
              <button onClick={prev} className="flex items-center gap-1 px-3 py-2 border border-slate-200 rounded-lg text-sm text-slate-600 hover:bg-slate-50" data-testid="tour-prev">
                <ChevronLeft size={14} /> Back
              </button>
            )}
            <button onClick={next} className="flex items-center gap-1 px-4 py-2 bg-[#2563EB] text-white rounded-lg text-sm font-medium hover:bg-[#1D4ED8]" data-testid="tour-next">
              {step === steps.length - 1 ? 'Get Started!' : 'Next'} {step < steps.length - 1 && <ChevronRight size={14} />}
            </button>
          </div>
        </div>
        {/* Progress dots */}
        <div className="flex justify-center gap-1.5 mt-4 flex-wrap">
          {steps.map((_, i) => (
            <div key={i} className={`w-2 h-2 rounded-full transition-colors ${i === step ? 'bg-[#2563EB]' : i < step ? 'bg-blue-200' : 'bg-slate-200'}`} />
          ))}
        </div>
      </div>
    </div>
  );
};

export default OnboardingTour;
