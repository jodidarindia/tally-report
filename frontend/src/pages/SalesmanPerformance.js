import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Users, TrendingUp, Award, Plus, X, Package, ChevronDown, ChevronUp, Save, Trash2 } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts';
import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const SalesmanPerformance = () => {
  const [performance, setPerformance] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('performance');
  const [showAddForm, setShowAddForm] = useState(false);
  const [expandedSalesman, setExpandedSalesman] = useState(null);
  const [customers, setCustomers] = useState([]);

  // Form state
  const [formData, setFormData] = useState({
    salesman_name: '',
    phone: '',
    email: '',
    monthly_target: '',
    quarterly_target: '',
    customers: []
  });

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [perfRes, custRes] = await Promise.all([
        axios.get(`${API}/salesman/performance-detailed`),
        axios.get(`${API}/customers/outstanding`)
      ]);
      setPerformance(perfRes.data?.data?.salesman || []);
      const custList = custRes.data?.data?.customers || [];
      setCustomers(custList.map(c => c.customer_name));
    } catch (error) {
      console.error('Error fetching data:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleSaveSalesman = async (e) => {
    e.preventDefault();
    if (!formData.salesman_name.trim()) {
      toast.error('Salesman name is required');
      return;
    }
    try {
      const payload = {
        ...formData,
        monthly_target: parseFloat(formData.monthly_target) || 0,
        quarterly_target: parseFloat(formData.quarterly_target) || 0
      };
      const res = await axios.post(`${API}/salesman/master`, payload);
      if (res.data?.success) {
        toast.success(`Salesman '${formData.salesman_name}' saved`);
        setShowAddForm(false);
        setFormData({ salesman_name: '', phone: '', email: '', monthly_target: '', quarterly_target: '', customers: [] });
        fetchData();
      } else {
        toast.error(res.data?.error || 'Failed to save');
      }
    } catch (error) {
      toast.error('Failed to save salesman');
    }
  };

  const handleDeleteSalesman = async (name) => {
    if (!window.confirm(`Delete salesman "${name}"?`)) return;
    try {
      await axios.delete(`${API}/salesman/master/${encodeURIComponent(name)}`);
      toast.success('Deleted');
      fetchData();
    } catch (error) {
      toast.error('Failed to delete');
    }
  };

  const handleEditSalesman = (person) => {
    setFormData({
      salesman_name: person.salesman_name,
      phone: person.phone || '',
      email: person.email || '',
      monthly_target: person.monthly_target || '',
      quarterly_target: person.quarterly_target || '',
      customers: person.mapped_customers || []
    });
    setShowAddForm(true);
  };

  const toggleCustomer = (customerName) => {
    setFormData(prev => ({
      ...prev,
      customers: prev.customers.includes(customerName)
        ? prev.customers.filter(c => c !== customerName)
        : [...prev.customers, customerName]
    }));
  };

  const chartData = performance.map(p => ({
    name: p.salesman_name,
    target: p.monthly_target,
    achieved: p.achieved_amount,
    percentage: p.achievement_percentage
  }));

  const topPerformer = performance.length > 0 ? performance[0] : null;

  const tabs = [
    { id: 'performance', label: 'Performance', icon: TrendingUp },
    { id: 'items', label: 'Item-wise Sales', icon: Package },
    { id: 'manage', label: 'Manage Salesmen', icon: Users }
  ];

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="loading-spinner" />
      </div>
    );
  }

  return (
    <div data-testid="salesman-page">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-4xl font-light tracking-tight text-slate-900" style={{ fontFamily: 'Outfit, sans-serif' }}>
            Salesman Performance
          </h1>
          <p className="mt-2 text-base text-slate-600">Track sales team, set targets, and manage customer mapping</p>
        </div>
        <button
          onClick={() => { setShowAddForm(true); setFormData({ salesman_name: '', phone: '', email: '', monthly_target: '', quarterly_target: '', customers: [] }); }}
          className="btn-primary flex items-center gap-2"
          data-testid="add-salesman-button"
        >
          <Plus size={16} />
          Add Salesman
        </button>
      </div>

      {/* Tabs */}
      <div className="bg-white border border-slate-200 rounded-xl p-2 mb-6 flex gap-2">
        {tabs.map(tab => {
          const Icon = tab.icon;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              data-testid={`salesman-tab-${tab.id}`}
              className={`flex-1 flex items-center justify-center gap-2 px-4 py-3 rounded-lg transition-all ${
                activeTab === tab.id ? 'bg-[#2563EB] text-white' : 'text-slate-600 hover:bg-slate-50'
              }`}
            >
              <Icon size={18} />
              <span className="text-sm font-medium">{tab.label}</span>
            </button>
          );
        })}
      </div>

      {/* Top Performer Card */}
      {topPerformer && activeTab === 'performance' && (
        <div className="bg-gradient-to-r from-[#2563EB] to-[#7C3AED] text-white rounded-xl p-8 mb-6">
          <div className="flex items-center gap-3 mb-4">
            <Award size={32} />
            <h2 className="text-2xl font-semibold">Top Performer</h2>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
            <div>
              <div className="text-sm opacity-90">Salesman</div>
              <div className="text-2xl font-bold mt-1">{topPerformer.salesman_name}</div>
            </div>
            <div>
              <div className="text-sm opacity-90">Achievement</div>
              <div className="text-2xl font-bold mt-1">{topPerformer.achievement_percentage.toFixed(1)}%</div>
            </div>
            <div>
              <div className="text-sm opacity-90">Total Sales</div>
              <div className="text-2xl font-bold mt-1">Rs.{topPerformer.achieved_amount.toLocaleString('en-IN')}</div>
            </div>
            <div>
              <div className="text-sm opacity-90">Customers</div>
              <div className="text-2xl font-bold mt-1">{topPerformer.total_customers}</div>
            </div>
          </div>
        </div>
      )}

      {/* Performance Tab */}
      {activeTab === 'performance' && (
        <>
          <div className="bg-white border border-slate-200 rounded-xl p-6 mb-6">
            <h3 className="text-xl font-medium text-slate-900 mb-4">Target vs Achievement</h3>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#E0E7FF" />
                <XAxis dataKey="name" stroke="#64748B" style={{ fontSize: '12px' }} />
                <YAxis stroke="#64748B" style={{ fontSize: '12px' }} />
                <Tooltip contentStyle={{ background: 'white', border: '1px solid #E0E7FF', borderRadius: '8px' }} />
                <Bar dataKey="target" fill="#D1D5DB" name="Target" radius={[4, 4, 0, 0]} />
                <Bar dataKey="achieved" fill="#2563EB" name="Achieved" radius={[4, 4, 0, 0]}>
                  {chartData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.percentage >= 100 ? '#06B6D4' : '#2563EB'} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>

          <div className="bg-white border border-slate-200 rounded-xl overflow-hidden">
            <div className="overflow-x-auto">
              <table className="data-table" data-testid="performance-table">
                <thead>
                  <tr>
                    <th>Rank</th>
                    <th>Salesman</th>
                    <th className="numeric">Monthly Target</th>
                    <th className="numeric">Achieved</th>
                    <th className="numeric">Achievement %</th>
                    <th className="numeric">Customers</th>
                    <th className="numeric">Transactions</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {performance.map((person, idx) => (
                    <tr key={idx}>
                      <td className="font-bold">
                        {idx === 0 ? '1' : idx === 1 ? '2' : idx === 2 ? '3' : idx + 1}
                      </td>
                      <td>
                        <div className="font-medium text-slate-900">{person.salesman_name}</div>
                        {person.has_master && <div className="text-xs text-green-600">Registered</div>}
                      </td>
                      <td className="numeric">Rs.{person.monthly_target.toLocaleString('en-IN', {maximumFractionDigits: 0})}</td>
                      <td className="numeric font-semibold text-[#2563EB]">Rs.{person.achieved_amount.toLocaleString('en-IN')}</td>
                      <td className="numeric">
                        <div className="flex items-center gap-2">
                          <div className="flex-1 h-2 bg-slate-200 rounded-full overflow-hidden max-w-[100px]">
                            <div
                              className={`h-full ${person.achievement_percentage >= 100 ? 'bg-green-500' : 'bg-[#2563EB]'}`}
                              style={{ width: `${Math.min(person.achievement_percentage, 100)}%` }}
                            />
                          </div>
                          <span className="text-sm font-medium">{person.achievement_percentage.toFixed(1)}%</span>
                        </div>
                      </td>
                      <td className="numeric">{person.total_customers}</td>
                      <td className="numeric">{person.total_transactions}</td>
                      <td>
                        {person.achievement_percentage >= 100 ? (
                          <span className="px-3 py-1 rounded-full text-xs font-medium bg-green-100 text-green-700">Achieved</span>
                        ) : person.achievement_percentage >= 75 ? (
                          <span className="px-3 py-1 rounded-full text-xs font-medium bg-yellow-100 text-yellow-700">On Track</span>
                        ) : (
                          <span className="px-3 py-1 rounded-full text-xs font-medium bg-red-100 text-red-700">Behind</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}

      {/* Item-wise Sales Tab */}
      {activeTab === 'items' && (
        <div className="space-y-4">
          {performance.map((person, idx) => (
            <div key={idx} className="bg-white border border-slate-200 rounded-xl overflow-hidden">
              <button
                onClick={() => setExpandedSalesman(expandedSalesman === idx ? null : idx)}
                className="w-full flex items-center justify-between p-5 hover:bg-slate-50 transition-colors"
                data-testid={`salesman-item-expand-${idx}`}
              >
                <div className="flex items-center gap-4">
                  <div className="w-10 h-10 bg-[#2563EB] rounded-full flex items-center justify-center text-white font-bold">
                    {person.salesman_name.charAt(0)}
                  </div>
                  <div className="text-left">
                    <div className="font-semibold text-slate-900">{person.salesman_name}</div>
                    <div className="text-sm text-slate-500">{person.items_sold?.length || 0} items sold | Rs.{person.achieved_amount.toLocaleString('en-IN')} total</div>
                  </div>
                </div>
                {expandedSalesman === idx ? <ChevronUp size={20} className="text-slate-400" /> : <ChevronDown size={20} className="text-slate-400" />}
              </button>

              {expandedSalesman === idx && (
                <div className="border-t border-slate-200">
                  <div className="overflow-x-auto">
                    <table className="data-table" data-testid={`item-table-${idx}`}>
                      <thead>
                        <tr>
                          <th>Item Name</th>
                          <th className="numeric">Qty Sold</th>
                          <th className="numeric">Revenue</th>
                          <th className="numeric">Transactions</th>
                          <th className="numeric">Avg Qty/Txn</th>
                        </tr>
                      </thead>
                      <tbody>
                        {(person.items_sold || []).map((item, itemIdx) => (
                          <tr key={itemIdx}>
                            <td className="font-medium text-slate-900">{item.item_name}</td>
                            <td className="numeric font-semibold">{item.total_quantity}</td>
                            <td className="numeric text-[#2563EB] font-semibold">Rs.{item.total_revenue.toLocaleString('en-IN')}</td>
                            <td className="numeric">{item.transaction_count}</td>
                            <td className="numeric">{(item.total_quantity / item.transaction_count).toFixed(1)}</td>
                          </tr>
                        ))}
                        {(!person.items_sold || person.items_sold.length === 0) && (
                          <tr><td colSpan="5" className="text-center py-4 text-slate-500">No items sold</td></tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Manage Salesmen Tab */}
      {activeTab === 'manage' && (
        <div className="space-y-4">
          {performance.map((person, idx) => (
            <div key={idx} className="bg-white border border-slate-200 rounded-xl p-5">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                  <div className="w-10 h-10 bg-[#2563EB] rounded-full flex items-center justify-center text-white font-bold">
                    {person.salesman_name.charAt(0)}
                  </div>
                  <div>
                    <div className="font-semibold text-slate-900">{person.salesman_name}</div>
                    <div className="text-sm text-slate-500">
                      {person.phone && <span className="mr-3">Phone: {person.phone}</span>}
                      {person.email && <span>Email: {person.email}</span>}
                    </div>
                    <div className="text-xs text-slate-400 mt-1">
                      Target: Rs.{(person.monthly_target || 0).toLocaleString('en-IN', {maximumFractionDigits: 0})}/month
                      {person.mapped_customers?.length > 0 && (
                        <span className="ml-3">Mapped: {person.mapped_customers.join(', ')}</span>
                      )}
                    </div>
                  </div>
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={() => handleEditSalesman(person)}
                    className="btn-secondary text-sm px-3 py-1"
                    data-testid={`edit-salesman-${idx}`}
                  >
                    Edit
                  </button>
                  {person.has_master && (
                    <button
                      onClick={() => handleDeleteSalesman(person.salesman_name)}
                      className="text-red-500 hover:text-red-700 p-1"
                      data-testid={`delete-salesman-${idx}`}
                    >
                      <Trash2 size={16} />
                    </button>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Add/Edit Salesman Modal */}
      {showAddForm && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-6 z-50" onClick={() => setShowAddForm(false)}>
          <div className="bg-white rounded-xl max-w-lg w-full max-h-[90vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
            <div className="sticky top-0 bg-white border-b border-slate-200 p-6 flex items-center justify-between">
              <h2 className="text-xl font-semibold text-slate-900" style={{ fontFamily: 'Outfit, sans-serif' }}>
                {formData.salesman_name ? `Edit: ${formData.salesman_name}` : 'Add Salesman'}
              </h2>
              <button onClick={() => setShowAddForm(false)} className="text-slate-400 hover:text-slate-600">
                <X size={20} />
              </button>
            </div>

            <form onSubmit={handleSaveSalesman} className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Name *</label>
                <input
                  type="text"
                  value={formData.salesman_name}
                  onChange={(e) => setFormData({...formData, salesman_name: e.target.value})}
                  className="w-full px-4 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#2563EB]"
                  placeholder="Salesman name"
                  data-testid="salesman-name-input"
                  required
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">Phone</label>
                  <input
                    type="text"
                    value={formData.phone}
                    onChange={(e) => setFormData({...formData, phone: e.target.value})}
                    className="w-full px-4 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#2563EB]"
                    placeholder="Phone number"
                    data-testid="salesman-phone-input"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">Email</label>
                  <input
                    type="email"
                    value={formData.email}
                    onChange={(e) => setFormData({...formData, email: e.target.value})}
                    className="w-full px-4 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#2563EB]"
                    placeholder="Email"
                    data-testid="salesman-email-input"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">Monthly Target (Rs.)</label>
                  <input
                    type="number"
                    value={formData.monthly_target}
                    onChange={(e) => setFormData({...formData, monthly_target: e.target.value})}
                    className="w-full px-4 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#2563EB]"
                    placeholder="0"
                    data-testid="salesman-monthly-target"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">Quarterly Target (Rs.)</label>
                  <input
                    type="number"
                    value={formData.quarterly_target}
                    onChange={(e) => setFormData({...formData, quarterly_target: e.target.value})}
                    className="w-full px-4 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#2563EB]"
                    placeholder="0"
                    data-testid="salesman-quarterly-target"
                  />
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">Map Customers</label>
                <div className="border border-slate-200 rounded-lg max-h-48 overflow-y-auto p-2 space-y-1">
                  {customers.length > 0 ? customers.map((cust, idx) => (
                    <label key={idx} className="flex items-center gap-2 px-3 py-2 rounded hover:bg-slate-50 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={formData.customers.includes(cust)}
                        onChange={() => toggleCustomer(cust)}
                        className="accent-[#2563EB]"
                      />
                      <span className="text-sm text-slate-700">{cust}</span>
                    </label>
                  )) : (
                    <p className="text-sm text-slate-500 p-2">No customers available. Sync Tally data first.</p>
                  )}
                </div>
                {formData.customers.length > 0 && (
                  <p className="text-xs text-slate-500 mt-1">{formData.customers.length} customer(s) selected</p>
                )}
              </div>

              <div className="flex gap-3 pt-2">
                <button type="submit" className="flex-1 btn-primary py-3 flex items-center justify-center gap-2" data-testid="save-salesman-button">
                  <Save size={16} />
                  Save Salesman
                </button>
                <button type="button" onClick={() => setShowAddForm(false)} className="flex-1 btn-secondary py-3">
                  Cancel
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default SalesmanPerformance;
