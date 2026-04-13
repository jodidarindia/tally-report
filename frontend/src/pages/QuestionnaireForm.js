import React, { useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import {
  Building2, User, Phone, Mail, MapPin, Briefcase, ChevronRight, ChevronLeft,
  Check, ClipboardList, Send, ArrowLeft
} from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

const INDUSTRIES = ["Distributor / Wholesaler", "Manufacturer", "Retailer", "Trader / Commission Agent", "Service Provider", "Other"];
const EMPLOYEE_RANGES = ["1-5", "6-15", "16-50", "51-200", "200+"];
const TURNOVER_RANGES = ["Below Rs.50 Lakh", "Rs.50 Lakh - 2 Crore", "Rs.2 Crore - 10 Crore", "Rs.10 Crore - 50 Crore", "Above Rs.50 Crore"];
const TALLY_VERSIONS = ["Tally Prime (Latest)", "Tally Prime (Older release)", "Tally ERP 9", "Not sure"];
const REMOTE_ACCESS_OPTIONS = ["We don't - office only", "Tally on Mobile app", "Remote Desktop / TeamViewer", "WhatsApp photos from accountant", "Manual Excel exports emailed", "Other"];
const TALLY_ROLES = ["Accountant / Bookkeeper", "Business Owner / Director", "Sales Team", "Warehouse / Inventory Team", "CA / External Auditor"];
const PAIN_POINTS = [
  "Cannot check sales / outstanding from phone when traveling",
  "Manual Excel exports take too much time (3-4 hrs/week)",
  "Branch transfers inflate my actual sales figures",
  "No visibility into customer payment behavior",
  "Dead stock / slow-moving items pile up unnoticed",
  "Cannot get Cash Flow or P&L without waiting for accountant",
  "No way to set and track customer-wise sales targets",
  "Reorder levels are guesswork - no data-driven suggestions",
  "Multiple Tally companies but no unified view",
  "Security concern - employees share Tally login",
  "No audit trail of who accessed what data",
];
const FEATURES_LIST = [
  "Live Dashboard (sales, inventory, outstanding overview)",
  "Sales Analytics (trends, voucher drill-down, customer breakdown)",
  "Customer CRM (targets, follow-ups, payment behavior scoring)",
  "Outstanding & Overdue Management with Excel Export",
  "Inventory with Stock Alerts & Smart Auto-Reorder",
  "Movement Analysis (Opening > Inward > Sales > Closing)",
  "Below Cost Sales Detection (negative margin alerts)",
  "AI-Powered Purchase Order Recommendations",
  "CA Corner: Cash Flow Statement (Indirect Method)",
  "CA Corner: P&L Report (Annual + Monthly Toggle)",
  "CA Corner: AI Expense Insights & Health Score",
  "Branch Toggle (exclude internal transfers)",
  "Refer & Earn (3% commission on referrals)",
  "Mobile Access (phone & tablet)",
  "Multi-Company Support",
];
const DECISION_FACTORS = ["Price / Value for money", "Ease of setup", "Data security & encryption", "Mobile access", "Specific features", "Customer support quality", "Integration with Tally* without changes"];
const TIMELINES = ["Immediately (this week)", "Within 1 month", "Within 3 months", "Just exploring / no timeline"];
const DECISION_MAKERS = ["I am the decision maker", "Need to consult with partner / director", "IT team will evaluate", "CA / Auditor recommendation needed"];
const BUDGETS = ["Below Rs.500/mo", "Rs.500 - Rs.1,000/mo", "Rs.1,000 - Rs.2,500/mo", "Rs.2,500 - Rs.4,000/mo", "Above Rs.4,000/mo"];
const HEARD_FROM = ["Google Search", "LinkedIn / Social Media", "Referral from another business", "WhatsApp message", "Trade show / event", "CA / Accountant recommendation", "Other"];
const NEXT_STEPS_OPTIONS = ["Start a 14-day free trial right now", "Schedule a live demo", "Receive pricing details via email", "Get a call back", "Share this with my team first"];

const STEPS = [
  { id: 'company', title: 'Company Info', icon: Building2 },
  { id: 'tally', title: 'Tally* Usage', icon: ClipboardList },
  { id: 'pain', title: 'Pain Points', icon: ClipboardList },
  { id: 'features', title: 'Feature Priority', icon: ClipboardList },
  { id: 'decision', title: 'Decision & Budget', icon: Briefcase },
  { id: 'next', title: 'Next Steps', icon: Send },
];

const QuestionnaireForm = ({ onBack }) => {
  const [step, setStep] = useState(0);
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [form, setForm] = useState({
    company_name: '', contact_person: '', designation: '', phone: '', email: '', city: '',
    industry: '', employees: '', turnover: '',
    tally_version: '', tally_companies: '', tally_users: '', has_branches: '', branch_count: '',
    remote_access: [], tally_users_roles: [],
    pain_points: [], biggest_challenge: '',
    feature_ratings: {},
    decision_factors: [], timeline: '', decision_maker: '', budget: '', additional_features: '',
    heard_from: '', next_steps: [], callback_time: '', notes: '',
    submitted_by: 'prospect',
  });

  const set = (key, val) => setForm(prev => ({ ...prev, [key]: val }));
  const toggleArr = (key, val) => setForm(prev => ({
    ...prev, [key]: prev[key].includes(val) ? prev[key].filter(v => v !== val) : [...prev[key], val]
  }));
  const setRating = (feat, val) => setForm(prev => ({
    ...prev, feature_ratings: { ...prev.feature_ratings, [feat]: val }
  }));

  const handleSubmit = async () => {
    if (!form.company_name && !form.contact_person && !form.phone) {
      toast.error('Please fill at least company name, contact person, or phone.');
      return;
    }
    setSubmitting(true);
    try {
      const res = await axios.post(`${API}/questionnaire/submit`, form);
      if (res.data?.success) {
        setSubmitted(true);
        toast.success('Submitted successfully!');
      } else {
        toast.error(res.data?.error || 'Submission failed');
      }
    } catch {
      toast.error('Failed to submit. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  if (submitted) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4">
        <div className="bg-white rounded-2xl border border-slate-200 p-10 max-w-md text-center" data-testid="questionnaire-success">
          <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-5">
            <Check size={32} className="text-green-600" />
          </div>
          <h2 className="text-2xl font-bold text-slate-900 mb-3">Thank You!</h2>
          <p className="text-slate-600 mb-6">We've received your requirements. Our team will reach out to you shortly with a personalized recommendation.</p>
          <div className="flex gap-3 justify-center">
            <button onClick={onBack} className="px-6 py-2.5 bg-[#2563EB] text-white rounded-lg font-medium hover:bg-[#1D4ED8]" data-testid="back-to-home-btn">
              Back to Home
            </button>
          </div>
        </div>
      </div>
    );
  }

  const Checkbox = ({ label, checked, onChange }) => (
    <label className="flex items-start gap-2.5 cursor-pointer group py-1">
      <div className={`w-5 h-5 rounded border-2 flex items-center justify-center mt-0.5 shrink-0 transition-colors ${checked ? 'bg-[#2563EB] border-[#2563EB]' : 'border-slate-300 group-hover:border-slate-400'}`}>
        {checked && <Check size={12} className="text-white" />}
      </div>
      <span className="text-sm text-slate-700">{label}</span>
    </label>
  );

  const Radio = ({ label, checked, onChange }) => (
    <label className="flex items-center gap-2.5 cursor-pointer group py-1">
      <div className={`w-5 h-5 rounded-full border-2 flex items-center justify-center shrink-0 transition-colors ${checked ? 'border-[#2563EB]' : 'border-slate-300 group-hover:border-slate-400'}`}>
        {checked && <div className="w-2.5 h-2.5 rounded-full bg-[#2563EB]" />}
      </div>
      <span className="text-sm text-slate-700">{label}</span>
    </label>
  );

  const Input = ({ label, value, onChange, type = 'text', placeholder = '' }) => (
    <div>
      <label className="block text-sm font-medium text-slate-700 mb-1.5">{label}</label>
      <input type={type} value={value} onChange={e => onChange(e.target.value)}
        className="w-full px-3.5 py-2.5 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[#2563EB]/30 focus:border-[#2563EB]"
        placeholder={placeholder} data-testid={`q-${label.toLowerCase().replace(/[^a-z]/g, '-')}`} />
    </div>
  );

  const renderStep = () => {
    switch (step) {
      case 0: // Company Info
        return (
          <div className="space-y-4" data-testid="step-company">
            <div className="grid sm:grid-cols-2 gap-4">
              <Input label="Company Name" value={form.company_name} onChange={v => set('company_name', v)} placeholder="Your company name" />
              <Input label="Contact Person" value={form.contact_person} onChange={v => set('contact_person', v)} placeholder="Full name" />
            </div>
            <div className="grid sm:grid-cols-2 gap-4">
              <Input label="Designation" value={form.designation} onChange={v => set('designation', v)} placeholder="e.g. Owner, Director" />
              <Input label="Phone" value={form.phone} onChange={v => set('phone', v)} type="tel" placeholder="+91 XXXXX XXXXX" />
            </div>
            <div className="grid sm:grid-cols-2 gap-4">
              <Input label="Email" value={form.email} onChange={v => set('email', v)} type="email" placeholder="you@company.com" />
              <Input label="City / Location" value={form.city} onChange={v => set('city', v)} placeholder="e.g. Mumbai" />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">Industry / Business Type</label>
              <div className="grid sm:grid-cols-2 gap-1">
                {INDUSTRIES.map(i => <Radio key={i} label={i} checked={form.industry === i} onChange={() => set('industry', i)} />)}
              </div>
            </div>
            <div className="grid sm:grid-cols-2 gap-6">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">Number of Employees</label>
                {EMPLOYEE_RANGES.map(r => <Radio key={r} label={r} checked={form.employees === r} onChange={() => set('employees', r)} />)}
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">Annual Turnover (approx.)</label>
                {TURNOVER_RANGES.map(r => <Radio key={r} label={r} checked={form.turnover === r} onChange={() => set('turnover', r)} />)}
              </div>
            </div>
          </div>
        );

      case 1: // Tally Usage
        return (
          <div className="space-y-5" data-testid="step-tally">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">Which Tally* version are you using?</label>
              {TALLY_VERSIONS.map(v => <Radio key={v} label={v} checked={form.tally_version === v} onChange={() => set('tally_version', v)} />)}
            </div>
            <div className="grid sm:grid-cols-2 gap-4">
              <Input label="How many companies in Tally*?" value={form.tally_companies} onChange={v => set('tally_companies', v)} placeholder="e.g. 3" />
              <Input label="How many Tally* users / terminals?" value={form.tally_users} onChange={v => set('tally_users', v)} placeholder="e.g. 5" />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">Do you have multiple branches / depots?</label>
              <div className="flex gap-4 mb-2">
                <Radio label="Yes" checked={form.has_branches === 'yes'} onChange={() => set('has_branches', 'yes')} />
                <Radio label="No - Single location" checked={form.has_branches === 'no'} onChange={() => set('has_branches', 'no')} />
              </div>
              {form.has_branches === 'yes' && (
                <Input label="Number of branches" value={form.branch_count} onChange={v => set('branch_count', v)} placeholder="e.g. 4" />
              )}
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">How do you currently access Tally* data remotely?</label>
              {REMOTE_ACCESS_OPTIONS.map(o => <Checkbox key={o} label={o} checked={form.remote_access.includes(o)} onChange={() => toggleArr('remote_access', o)} />)}
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">Who uses Tally* in your organization?</label>
              <div className="grid sm:grid-cols-2 gap-1">
                {TALLY_ROLES.map(r => <Checkbox key={r} label={r} checked={form.tally_users_roles.includes(r)} onChange={() => toggleArr('tally_users_roles', r)} />)}
              </div>
            </div>
          </div>
        );

      case 2: // Pain Points
        return (
          <div className="space-y-5" data-testid="step-pain">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">What frustrates you most? (Check all that apply)</label>
              <div className="space-y-0.5">
                {PAIN_POINTS.map(p => <Checkbox key={p} label={p} checked={form.pain_points.includes(p)} onChange={() => toggleArr('pain_points', p)} />)}
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1.5">Describe your biggest daily challenge with Tally* data</label>
              <textarea value={form.biggest_challenge} onChange={e => set('biggest_challenge', e.target.value)}
                className="w-full px-3.5 py-2.5 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[#2563EB]/30 focus:border-[#2563EB] min-h-[100px]"
                placeholder="Tell us what slows you down the most..." data-testid="q-biggest-challenge" />
            </div>
          </div>
        );

      case 3: // Feature Priority
        return (
          <div className="space-y-3" data-testid="step-features">
            <p className="text-xs text-slate-500 mb-2">Rate each feature: 1 = Not Important, 3 = Nice to Have, 5 = Must Have</p>
            {FEATURES_LIST.map(feat => (
              <div key={feat} className="flex flex-col sm:flex-row sm:items-center gap-1 sm:gap-3 py-2 border-b border-slate-100 last:border-0">
                <span className="text-sm text-slate-700 sm:w-[55%]">{feat}</span>
                <div className="flex gap-2">
                  {[1, 2, 3, 4, 5].map(n => (
                    <button key={n} onClick={() => setRating(feat, n)}
                      className={`w-8 h-8 rounded-lg text-xs font-bold transition-colors ${form.feature_ratings[feat] === n ? 'bg-[#2563EB] text-white' : 'bg-slate-100 text-slate-500 hover:bg-slate-200'}`}
                      data-testid={`rating-${n}`}>
                      {n}
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </div>
        );

      case 4: // Decision Criteria
        return (
          <div className="space-y-5" data-testid="step-decision">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">What is most important to you in choosing a solution?</label>
              {DECISION_FACTORS.map(f => <Checkbox key={f} label={f} checked={form.decision_factors.includes(f)} onChange={() => toggleArr('decision_factors', f)} />)}
            </div>
            <div className="grid sm:grid-cols-2 gap-6">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">When are you looking to implement?</label>
                {TIMELINES.map(t => <Radio key={t} label={t} checked={form.timeline === t} onChange={() => set('timeline', t)} />)}
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">Who will make the final decision?</label>
                {DECISION_MAKERS.map(d => <Radio key={d} label={d} checked={form.decision_maker === d} onChange={() => set('decision_maker', d)} />)}
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">Budget range (per month)?</label>
              <div className="grid sm:grid-cols-2 gap-1">
                {BUDGETS.map(b => <Radio key={b} label={b} checked={form.budget === b} onChange={() => set('budget', b)} />)}
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1.5">Any specific features not mentioned above?</label>
              <textarea value={form.additional_features} onChange={e => set('additional_features', e.target.value)}
                className="w-full px-3.5 py-2.5 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[#2563EB]/30 focus:border-[#2563EB] min-h-[80px]"
                placeholder="Tell us what you need..." data-testid="q-additional-features" />
            </div>
          </div>
        );

      case 5: // Next Steps
        return (
          <div className="space-y-5" data-testid="step-next">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">How did you hear about FLOWRA?</label>
              <div className="grid sm:grid-cols-2 gap-1">
                {HEARD_FROM.map(h => <Radio key={h} label={h} checked={form.heard_from === h} onChange={() => set('heard_from', h)} />)}
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">What would you like to do next?</label>
              {NEXT_STEPS_OPTIONS.map(n => <Checkbox key={n} label={n} checked={form.next_steps.includes(n)} onChange={() => toggleArr('next_steps', n)} />)}
            </div>
            <Input label="Preferred call-back time" value={form.callback_time} onChange={v => set('callback_time', v)} placeholder="e.g. Weekdays 2-4 PM" />
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1.5">Additional notes / special requirements</label>
              <textarea value={form.notes} onChange={e => set('notes', e.target.value)}
                className="w-full px-3.5 py-2.5 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[#2563EB]/30 focus:border-[#2563EB] min-h-[80px]"
                placeholder="Anything else you'd like us to know..." data-testid="q-notes" />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">Who is filling this form?</label>
              <div className="flex gap-4">
                <Radio label="I am a prospective customer" checked={form.submitted_by === 'prospect'} onChange={() => set('submitted_by', 'prospect')} />
                <Radio label="FLOWRA sales rep" checked={form.submitted_by === 'employee'} onChange={() => set('submitted_by', 'employee')} />
              </div>
            </div>
          </div>
        );

      default: return null;
    }
  };

  const StepIcon = STEPS[step].icon;

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Header */}
      <header className="bg-white border-b border-slate-200 sticky top-0 z-40">
        <div className="max-w-3xl mx-auto px-4 h-14 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <button onClick={onBack} className="p-1.5 hover:bg-slate-100 rounded-lg" data-testid="q-back-btn">
              <ArrowLeft size={18} className="text-slate-600" />
            </button>
            <img src="/flowra-logo.png" alt="FLOWRA" className="h-7" />
            <span className="text-sm font-bold text-slate-900">FLOWRA</span>
          </div>
          <span className="text-xs text-slate-400">Needs Assessment</span>
        </div>
      </header>

      <div className="max-w-3xl mx-auto px-4 py-6">
        {/* Progress */}
        <div className="flex items-center gap-1 mb-6 overflow-x-auto" data-testid="q-progress">
          {STEPS.map((s, i) => (
            <button key={s.id} onClick={() => setStep(i)}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium whitespace-nowrap transition-colors ${
                i === step ? 'bg-[#2563EB] text-white' : i < step ? 'bg-blue-100 text-[#2563EB]' : 'bg-slate-100 text-slate-400'
              }`}>
              {i < step ? <Check size={12} /> : <span>{i + 1}</span>}
              <span className="hidden sm:inline">{s.title}</span>
            </button>
          ))}
        </div>

        {/* Step Content */}
        <div className="bg-white rounded-2xl border border-slate-200 p-6 sm:p-8">
          <div className="flex items-center gap-3 mb-6">
            <div className="w-10 h-10 bg-blue-50 rounded-xl flex items-center justify-center">
              <StepIcon size={20} className="text-[#2563EB]" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-slate-900">{STEPS[step].title}</h2>
              <p className="text-xs text-slate-500">Step {step + 1} of {STEPS.length}</p>
            </div>
          </div>

          {renderStep()}

          {/* Navigation */}
          <div className="flex items-center justify-between mt-8 pt-6 border-t border-slate-100">
            <button onClick={() => step > 0 && setStep(step - 1)} disabled={step === 0}
              className="flex items-center gap-1.5 px-4 py-2.5 border border-slate-200 rounded-lg text-sm font-medium text-slate-600 hover:bg-slate-50 disabled:opacity-30 disabled:cursor-not-allowed"
              data-testid="q-prev-btn">
              <ChevronLeft size={16} /> Previous
            </button>
            {step < STEPS.length - 1 ? (
              <button onClick={() => setStep(step + 1)}
                className="flex items-center gap-1.5 px-5 py-2.5 bg-[#2563EB] text-white rounded-lg text-sm font-medium hover:bg-[#1D4ED8]"
                data-testid="q-next-btn">
                Next <ChevronRight size={16} />
              </button>
            ) : (
              <button onClick={handleSubmit} disabled={submitting}
                className="flex items-center gap-1.5 px-6 py-2.5 bg-green-600 text-white rounded-lg text-sm font-medium hover:bg-green-700 disabled:opacity-50"
                data-testid="q-submit-btn">
                {submitting ? 'Submitting...' : 'Submit'} <Send size={14} />
              </button>
            )}
          </div>
        </div>

        {/* Disclaimer */}
        <p className="text-center text-[9px] text-slate-400 mt-6 max-w-lg mx-auto leading-relaxed">
          Tally* is the trademark of its respective owner and is not affiliated, endorsed, connected or sponsored in any way to this website, mobile application or any of our affiliate sites.
        </p>
      </div>
    </div>
  );
};

export default QuestionnaireForm;
