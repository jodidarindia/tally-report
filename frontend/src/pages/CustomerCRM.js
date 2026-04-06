import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Users, Phone, Mail, Calendar, TrendingUp, AlertTriangle, CheckCircle } from 'lucide-react';
import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const CustomerCRM = () => {
  const [activeTab, setActiveTab] = useState('outstanding');
  const [outstanding, setOutstanding] = useState([]);
  const [followups, setFollowups] = useState([]);
  const [targets, setTargets] = useState([]);
  const [paymentBehavior, setPaymentBehavior] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showAddFollowup, setShowAddFollowup] = useState(false);
  const [newFollowup, setNewFollowup] = useState({
    customer_name: '',
    followup_date: '',
    followup_type: 'call',
    notes: ''
  });

  useEffect(() => {
    fetchData();
  }, [activeTab]);

  const fetchData = async () => {
    setLoading(true);
    try {
      if (activeTab === 'outstanding') {
        const res = await axios.get(`${API}/customers/outstanding`);
        setOutstanding(res.data?.data?.customers || []);
      } else if (activeTab === 'followups') {
        const res = await axios.get(`${API}/customers/followups`);
        setFollowups(res.data?.data?.followups || []);
      } else if (activeTab === 'targets') {
        const res = await axios.get(`${API}/customers/targets`);
        setTargets(res.data?.data?.targets || []);
      } else if (activeTab === 'behavior') {
        const res = await axios.get(`${API}/customers/payment-behavior`);
        setPaymentBehavior(res.data?.data?.customers || []);
      }
    } catch (error) {
      console.error('Error fetching data:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleAddFollowup = async () => {
    try {
      await axios.post(`${API}/customers/followups`, newFollowup);
      toast.success('Follow-up created successfully!');
      setShowAddFollowup(false);
      setNewFollowup({ customer_name: '', followup_date: '', followup_type: 'call', notes: '' });
      fetchData();
    } catch (error) {
      toast.error('Failed to create follow-up');
    }
  };

  const updateFollowupStatus = async (id, status) => {
    try {
      await axios.patch(`${API}/customers/followups/${id}?status=${status}`);
      toast.success('Follow-up updated!');
      fetchData();
    } catch (error) {
      toast.error('Failed to update');
    }
  };

  const tabs = [
    { id: 'outstanding', label: 'Payment Outstanding', icon: AlertTriangle },
    { id: 'followups', label: 'Follow-ups', icon: Calendar },
    { id: 'targets', label: 'Targets & Achievement', icon: TrendingUp },
    { id: 'behavior', label: 'Payment Behavior', icon: Users }
  ];

  return (
    <div data-testid="crm-page">
      <div className="mb-8">
        <h1 className="text-4xl font-light tracking-tight text-stone-900" style={{ fontFamily: 'Outfit, sans-serif' }}>
          Customer CRM
        </h1>
        <p className="mt-2 text-base text-stone-600">Manage customer relationships and track payments</p>
      </div>

      {/* Tabs */}
      <div className="bg-white border border-stone-200 rounded-xl p-2 mb-6 flex gap-2">
        {tabs.map(tab => {
          const Icon = tab.icon;
          return (
            <button
              key={tab.id}
              data-testid={`tab-${tab.id}`}
              onClick={() => setActiveTab(tab.id)}
              className={`flex-1 flex items-center justify-center gap-2 px-4 py-3 rounded-lg transition-all ${
                activeTab === tab.id
                  ? 'bg-[#064E3B] text-white'
                  : 'text-stone-600 hover:bg-stone-50'
              }`}
            >
              <Icon size={18} />
              <span className="text-sm font-medium">{tab.label}</span>
            </button>
          );
        })}
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-64">
          <div className="loading-spinner" />
        </div>
      ) : (
        <>
          {/* Outstanding Payments */}
          {activeTab === 'outstanding' && (
            <div className="bg-white border border-stone-200 rounded-xl overflow-hidden">
              <div className="overflow-x-auto">
                <table className="data-table" data-testid="outstanding-table">
                  <thead>
                    <tr>
                      <th>Customer Name</th>
                      <th className="numeric">Outstanding</th>
                      <th className="numeric">Overdue</th>
                      <th className="numeric">0-30 Days</th>
                      <th className="numeric">30-60 Days</th>
                      <th className="numeric">60-90 Days</th>
                      <th className="numeric">90+ Days</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {outstanding.map((customer, idx) => (
                      <tr key={idx}>
                        <td className="font-medium text-stone-900">{customer.customer_name}</td>
                        <td className="numeric font-semibold text-[#064E3B]">
                          ₹{customer.outstanding_amount.toLocaleString('en-IN')}
                        </td>
                        <td className="numeric text-red-600">
                          ₹{customer.overdue_amount.toLocaleString('en-IN')}
                        </td>
                        <td className="numeric">₹{customer.aging_30_days.toLocaleString('en-IN')}</td>
                        <td className="numeric">₹{customer.aging_60_days.toLocaleString('en-IN')}</td>
                        <td className="numeric">₹{customer.aging_90_days.toLocaleString('en-IN')}</td>
                        <td className="numeric">₹{customer.aging_90_plus.toLocaleString('en-IN')}</td>
                        <td>
                          {customer.overdue_amount > 50000 ? (
                            <span className="status-badge" style={{ background: '#FEE2E2', color: '#991B1B' }}>
                              High Risk
                            </span>
                          ) : (
                            <span className="status-badge connected">Normal</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Follow-ups */}
          {activeTab === 'followups' && (
            <div>
              <div className="mb-4 flex justify-end">
                <button
                  onClick={() => setShowAddFollowup(true)}
                  className="btn-primary"
                  data-testid="add-followup-button"
                >
                  + Add Follow-up
                </button>
              </div>

              {showAddFollowup && (
                <div className="bg-white border border-stone-200 rounded-xl p-6 mb-6">
                  <h3 className="text-lg font-medium mb-4">New Follow-up</h3>
                  <div className="grid grid-cols-2 gap-4">
                    <input
                      type="text"
                      placeholder="Customer Name"
                      value={newFollowup.customer_name}
                      onChange={(e) => setNewFollowup({...newFollowup, customer_name: e.target.value})}
                      className="px-4 py-2 border rounded-lg"
                    />
                    <input
                      type="datetime-local"
                      value={newFollowup.followup_date}
                      onChange={(e) => setNewFollowup({...newFollowup, followup_date: e.target.value})}
                      className="px-4 py-2 border rounded-lg"
                    />
                    <select
                      value={newFollowup.followup_type}
                      onChange={(e) => setNewFollowup({...newFollowup, followup_type: e.target.value})}
                      className="px-4 py-2 border rounded-lg"
                    >
                      <option value="call">Call</option>
                      <option value="email">Email</option>
                      <option value="visit">Visit</option>
                      <option value="meeting">Meeting</option>
                    </select>
                    <textarea
                      placeholder="Notes"
                      value={newFollowup.notes}
                      onChange={(e) => setNewFollowup({...newFollowup, notes: e.target.value})}
                      className="px-4 py-2 border rounded-lg col-span-2"
                      rows="3"
                    />
                  </div>
                  <div className="flex gap-2 mt-4">
                    <button onClick={handleAddFollowup} className="btn-primary">Save</button>
                    <button onClick={() => setShowAddFollowup(false)} className="btn-secondary">Cancel</button>
                  </div>
                </div>
              )}

              <div className="grid grid-cols-1 gap-4">
                {followups.map((followup, idx) => (
                  <div key={idx} className="bg-white border border-stone-200 rounded-xl p-6">
                    <div className="flex items-center justify-between">
                      <div className="flex-1">
                        <h3 className="text-lg font-medium text-stone-900">{followup.customer_name}</h3>
                        <div className="flex items-center gap-4 mt-2 text-sm text-stone-600">
                          <span className="flex items-center gap-1">
                            <Calendar size={14} />
                            {new Date(followup.followup_date).toLocaleString()}
                          </span>
                          <span className="capitalize">{followup.followup_type}</span>
                        </div>
                        {followup.notes && <p className="mt-2 text-sm text-stone-700">{followup.notes}</p>}
                      </div>
                      <div className="flex gap-2">
                        {followup.status === 'pending' && (
                          <button
                            onClick={() => updateFollowupStatus(followup.id, 'completed')}
                            className="btn-primary"
                          >
                            Mark Complete
                          </button>
                        )}
                        {followup.status === 'completed' && (
                          <span className="status-badge connected flex items-center gap-1">
                            <CheckCircle size={14} /> Completed
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Targets */}
          {activeTab === 'targets' && (
            <div className="bg-white border border-stone-200 rounded-xl overflow-hidden">
              <div className="overflow-x-auto">
                <table className="data-table" data-testid="targets-table">
                  <thead>
                    <tr>
                      <th>Customer Name</th>
                      <th className="numeric">Target</th>
                      <th className="numeric">Achieved</th>
                      <th className="numeric">Achievement %</th>
                      <th className="numeric">Remaining</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {targets.map((target, idx) => (
                      <tr key={idx}>
                        <td className="font-medium">{target.customer_name}</td>
                        <td className="numeric">₹{target.target_amount.toLocaleString('en-IN')}</td>
                        <td className="numeric font-semibold text-[#064E3B]">
                          ₹{target.achieved_amount.toLocaleString('en-IN')}
                        </td>
                        <td className="numeric">
                          <div className="flex items-center gap-2">
                            <div className="flex-1 h-2 bg-stone-200 rounded-full overflow-hidden">
                              <div
                                className="h-full bg-[#064E3B]"
                                style={{ width: `${Math.min(target.achievement_percentage, 100)}%` }}
                              />
                            </div>
                            <span className="text-sm font-medium">
                              {target.achievement_percentage.toFixed(1)}%
                            </span>
                          </div>
                        </td>
                        <td className="numeric">₹{target.remaining.toLocaleString('en-IN')}</td>
                        <td>
                          {target.achievement_percentage >= 100 ? (
                            <span className="status-badge connected">Achieved</span>
                          ) : target.achievement_percentage >= 75 ? (
                            <span className="status-badge" style={{ background: '#FEF3E2', color: '#B45309' }}>
                              On Track
                            </span>
                          ) : (
                            <span className="status-badge" style={{ background: '#FEE2E2', color: '#991B1B' }}>
                              Behind
                            </span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Payment Behavior */}
          {activeTab === 'behavior' && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {paymentBehavior.map((customer, idx) => (
                <div key={idx} className="bg-white border border-stone-200 rounded-xl p-6">
                  <h3 className="text-lg font-medium text-stone-900 mb-4">{customer.customer_name}</h3>
                  <div className="space-y-3">
                    <div className="flex justify-between">
                      <span className="text-sm text-stone-600">Total Transactions</span>
                      <span className="font-semibold">{customer.total_transactions}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-sm text-stone-600">Total Amount</span>
                      <span className="font-semibold">₹{customer.total_amount.toLocaleString('en-IN')}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-sm text-stone-600">Average Transaction</span>
                      <span className="font-semibold">₹{customer.average_transaction.toLocaleString('en-IN')}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-sm text-stone-600">Avg Payment Delay</span>
                      <span className="font-semibold">{customer.average_payment_delay} days</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-sm text-stone-600">Credit Score</span>
                      <span className="font-semibold text-[#064E3B]">{customer.credit_score.toFixed(0)}/100</span>
                    </div>
                    <div className="pt-3 border-t">
                      <span className="text-sm text-stone-600">Payment Pattern:</span>
                      <span className={`ml-2 px-3 py-1 rounded-full text-xs font-medium ${
                        customer.payment_pattern === 'excellent' ? 'bg-green-100 text-green-700' :
                        customer.payment_pattern === 'regular' ? 'bg-blue-100 text-blue-700' :
                        customer.payment_pattern === 'irregular' ? 'bg-yellow-100 text-yellow-700' :
                        'bg-red-100 text-red-700'
                      }`}>
                        {customer.payment_pattern}
                      </span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
};

export default CustomerCRM;
