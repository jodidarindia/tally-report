import React, { useEffect, useState, useCallback } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { X, Sparkles, Check, Loader2 } from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const loadRazorpay = () => new Promise((resolve) => {
  if (window.Razorpay) return resolve(true);
  const s = document.createElement('script');
  s.src = 'https://checkout.razorpay.com/v1/checkout.js';
  s.onload = () => resolve(true);
  s.onerror = () => resolve(false);
  document.body.appendChild(s);
});

/**
 * UpgradeModal — self-serve conversion for trial users, renewal for
 * paid users, and mid-cycle plan changes. Uses the Razorpay Checkout
 * widget and posts the signed response to /api/billing/verify.
 */
export const UpgradeModal = ({ open, onClose, user, token, initialIntent = 'upgrade' }) => {
  const [cfg, setCfg] = useState(null);
  const [plan, setPlan] = useState(user?.is_trial ? 'enterprise' : (user?.plan || 'starter'));
  const [cycle, setCycle] = useState('annual');
  const [months, setMonths] = useState(12);
  const [intent] = useState(initialIntent);
  const [processing, setProcessing] = useState(false);

  const headers = { Authorization: `Bearer ${token}` };

  useEffect(() => {
    if (!open) return;
    axios.get(`${API}/billing/config`, { headers })
      .then((r) => setCfg(r.data?.data || null))
      .catch(() => setCfg({ configured: false }));
    loadRazorpay();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const priceFor = useCallback((p, c) => {
    const plans = cfg?.plans || {};
    const pricing = plans[p];
    if (!pricing) return 0;
    return c === 'annual' ? pricing.annual : pricing.monthly;
  }, [cfg]);

  const startCheckout = async () => {
    if (!cfg?.configured) {
      toast.error('Razorpay is not configured yet. Please contact support.');
      return;
    }
    const scriptOk = await loadRazorpay();
    if (!scriptOk) return toast.error('Failed to load Razorpay. Check your internet connection.');
    setProcessing(true);
    try {
      const r = await axios.post(`${API}/billing/create-order`,
        { intent, plan, cycle, months }, { headers });
      if (!r.data?.success) throw new Error(r.data?.error || 'Order creation failed');
      const { order_id, amount, key_id, prefill } = r.data.data;

      const options = {
        key: key_id,
        amount, currency: 'INR', order_id,
        name: 'FLOWRA', description: `${plan.toUpperCase()} · ${cycle} · ${months}m`,
        image: '/apple-touch-icon.png',
        prefill: { name: prefill?.name || '', email: prefill?.email || '', contact: prefill?.contact || '' },
        theme: { color: '#2563EB' },
        handler: async (res) => {
          try {
            const verify = await axios.post(`${API}/billing/verify`, {
              razorpay_payment_id: res.razorpay_payment_id,
              razorpay_order_id:   res.razorpay_order_id,
              razorpay_signature:  res.razorpay_signature,
            }, { headers });
            if (verify.data?.success) {
              toast.success('Payment successful — your plan is upgraded!');
              onClose?.(true);
              // Force a fresh reload so /auth/me reflects the new plan + features.
              setTimeout(() => window.location.reload(), 1200);
            } else {
              toast.error(verify.data?.error || 'Verification failed. Contact support.');
            }
          } catch (err) {
            toast.error(err.response?.data?.error || 'Verification failed.');
          }
        },
        modal: { ondismiss: () => setProcessing(false) },
      };
      new window.Razorpay(options).open();
    } catch (err) {
      toast.error(err.response?.data?.error || err.message || 'Payment failed to start');
    } finally {
      setProcessing(false);
    }
  };

  if (!open) return null;
  const price = priceFor(plan, cycle);
  const total = cycle === 'annual' ? price * (months / 12) : price * months;

  const plansToShow = Object.entries(cfg?.plans || {});

  return (
    <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-sm flex items-center justify-center p-4" onClick={(e) => e.target === e.currentTarget && onClose?.()} data-testid="upgrade-modal">
      <div className="bg-white rounded-2xl w-full max-w-2xl shadow-2xl border border-slate-200">
        <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Sparkles size={18} className="text-blue-600" />
            <h2 className="text-lg font-semibold text-slate-900">
              {user?.is_trial ? 'Convert your trial' : (intent === 'renew' ? 'Renew subscription' : 'Change plan')}
            </h2>
          </div>
          <button onClick={() => onClose?.()} className="p-1 rounded hover:bg-slate-100" data-testid="upgrade-close">
            <X size={18} className="text-slate-500" />
          </button>
        </div>

        {!cfg && (
          <div className="p-10 text-center text-slate-500 text-sm">
            <Loader2 className="animate-spin inline mr-2" size={16} /> Loading plans…
          </div>
        )}

        {cfg && !cfg.configured && (
          <div className="p-6 text-sm">
            <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 text-amber-800">
              Razorpay is not yet configured for this environment. Please contact your administrator or wait until the payment gateway is enabled.
            </div>
          </div>
        )}

        {cfg?.configured && (
          <div className="p-6 space-y-5">
            <div>
              <div className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-2">Pick a plan</div>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                {plansToShow.map(([id, p]) => (
                  <button key={id}
                    onClick={() => setPlan(id)}
                    className={`text-left p-4 border rounded-xl transition-all ${plan === id ? 'border-blue-500 bg-blue-50 ring-1 ring-blue-500' : 'border-slate-200 hover:border-blue-300'}`}
                    data-testid={`upgrade-plan-${id}`}>
                    <div className="text-sm font-bold text-slate-900">{p.name}</div>
                    <div className="text-xs text-slate-500 mt-0.5">
                      ₹{(cycle === 'annual' ? p.annual : p.monthly).toLocaleString('en-IN')} / {cycle}
                    </div>
                    {plan === id && <Check size={14} className="text-blue-600 mt-1" />}
                  </button>
                ))}
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <div className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-2">Billing cycle</div>
                <div className="flex gap-2">
                  {['monthly', 'annual'].map((c) => (
                    <button key={c} onClick={() => setCycle(c)}
                      className={`flex-1 py-2 text-sm font-medium rounded-lg border ${cycle === c ? 'border-blue-500 bg-blue-50 text-blue-700' : 'border-slate-200'}`}
                      data-testid={`upgrade-cycle-${c}`}>
                      {c === 'annual' ? 'Annual (Save 17%)' : 'Monthly'}
                    </button>
                  ))}
                </div>
              </div>
              <div>
                <div className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-2">Duration</div>
                <select value={months} onChange={(e) => setMonths(parseInt(e.target.value))}
                  className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm">
                  {[1, 3, 6, 12, 24, 36].map(m => <option key={m} value={m}>{m} month(s)</option>)}
                </select>
              </div>
            </div>

            <div className="bg-slate-50 border border-slate-200 rounded-xl p-4">
              <div className="flex justify-between text-sm mb-1">
                <span className="text-slate-500">Base price</span>
                <span className="font-medium">₹{price.toLocaleString('en-IN')} / {cycle}</span>
              </div>
              <div className="flex justify-between text-sm mb-1">
                <span className="text-slate-500">Duration multiplier</span>
                <span className="font-medium">× {cycle === 'annual' ? (months / 12).toFixed(2) : months}</span>
              </div>
              <div className="flex justify-between text-base font-bold text-slate-900 border-t border-slate-200 pt-2 mt-2">
                <span>Total to pay</span>
                <span>₹{total.toLocaleString('en-IN')}</span>
              </div>
              <p className="text-[11px] text-slate-400 mt-2">
                Secure payment via Razorpay · UPI, Card, Netbanking, Wallets accepted.
              </p>
            </div>

            <button onClick={startCheckout} disabled={processing}
              className="w-full py-3 bg-blue-600 text-white rounded-lg font-semibold hover:bg-blue-700 disabled:opacity-50 flex items-center justify-center gap-2"
              data-testid="upgrade-pay-btn">
              {processing ? <><Loader2 className="animate-spin" size={16} /> Opening Razorpay…</> : `Pay ₹${total.toLocaleString('en-IN')} securely`}
            </button>
          </div>
        )}
      </div>
    </div>
  );
};

export default UpgradeModal;
