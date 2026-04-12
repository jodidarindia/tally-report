import React, { useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import {
  ArrowLeft, ArrowRight, Building2, User, Mail, Phone, MapPin,
  FileText, Loader, Check, Eye, Package, BarChart3, Users, Brain,
  Truck, Shield, Lightbulb, ChevronRight, Play
} from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

const AVAILABLE_FEATURES = [
  { id: 'dashboard', label: 'Dashboard & Overview', icon: BarChart3 },
  { id: 'sales', label: 'Sales Tracking', icon: BarChart3 },
  { id: 'crm', label: 'Customer CRM & Outstanding', icon: Users },
  { id: 'inventory', label: 'Inventory Management', icon: Package },
  { id: 'analytics', label: 'Movement Analytics', icon: BarChart3 },
  { id: 'salesman', label: 'Salesman Performance', icon: Truck },
  { id: 'ai_reports', label: 'AI-Powered Reports', icon: Brain },
  { id: 'insider', label: 'Insider Result BI Analytics', icon: Lightbulb },
];

const SignupPage = ({ onNavigateToLogin, onNavigateToLanding }) => {
  const [step, setStep] = useState(1); // 1=signup, 2=demo, 3=requirements, 4=done
  const [loading, setLoading] = useState(false);
  const [prospectId, setProspectId] = useState('');
  const [email, setEmail] = useState('');
  const [demoToken, setDemoToken] = useState('');
  const [demoData, setDemoData] = useState(null);
  const [selectedFeatures, setSelectedFeatures] = useState([]);
  const [notes, setNotes] = useState('');

  const [form, setForm] = useState({
    company_name: '',
    contact_person: '',
    email: '',
    phone: '',
    gst_number: '',
    address: '',
    selected_plan: '',
    message: '',
  });

  const updateForm = (field, value) => setForm(prev => ({ ...prev, [field]: value }));

  // Step 1: Submit signup
  const handleSignup = async (e) => {
    e.preventDefault();
    if (!form.company_name || !form.contact_person || !form.email || !form.phone) {
      toast.error('Please fill all required fields');
      return;
    }
    setLoading(true);
    try {
      // Get reCAPTCHA v3 token
      let captchaToken = '';
      if (window.grecaptcha?.execute) {
        try {
          captchaToken = await window.grecaptcha.execute(process.env.REACT_APP_RECAPTCHA_SITE_KEY, { action: 'signup' });
        } catch { /* fail open */ }
      }
      const res = await axios.post(`${API}/public/signup`, { ...form, captcha_token: captchaToken });
      if (res.data?.success) {
        toast.success(res.data.message);
        setProspectId(res.data.data.prospect_id);
        setEmail(res.data.data.email);
        setStep(2);
      } else {
        toast.error(res.data?.error || 'Signup failed');
      }
    } catch (err) {
      toast.error(err.response?.data?.error || 'Something went wrong');
    } finally {
      setLoading(false);
    }
  };

  // Step 2: Request demo
  const handleDemoRequest = async () => {
    setLoading(true);
    try {
      const res = await axios.post(`${API}/public/demo-request`, { prospect_id: prospectId, email });
      if (res.data?.success) {
        setDemoToken(res.data.data.demo_token);
        // Fetch demo data
        const demoRes = await axios.get(`${API}/public/demo-data?demo_token=${res.data.data.demo_token}`);
        if (demoRes.data?.success) {
          setDemoData(demoRes.data.data);
        }
        toast.success('Demo data loaded!');
      } else {
        toast.error(res.data?.error);
      }
    } catch (err) {
      toast.error('Could not load demo');
    } finally {
      setLoading(false);
    }
  };

  // Step 3: Submit requirements
  const handleSubmitRequirements = async () => {
    setLoading(true);
    try {
      const res = await axios.post(`${API}/public/submit-requirements`, {
        prospect_id: prospectId,
        email,
        requirements: selectedFeatures,
        notes
      });
      if (res.data?.success) {
        toast.success(res.data.message);
        setStep(4);
      }
    } catch (err) {
      toast.error('Submission failed');
    } finally {
      setLoading(false);
    }
  };

  const toggleFeature = (id) => {
    setSelectedFeatures(prev => prev.includes(id) ? prev.filter(f => f !== id) : [...prev, id]);
  };

  return (
    <div className="min-h-screen bg-zinc-50" style={{ fontFamily: 'Outfit, sans-serif' }}>
      {/* Header */}
      <header className="bg-white border-b border-zinc-100">
        <div className="max-w-5xl mx-auto px-6 h-16 flex items-center justify-between">
          <button onClick={onNavigateToLanding} className="flex items-center gap-2 text-zinc-500 hover:text-zinc-950 transition-colors">
            <ArrowLeft size={18} />
            <img src="/flowra-logo.png" alt="FLOWRA" className="h-7 object-contain" />
            <span className="font-bold text-zinc-950">FLOWRA</span>
          </button>
          <button onClick={onNavigateToLogin} className="text-sm font-medium text-zinc-600 hover:text-zinc-950">
            Already have an account? <span className="font-bold text-[#0052FF]">Login</span>
          </button>
        </div>
      </header>

      {/* Progress Steps */}
      <div className="max-w-3xl mx-auto px-6 pt-8">
        <div className="flex items-center justify-center gap-2 mb-8">
          {[
            { n: 1, label: 'Your Details' },
            { n: 2, label: 'Explore Demo' },
            { n: 3, label: 'Requirements' },
            { n: 4, label: 'Complete' }
          ].map(({ n, label }, i) => (
            <React.Fragment key={n}>
              {i > 0 && <div className={`w-12 h-0.5 ${step >= n ? 'bg-[#0052FF]' : 'bg-zinc-200'}`} />}
              <div className="flex flex-col items-center">
                <div className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold ${step >= n ? 'bg-[#0052FF] text-white' : 'bg-zinc-200 text-zinc-500'}`}>
                  {step > n ? <Check size={14} /> : n}
                </div>
                <span className="text-[10px] mt-1 text-zinc-500">{label}</span>
              </div>
            </React.Fragment>
          ))}
        </div>
      </div>

      {/* Step 1: Signup Form */}
      {step === 1 && (
        <div className="max-w-2xl mx-auto px-6 pb-16">
          <div className="bg-white border border-zinc-200 rounded-sm p-8" data-testid="signup-form">
            <h2 className="text-2xl font-bold text-zinc-950 mb-1" style={{ fontFamily: 'Cabinet Grotesk, Outfit, sans-serif' }}>
              Tell us about your business
            </h2>
            <p className="text-zinc-500 text-sm mb-8">We'll customize FLOWRA for your needs. All data is encrypted and secure.</p>

            <form onSubmit={handleSignup} className="space-y-5">
              <div className="grid md:grid-cols-2 gap-5">
                <div>
                  <label className="block text-sm font-medium text-zinc-700 mb-1.5">Company Name *</label>
                  <div className="relative">
                    <Building2 size={16} className="absolute left-3 top-3 text-zinc-400" />
                    <input type="text" value={form.company_name} onChange={e => updateForm('company_name', e.target.value)}
                      className="w-full pl-10 pr-4 py-2.5 border border-zinc-200 rounded-sm text-sm focus:outline-none focus:ring-2 focus:ring-[#0052FF] focus:border-transparent" placeholder="Acme Trading Co." data-testid="signup-company" required />
                  </div>
                </div>
                <div>
                  <label className="block text-sm font-medium text-zinc-700 mb-1.5">Contact Person *</label>
                  <div className="relative">
                    <User size={16} className="absolute left-3 top-3 text-zinc-400" />
                    <input type="text" value={form.contact_person} onChange={e => updateForm('contact_person', e.target.value)}
                      className="w-full pl-10 pr-4 py-2.5 border border-zinc-200 rounded-sm text-sm focus:outline-none focus:ring-2 focus:ring-[#0052FF] focus:border-transparent" placeholder="Rajesh Agarwal" data-testid="signup-contact" required />
                  </div>
                </div>
              </div>

              <div className="grid md:grid-cols-2 gap-5">
                <div>
                  <label className="block text-sm font-medium text-zinc-700 mb-1.5">Email *</label>
                  <div className="relative">
                    <Mail size={16} className="absolute left-3 top-3 text-zinc-400" />
                    <input type="email" value={form.email} onChange={e => updateForm('email', e.target.value)}
                      className="w-full pl-10 pr-4 py-2.5 border border-zinc-200 rounded-sm text-sm focus:outline-none focus:ring-2 focus:ring-[#0052FF] focus:border-transparent" placeholder="rajesh@company.com" data-testid="signup-email" required />
                  </div>
                </div>
                <div>
                  <label className="block text-sm font-medium text-zinc-700 mb-1.5">Phone *</label>
                  <div className="relative">
                    <Phone size={16} className="absolute left-3 top-3 text-zinc-400" />
                    <input type="tel" value={form.phone} onChange={e => updateForm('phone', e.target.value)}
                      className="w-full pl-10 pr-4 py-2.5 border border-zinc-200 rounded-sm text-sm focus:outline-none focus:ring-2 focus:ring-[#0052FF] focus:border-transparent" placeholder="+91-9876543210" data-testid="signup-phone" required />
                  </div>
                </div>
              </div>

              <div className="grid md:grid-cols-2 gap-5">
                <div>
                  <label className="block text-sm font-medium text-zinc-700 mb-1.5">GST Number</label>
                  <div className="relative">
                    <FileText size={16} className="absolute left-3 top-3 text-zinc-400" />
                    <input type="text" value={form.gst_number} onChange={e => updateForm('gst_number', e.target.value)}
                      className="w-full pl-10 pr-4 py-2.5 border border-zinc-200 rounded-sm text-sm focus:outline-none focus:ring-2 focus:ring-[#0052FF] focus:border-transparent" placeholder="22AAAAA0000A1Z5" data-testid="signup-gst" />
                  </div>
                </div>
                <div>
                  <label className="block text-sm font-medium text-zinc-700 mb-1.5">Preferred Plan</label>
                  <select value={form.selected_plan} onChange={e => updateForm('selected_plan', e.target.value)}
                    className="w-full px-4 py-2.5 border border-zinc-200 rounded-sm text-sm focus:outline-none focus:ring-2 focus:ring-[#0052FF]" data-testid="signup-plan">
                    <option value="">Select a plan</option>
                    <option value="starter">Starter - ₹999/mo</option>
                    <option value="professional">Professional - ₹2,499/mo</option>
                    <option value="enterprise">Enterprise - Rs.3,799/mo</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-zinc-700 mb-1.5">Address</label>
                <div className="relative">
                  <MapPin size={16} className="absolute left-3 top-3 text-zinc-400" />
                  <input type="text" value={form.address} onChange={e => updateForm('address', e.target.value)}
                    className="w-full pl-10 pr-4 py-2.5 border border-zinc-200 rounded-sm text-sm focus:outline-none focus:ring-2 focus:ring-[#0052FF] focus:border-transparent" placeholder="Your business address" data-testid="signup-address" />
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-zinc-700 mb-1.5">Message (optional)</label>
                <textarea value={form.message} onChange={e => updateForm('message', e.target.value)} rows={3}
                  className="w-full px-4 py-2.5 border border-zinc-200 rounded-sm text-sm focus:outline-none focus:ring-2 focus:ring-[#0052FF] focus:border-transparent resize-none" placeholder="Tell us about your business needs..." data-testid="signup-message" />
              </div>

              <div className="flex items-start gap-2 p-3 bg-zinc-50 rounded-sm">
                <Shield size={16} className="text-green-600 mt-0.5 flex-shrink-0" />
                <p className="text-xs text-zinc-500">Your data is encrypted with AES-256 and stored securely. We never share your information with third parties.</p>
              </div>

              <button type="submit" disabled={loading} data-testid="signup-submit-btn"
                className="w-full bg-[#0052FF] text-white py-3 font-bold rounded-sm hover:bg-[#0039B3] transition-colors flex items-center justify-center gap-2 disabled:opacity-50">
                {loading ? <><Loader className="animate-spin" size={18} /> Submitting...</> : <>Submit Enquiry <ArrowRight size={18} /></>}
              </button>
            </form>
          </div>
        </div>
      )}

      {/* Step 2: Demo Experience */}
      {step === 2 && (
        <div className="max-w-4xl mx-auto px-6 pb-16">
          <div className="bg-white border border-zinc-200 rounded-sm p-8" data-testid="demo-section">
            <h2 className="text-2xl font-bold text-zinc-950 mb-2" style={{ fontFamily: 'Cabinet Grotesk, Outfit, sans-serif' }}>
              Explore FLOWRA with Demo Data
            </h2>
            <p className="text-zinc-500 text-sm mb-6">See how FLOWRA works with a sample trading company. This uses demo data only — no real customer data.</p>

            {!demoData ? (
              <div className="text-center py-12">
                <div className="w-16 h-16 bg-[#0052FF]/10 rounded-full flex items-center justify-center mx-auto mb-4">
                  <Play size={24} className="text-[#0052FF]" />
                </div>
                <p className="text-zinc-700 font-medium mb-2">Would you like to explore FLOWRA?</p>
                <p className="text-zinc-500 text-sm mb-6">See a preview of the dashboard and try with sample data.</p>

                {/* Animated Dashboard Mockup */}
                <div className="mb-8 max-w-2xl mx-auto bg-slate-50 border border-zinc-200 rounded-sm overflow-hidden" data-testid="demo-mockup">
                  {/* Mock Navbar */}
                  <div className="bg-white border-b border-zinc-200 px-4 py-2 flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <div className="w-5 h-5 bg-[#0052FF] rounded-sm" />
                      <span className="text-xs font-bold text-zinc-900">FLOWRA</span>
                    </div>
                    <div className="flex items-center gap-3">
                      {['Dashboard', 'Sales', 'CRM', 'Inventory', 'Analytics'].map((n, i) => (
                        <span key={n} className={`text-[10px] font-medium px-2 py-1 rounded ${i === 0 ? 'bg-[#0052FF] text-white' : 'text-zinc-500'}`}>{n}</span>
                      ))}
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-[10px] text-zinc-500 border border-zinc-200 rounded px-1.5 py-0.5">FY 2025-26</span>
                      <div className="w-5 h-5 bg-[#0052FF] rounded-full" />
                    </div>
                  </div>
                  {/* Mock Dashboard Body */}
                  <div className="p-4">
                    <div className="flex items-center justify-between mb-3">
                      <div>
                        <p className="text-sm font-bold text-zinc-900">Dashboard</p>
                        <p className="text-[10px] text-zinc-500">Last sync: 10/04/2026, 14:30 IST</p>
                      </div>
                    </div>
                    <div className="grid grid-cols-4 gap-2 mb-3">
                      {[
                        { label: 'Total Sales', value: 'Rs.52.3L', color: 'text-blue-600' },
                        { label: 'Inventory Items', value: '156', color: 'text-purple-600' },
                        { label: 'Low Stock', value: '23', color: 'text-red-600' },
                        { label: 'FY Sales', value: 'Rs.52.3L', color: 'text-cyan-600' }
                      ].map(s => (
                        <div key={s.label} className="bg-white border border-zinc-200 rounded p-2.5 animate-fade-in">
                          <p className="text-[9px] text-zinc-500">{s.label}</p>
                          <p className={`text-sm font-bold ${s.color}`}>{s.value}</p>
                        </div>
                      ))}
                    </div>
                    <div className="grid grid-cols-2 gap-2">
                      <div className="bg-white border border-zinc-200 rounded p-2.5">
                        <p className="text-[9px] font-medium text-zinc-600 mb-1.5">Recent Transactions</p>
                        {['ABC Motors - Rs.1.2L', 'Shree Krishna - Rs.98K', 'Mahalaxmi Ent - Rs.75K'].map(t => (
                          <div key={t} className="flex justify-between text-[9px] py-1 border-b border-zinc-50 last:border-0">
                            <span className="text-zinc-700">{t.split(' - ')[0]}</span>
                            <span className="text-[#0052FF] font-medium">{t.split(' - ')[1]}</span>
                          </div>
                        ))}
                      </div>
                      <div className="bg-white border border-zinc-200 rounded p-2.5">
                        <p className="text-[9px] font-medium text-zinc-600 mb-1.5">Top Customers</p>
                        {['ABC Motors - Rs.12.5L', 'Shree Krishna - Rs.9.8L', 'National Auto - Rs.6.2L'].map((t, i) => (
                          <div key={t} className="flex items-center justify-between text-[9px] py-1 border-b border-zinc-50 last:border-0">
                            <div className="flex items-center gap-1">
                              <span className="w-3.5 h-3.5 rounded-full bg-blue-50 text-blue-600 flex items-center justify-center text-[7px] font-bold">{i + 1}</span>
                              <span className="text-zinc-700">{t.split(' - ')[0]}</span>
                            </div>
                            <span className="text-[#0052FF] font-medium">{t.split(' - ')[1]}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>
                <p className="text-xs text-zinc-400 mb-6">Interactive preview of the FLOWRA admin dashboard</p>

                <div className="flex justify-center gap-4">
                  <button onClick={handleDemoRequest} disabled={loading} data-testid="demo-start-btn"
                    className="bg-[#0052FF] text-white px-8 py-3 font-bold rounded-sm hover:bg-[#0039B3] transition-colors flex items-center gap-2 disabled:opacity-50">
                    {loading ? <Loader className="animate-spin" size={18} /> : <Eye size={18} />} Try with Sample Data
                  </button>
                  <button onClick={() => setStep(3)} className="border border-zinc-300 text-zinc-700 px-8 py-3 font-bold rounded-sm hover:bg-zinc-50 transition-colors">
                    Skip to Requirements
                  </button>
                </div>
              </div>
            ) : (
              <div>
                <div className="bg-[#0052FF]/5 border border-[#0052FF]/20 rounded-sm p-3 mb-6 text-xs text-[#0052FF] font-medium">
                  Demo Company: {demoData.company_name} | FY: {demoData.fy} — Showing Professional Plan features
                </div>

                {/* Professional Plan Features */}
                <div className="mb-6 bg-gradient-to-r from-blue-50 to-indigo-50 border border-blue-100 rounded-sm p-4">
                  <h3 className="text-sm font-bold text-blue-900 mb-2">Professional Plan Features Included</h3>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                    {['Dashboard', 'Sales Tracking', 'Customer CRM', 'Inventory Mgmt', 'Movement Analytics', 'Sync History', 'Excel/PDF Exports', 'Multi-Company (3)'].map(f => (
                      <div key={f} className="flex items-center gap-1.5 text-xs text-blue-800">
                        <Check size={12} className="text-blue-600" /> {f}
                      </div>
                    ))}
                  </div>
                  <p className="text-[10px] text-blue-600 mt-2">Upgrade to Enterprise for Salesman Tracking, AI Reports, Insider BI Analytics, and up to 10 companies</p>
                </div>

                {/* Demo Dashboard */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                  <div className="border border-zinc-200 rounded-sm p-4">
                    <p className="text-xs text-zinc-500">Total Sales</p>
                    <p className="text-lg font-bold text-zinc-950">Rs.{(demoData.dashboard.total_sales / 100000).toFixed(1)}L</p>
                  </div>
                  <div className="border border-zinc-200 rounded-sm p-4">
                    <p className="text-xs text-zinc-500">Inventory Items</p>
                    <p className="text-lg font-bold text-zinc-950">{demoData.dashboard.inventory_items}</p>
                  </div>
                  <div className="border border-zinc-200 rounded-sm p-4">
                    <p className="text-xs text-zinc-500">Low Stock</p>
                    <p className="text-lg font-bold text-amber-600">{demoData.dashboard.low_stock_items}</p>
                  </div>
                  <div className="border border-zinc-200 rounded-sm p-4">
                    <p className="text-xs text-zinc-500">Overdue</p>
                    <p className="text-lg font-bold text-red-600">Rs.{(demoData.dashboard.overdue_payments / 100000).toFixed(1)}L</p>
                  </div>
                </div>

                {/* Demo Inventory Table */}
                <h3 className="text-sm font-bold text-zinc-950 mb-3">Sample Inventory</h3>
                <div className="overflow-x-auto mb-6">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="bg-zinc-50 border-b border-zinc-200">
                        <th className="text-left py-2 px-3 font-medium text-zinc-600">Item</th>
                        <th className="text-right py-2 px-3 font-medium text-zinc-600">Qty</th>
                        <th className="text-right py-2 px-3 font-medium text-zinc-600">Value</th>
                        <th className="text-left py-2 px-3 font-medium text-zinc-600">Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {demoData.inventory_sample.map((item, i) => (
                        <tr key={i} className="border-b border-zinc-100">
                          <td className="py-2 px-3 text-zinc-800">{item.item}</td>
                          <td className="py-2 px-3 text-right text-zinc-700">{item.qty}</td>
                          <td className="py-2 px-3 text-right text-zinc-700">Rs.{item.value.toLocaleString('en-IN')}</td>
                          <td className="py-2 px-3">
                            <span className={`text-xs px-2 py-0.5 rounded-sm font-medium ${item.status === 'In Stock' ? 'bg-green-50 text-green-700' : item.status === 'Low Stock' ? 'bg-amber-50 text-amber-700' : 'bg-red-50 text-red-700'}`}>
                              {item.status}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                {/* Demo CRM Table */}
                <h3 className="text-sm font-bold text-zinc-950 mb-3">Sample Customer Outstanding</h3>
                <div className="overflow-x-auto mb-8">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="bg-zinc-50 border-b border-zinc-200">
                        <th className="text-left py-2 px-3 font-medium text-zinc-600">Customer</th>
                        <th className="text-right py-2 px-3 font-medium text-zinc-600">Outstanding</th>
                        <th className="text-left py-2 px-3 font-medium text-zinc-600">Last Payment</th>
                        <th className="text-left py-2 px-3 font-medium text-zinc-600">Aging</th>
                      </tr>
                    </thead>
                    <tbody>
                      {demoData.crm_sample.map((c, i) => (
                        <tr key={i} className="border-b border-zinc-100">
                          <td className="py-2 px-3 text-zinc-800">{c.customer}</td>
                          <td className="py-2 px-3 text-right text-red-600 font-medium">Rs.{c.outstanding.toLocaleString('en-IN')}</td>
                          <td className="py-2 px-3 text-zinc-600">{c.last_payment}</td>
                          <td className="py-2 px-3 text-zinc-600">{c.aging}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                <div className="flex justify-end">
                  <button onClick={() => setStep(3)} data-testid="demo-continue-btn"
                    className="bg-[#0052FF] text-white px-8 py-3 font-bold rounded-sm hover:bg-[#0039B3] transition-colors flex items-center gap-2">
                    Continue to Requirements <ArrowRight size={18} />
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Step 3: Feature Requirements */}
      {step === 3 && (
        <div className="max-w-2xl mx-auto px-6 pb-16">
          <div className="bg-white border border-zinc-200 rounded-sm p-8" data-testid="requirements-section">
            <h2 className="text-2xl font-bold text-zinc-950 mb-2" style={{ fontFamily: 'Cabinet Grotesk, Outfit, sans-serif' }}>
              Select your required features
            </h2>
            <p className="text-zinc-500 text-sm mb-6">Help us understand your needs. This is optional — you can always change later.</p>

            <div className="grid grid-cols-2 gap-3 mb-6">
              {AVAILABLE_FEATURES.map(f => (
                <button key={f.id} onClick={() => toggleFeature(f.id)}
                  className={`flex items-center gap-3 p-4 border rounded-sm text-left transition-all ${selectedFeatures.includes(f.id) ? 'border-[#0052FF] bg-[#0052FF]/5' : 'border-zinc-200 hover:border-zinc-300'}`}
                  data-testid={`req-feature-${f.id}`}>
                  <div className={`w-5 h-5 rounded-sm border flex items-center justify-center flex-shrink-0 ${selectedFeatures.includes(f.id) ? 'bg-[#0052FF] border-[#0052FF]' : 'border-zinc-300'}`}>
                    {selectedFeatures.includes(f.id) && <Check size={12} className="text-white" />}
                  </div>
                  <span className="text-sm font-medium text-zinc-800">{f.label}</span>
                </button>
              ))}
            </div>

            <div className="mb-6">
              <label className="block text-sm font-medium text-zinc-700 mb-1.5">Additional notes</label>
              <textarea value={notes} onChange={e => setNotes(e.target.value)} rows={3}
                className="w-full px-4 py-2.5 border border-zinc-200 rounded-sm text-sm focus:outline-none focus:ring-2 focus:ring-[#0052FF] focus:border-transparent resize-none"
                placeholder="Any specific requirements or integrations you need..." data-testid="req-notes" />
            </div>

            <div className="flex gap-3">
              <button onClick={handleSubmitRequirements} disabled={loading} data-testid="req-submit-btn"
                className="flex-1 bg-[#0052FF] text-white py-3 font-bold rounded-sm hover:bg-[#0039B3] transition-colors flex items-center justify-center gap-2 disabled:opacity-50">
                {loading ? <Loader className="animate-spin" size={18} /> : null} Submit Requirements
              </button>
              <button onClick={() => setStep(4)} className="px-6 py-3 border border-zinc-300 text-zinc-600 font-bold rounded-sm hover:bg-zinc-50 transition-colors">
                Skip
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Step 4: Complete */}
      {step === 4 && (
        <div className="max-w-xl mx-auto px-6 pb-16">
          <div className="bg-white border border-zinc-200 rounded-sm p-12 text-center" data-testid="signup-complete">
            <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-6">
              <Check size={28} className="text-green-600" />
            </div>
            <h2 className="text-2xl font-bold text-zinc-950 mb-3" style={{ fontFamily: 'Cabinet Grotesk, Outfit, sans-serif' }}>
              You're all set!
            </h2>
            <p className="text-zinc-600 mb-2">Your enquiry <span className="font-bold text-zinc-950">{prospectId}</span> has been submitted.</p>
            <p className="text-zinc-500 text-sm mb-8">Our team will review your requirements and contact you at <span className="font-medium">{email}</span> within 24 hours to set up your account.</p>

            <div className="flex flex-col gap-3">
              <button onClick={onNavigateToLanding} className="w-full bg-zinc-950 text-white py-3 font-bold rounded-sm hover:bg-zinc-800 transition-colors">
                Back to Home
              </button>
              <button onClick={onNavigateToLogin} className="w-full border border-zinc-300 text-zinc-700 py-3 font-bold rounded-sm hover:bg-zinc-50 transition-colors">
                Already have account? Login
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default SignupPage;
