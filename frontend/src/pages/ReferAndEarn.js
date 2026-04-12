import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { Gift, Copy, Users, IndianRupee, Clock, CheckCircle, ArrowDownCircle, ArrowUpCircle, Share2 } from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

const fmtRs = (v) => `Rs.${(v || 0).toLocaleString('en-IN', { maximumFractionDigits: 2 })}`;
const fmtDate = (d) => {
  if (!d) return '-';
  const dt = (d.includes('+') || d.includes('Z')) ? new Date(d) : new Date(d + 'Z');
  return dt.toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'Asia/Kolkata' });
};

const ReferAndEarn = () => {
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState(null);
  const [activeTab, setActiveTab] = useState('overview');

  useEffect(() => { fetchDashboard(); }, []);

  const fetchDashboard = async () => {
    setLoading(true);
    try {
      // Ensure we have a code first
      await axios.get(`${API}/referrals/my-code`);
      const res = await axios.get(`${API}/referrals/my-dashboard`);
      if (res.data?.success) setData(res.data.data);
    } catch (err) {
      toast.error('Failed to load referral data');
    } finally {
      setLoading(false);
    }
  };

  const copyCode = () => {
    if (data?.referral_code) {
      navigator.clipboard.writeText(data.referral_code);
      toast.success('Referral code copied!');
    }
  };

  const shareLink = () => {
    const text = `Join FLOWRA — India's smartest Tally* analytics platform! Use my referral code: ${data?.referral_code}\n\nSign up: https://www.flowralive.in`;
    if (navigator.share) {
      navigator.share({ title: 'FLOWRA Referral', text });
    } else {
      navigator.clipboard.writeText(text);
      toast.success('Referral message copied!');
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64" data-testid="referral-loading">
        <div className="loading-spinner" /><span className="ml-3 text-slate-600">Loading...</span>
      </div>
    );
  }

  const stats = data?.stats || {};
  const referrals = data?.referrals || [];
  const ledger = data?.ledger || [];

  return (
    <div data-testid="refer-earn-page">
      <div className="mb-6">
        <h1 className="text-2xl sm:text-4xl font-light tracking-tight text-slate-900" style={{ fontFamily: 'Outfit, sans-serif' }}>
          Refer & Earn
        </h1>
        <p className="mt-1 text-sm text-slate-600">Earn 3% commission on every successful referral subscription</p>
      </div>

      {/* Referral Code Card */}
      <div className="bg-gradient-to-r from-[#2563EB] to-[#1D4ED8] rounded-2xl p-6 sm:p-8 mb-6 text-white" data-testid="referral-code-card">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div>
            <p className="text-blue-200 text-sm mb-1">Your Referral Code</p>
            <div className="flex items-center gap-3">
              <span className="text-3xl sm:text-4xl font-bold tracking-wider font-mono" data-testid="referral-code">{data?.referral_code || '...'}</span>
              <button onClick={copyCode} className="p-2 bg-white/20 rounded-lg hover:bg-white/30 transition-colors" data-testid="copy-code-btn" title="Copy code">
                <Copy size={18} />
              </button>
            </div>
          </div>
          <button onClick={shareLink} className="flex items-center gap-2 px-5 py-3 bg-white text-[#2563EB] rounded-lg font-bold text-sm hover:bg-blue-50 transition-colors" data-testid="share-btn">
            <Share2 size={16} /> Share & Invite
          </button>
        </div>
        <div className="mt-4 p-3 bg-white/10 rounded-lg text-sm text-blue-100">
          Share this code with businesses. When they subscribe to FLOWRA, you earn <strong className="text-white">3% commission</strong> on their subscription amount.
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 sm:gap-4 mb-6">
        <div className="bg-white border border-slate-200 rounded-xl p-4" data-testid="stat-referrals">
          <div className="flex items-center gap-2 mb-2">
            <div className="w-8 h-8 bg-blue-100 rounded-lg flex items-center justify-center"><Users size={16} className="text-blue-600" /></div>
            <span className="text-xs text-slate-500">Total Referrals</span>
          </div>
          <div className="text-2xl font-bold text-slate-900">{stats.total_referrals || 0}</div>
        </div>
        <div className="bg-white border border-slate-200 rounded-xl p-4" data-testid="stat-earned">
          <div className="flex items-center gap-2 mb-2">
            <div className="w-8 h-8 bg-green-100 rounded-lg flex items-center justify-center"><IndianRupee size={16} className="text-green-600" /></div>
            <span className="text-xs text-slate-500">Total Earned</span>
          </div>
          <div className="text-2xl font-bold text-green-700">{fmtRs(stats.total_earned)}</div>
        </div>
        <div className="bg-white border border-slate-200 rounded-xl p-4" data-testid="stat-balance">
          <div className="flex items-center gap-2 mb-2">
            <div className="w-8 h-8 bg-amber-100 rounded-lg flex items-center justify-center"><IndianRupee size={16} className="text-amber-600" /></div>
            <span className="text-xs text-slate-500">Balance</span>
          </div>
          <div className="text-2xl font-bold text-amber-700">{fmtRs(stats.current_balance)}</div>
        </div>
        <div className="bg-white border border-slate-200 rounded-xl p-4" data-testid="stat-redeemed">
          <div className="flex items-center gap-2 mb-2">
            <div className="w-8 h-8 bg-purple-100 rounded-lg flex items-center justify-center"><CheckCircle size={16} className="text-purple-600" /></div>
            <span className="text-xs text-slate-500">Redeemed</span>
          </div>
          <div className="text-2xl font-bold text-purple-700">{fmtRs(stats.total_redeemed)}</div>
        </div>
      </div>

      {/* Tabs */}
      <div className="bg-white border border-slate-200 rounded-xl p-1.5 mb-6 flex gap-1.5">
        {[
          { id: 'overview', label: 'Referrals', icon: Users },
          { id: 'ledger', label: 'Earnings Ledger', icon: IndianRupee },
        ].map(tab => {
          const Icon = tab.icon;
          return (
            <button key={tab.id} onClick={() => setActiveTab(tab.id)}
              data-testid={`tab-${tab.id}`}
              className={`flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg transition-all text-sm font-medium ${
                activeTab === tab.id ? 'bg-[#2563EB] text-white' : 'text-slate-600 hover:bg-slate-50'
              }`}
            >
              <Icon size={16} /> {tab.label}
            </button>
          );
        })}
      </div>

      {/* Referrals Table */}
      {activeTab === 'overview' && (
        <div className="bg-white border border-slate-200 rounded-xl overflow-x-auto" data-testid="referrals-table-container">
          <table className="data-table min-w-[600px]" data-testid="referrals-table">
            <thead>
              <tr>
                <th>Referred Company</th>
                <th>Signup Date</th>
                <th>Status</th>
                <th className="numeric">Subscription</th>
                <th className="numeric">Commission (3%)</th>
              </tr>
            </thead>
            <tbody>
              {referrals.length > 0 ? referrals.map((r, idx) => (
                <tr key={idx} data-testid={`referral-row-${idx}`}>
                  <td className="font-medium text-slate-900">{r.referred_company}</td>
                  <td className="text-slate-600">{fmtDate(r.signup_date)}</td>
                  <td>
                    <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                      r.status === 'subscribed' ? 'bg-green-100 text-green-700' :
                      r.status === 'expired' ? 'bg-red-100 text-red-700' :
                      'bg-amber-100 text-amber-700'
                    }`}>
                      {r.status === 'subscribed' ? 'Subscribed' : r.status === 'expired' ? 'Expired' : 'Pending'}
                    </span>
                  </td>
                  <td className="numeric">{r.subscription_amount > 0 ? fmtRs(r.subscription_amount) : '-'}</td>
                  <td className="numeric font-medium text-green-700">{r.commission_amount > 0 ? fmtRs(r.commission_amount) : '-'}</td>
                </tr>
              )) : (
                <tr>
                  <td colSpan="5" className="text-center py-12 text-slate-400">
                    <Gift size={40} className="mx-auto mb-3 text-slate-300" />
                    <p className="font-medium">No referrals yet</p>
                    <p className="text-sm mt-1">Share your code and start earning!</p>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* Earnings Ledger */}
      {activeTab === 'ledger' && (
        <div className="bg-white border border-slate-200 rounded-xl overflow-x-auto" data-testid="ledger-table-container">
          <table className="data-table min-w-[600px]" data-testid="ledger-table">
            <thead>
              <tr>
                <th>Date</th>
                <th>Type</th>
                <th>Description</th>
                <th className="numeric">Amount</th>
                <th className="numeric">Balance</th>
              </tr>
            </thead>
            <tbody>
              {ledger.length > 0 ? ledger.map((e, idx) => (
                <tr key={idx} data-testid={`ledger-row-${idx}`}>
                  <td className="text-slate-600">{fmtDate(e.created_at)}</td>
                  <td>
                    <span className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium ${
                      e.type === 'credit' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
                    }`}>
                      {e.type === 'credit' ? <ArrowDownCircle size={12} /> : <ArrowUpCircle size={12} />}
                      {e.type === 'credit' ? 'Credit' : 'Debit'}
                    </span>
                  </td>
                  <td className="text-slate-700 text-sm">{e.description}</td>
                  <td className={`numeric font-medium ${e.type === 'credit' ? 'text-green-700' : 'text-red-600'}`}>
                    {e.type === 'credit' ? '+' : '-'}{fmtRs(e.amount)}
                  </td>
                  <td className="numeric font-semibold">{fmtRs(e.balance_after)}</td>
                </tr>
              )) : (
                <tr>
                  <td colSpan="5" className="text-center py-12 text-slate-400">
                    <Clock size={40} className="mx-auto mb-3 text-slate-300" />
                    <p className="font-medium">No transactions yet</p>
                    <p className="text-sm mt-1">Earnings will appear here when referrals subscribe</p>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* How It Works */}
      <div className="mt-8 bg-slate-50 border border-slate-200 rounded-xl p-6">
        <h3 className="font-bold text-slate-900 mb-4">How Refer & Earn Works</h3>
        <div className="grid sm:grid-cols-3 gap-4">
          {[
            { step: '1', title: 'Share Your Code', desc: 'Share your unique referral code with businesses who could benefit from FLOWRA.' },
            { step: '2', title: 'They Sign Up', desc: 'When they submit an enquiry with your code, the referral is linked to you.' },
            { step: '3', title: 'Earn 3% Commission', desc: 'Once they subscribe, you earn 3% of their subscription amount.' },
          ].map(s => (
            <div key={s.step} className="flex gap-3">
              <div className="w-8 h-8 bg-[#2563EB] text-white rounded-full flex items-center justify-center text-sm font-bold flex-shrink-0">{s.step}</div>
              <div>
                <h4 className="font-medium text-slate-900 text-sm">{s.title}</h4>
                <p className="text-xs text-slate-500 mt-0.5">{s.desc}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default ReferAndEarn;
