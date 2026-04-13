import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { ChevronRight, ChevronLeft, X } from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

const STEPS = [
  { target: '[data-testid="nav-dashboard"]', title: 'Dashboard', text: 'Your business overview — sales, overdue payments, inventory health, and top customers at a glance.' },
  { target: '[data-testid="nav-inventory"]', title: 'Inventory', text: 'All your stock items synced from Tally*. Click "Auto Reorder" to set smart reorder levels based on 2-month sales.' },
  { target: '[data-testid="nav-crm"]', title: 'CRM', text: 'Customer outstanding balances, targets, follow-ups, and payment behavior. Export to Excel anytime.' },
  { target: '[data-testid="nav-analytics"]', title: 'Analytics', text: 'Deep insights — inventory movement, below-cost sales, sales frequency, and customer-item breakdown.' },
  { target: '[data-testid="nav-referral"]', title: 'Refer & Earn', text: 'Share your referral code. Earn 3% commission when they subscribe!' },
  { target: '[data-testid="nav-setup"]', title: 'Setup', text: 'Connect Tally* and configure sync settings. Start here if you haven\'t connected yet.' },
  { target: '[data-testid="fy-selector"]', title: 'Financial Year', text: 'Switch between FYs. All reports filter by the selected year.' },
];

const OnboardingTour = ({ run, onComplete }) => {
  const [step, setStep] = useState(0);
  const [pos, setPos] = useState({ top: 0, left: 0, width: 0 });
  const overlayRef = useRef(null);

  useEffect(() => {
    if (!run) return;
    const el = document.querySelector(STEPS[step].target);
    if (el) {
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
  }, [step, run]);

  const finish = async () => {
    try { await axios.post(`${API}/auth/complete-onboarding`); } catch {}
    localStorage.setItem('flowra_onboarding_done', 'true');
    onComplete();
  };

  const next = () => { if (step < STEPS.length - 1) setStep(step + 1); else finish(); };
  const prev = () => { if (step > 0) setStep(step - 1); };

  if (!run) return null;

  const s = STEPS[step];
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
          <span className="text-[#2563EB] text-xs font-bold uppercase tracking-wider">Step {step + 1} of {STEPS.length}</span>
          <button onClick={finish} className="text-slate-400 hover:text-slate-600" data-testid="tour-skip"><X size={16} /></button>
        </div>
        <h3 className="text-lg font-bold text-slate-900 mb-1.5">{s.title}</h3>
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
              {step === STEPS.length - 1 ? 'Get Started!' : 'Next'} {step < STEPS.length - 1 && <ChevronRight size={14} />}
            </button>
          </div>
        </div>
        {/* Progress dots */}
        <div className="flex justify-center gap-1.5 mt-4">
          {STEPS.map((_, i) => (
            <div key={i} className={`w-2 h-2 rounded-full transition-colors ${i === step ? 'bg-[#2563EB]' : i < step ? 'bg-blue-200' : 'bg-slate-200'}`} />
          ))}
        </div>
      </div>
    </div>
  );
};

export default OnboardingTour;
