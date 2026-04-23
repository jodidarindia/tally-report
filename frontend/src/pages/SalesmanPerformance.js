import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import {
  Users, TrendingUp, Award, Plus, X, Package, ChevronDown, ChevronUp,
  Save, Trash2, Download, Calendar, Lock, BarChart3, ShoppingCart
} from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts';
import { toast } from 'sonner';
import SearchableSelect from '../components/SearchableSelect';
import SalesmanOrderApp from './SalesmanOrderApp';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

const fmt = (n) => {
  if (n === undefined || n === null || n === 0) return '0';
  if (n >= 10000000) return `${(n / 10000000).toFixed(2)} Cr`;
  if (n >= 100000) return `${(n / 100000).toFixed(2)} L`;
  if (n >= 1000) return `${(n / 1000).toFixed(1)} K`;
  return Number(n).toLocaleString('en-IN', { maximumFractionDigits: 0 });
};

const DURATION_TABS = [
  { id: 'monthly', label: 'Monthly' },
  { id: 'quarterly', label: 'Quarterly' },
  { id: 'annual', label: 'Annual' },
];

const SalesmanPerformance = ({ selectedFY, companyId }) => {
  const [performance, setPerformance] = useState([]);
  const [periods, setPeriods] = useState({ months: [], month_labels: {}, quarters: [] });
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('performance');
  const [duration, setDuration] = useState('monthly');
  const [expandedSalesman, setExpandedSalesman] = useState(null);
  const [customers, setCustomers] = useState([]);
  const [masterList, setMasterList] = useState([]);
  const [fyLocked, setFyLocked] = useState(false);
  const [currentFy, setCurrentFy] = useState('');
  const [showAddForm, setShowAddForm] = useState(false);
  const [exporting, setExporting] = useState(null);

  const [formData, setFormData] = useState({
    salesman_name: '',
    phone: '',
    email: '',
    monthly_target: '',
    quarterly_target: '',
    customers: [],
    isEdit: false,
  });

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const fyParam = selectedFY ? `fy=${selectedFY}` : '';
      const [perfRes, custRes, masterRes] = await Promise.all([
        axios.get(`${API}/salesman/performance-detailed?${fyParam}&duration=${duration}`),
        axios.get(`${API}/customers/outstanding?${fyParam}`),
        axios.get(`${API}/salesman/master?${fyParam}`),
      ]);
      setPerformance(perfRes.data?.data?.salesman || []);
      setPeriods(perfRes.data?.data?.periods || { months: [], month_labels: {}, quarters: [] });
      setCurrentFy(perfRes.data?.data?.current_fy || '');

      const custList = custRes.data?.data?.customers || [];
      setCustomers(custList.map(c => c.customer_name).sort((a, b) => a.localeCompare(b, 'en', { sensitivity: 'base' })));

      const mData = masterRes.data?.data || {};
      setMasterList(mData.salesmen || []);
      setFyLocked(mData.fy_locked || false);
    } catch (error) {
      console.error('Error fetching data:', error);
    } finally {
      setLoading(false);
    }
  }, [selectedFY, duration]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const handleSaveSalesman = async (e) => {
    e.preventDefault();
    if (!formData.salesman_name.trim()) {
      toast.error('Salesman name is required');
      return;
    }
    try {
      const payload = {
        salesman_name: formData.salesman_name,
        phone: formData.phone,
        email: formData.email,
        monthly_target: parseFloat(formData.monthly_target) || 0,
        quarterly_target: parseFloat(formData.quarterly_target) || 0,
        customers: formData.customers,
        fy: selectedFY || currentFy,
      };
      const res = await axios.post(`${API}/salesman/master`, payload);
      if (res.data?.success) {
        toast.success(res.data.message || `Salesman saved for FY ${selectedFY}`);
        setShowAddForm(false);
        resetForm();
        fetchData();
      } else {
        toast.error(res.data?.error || 'Failed to save');
      }
    } catch (error) {
      toast.error(error.response?.data?.error || 'Failed to save salesman');
    }
  };

  const handleDeleteSalesman = async (name) => {
    if (!window.confirm(`Delete salesman "${name}"? This will remove all FY data.`)) return;
    try {
      await axios.delete(`${API}/salesman/master/${encodeURIComponent(name)}`);
      toast.success('Deleted');
      fetchData();
    } catch (error) {
      toast.error('Failed to delete');
    }
  };

  const handleEditSalesman = (person) => {
    const master = masterList.find(m => m.salesman_name === person.salesman_name);
    setFormData({
      salesman_name: person.salesman_name,
      phone: person.phone || master?.phone || '',
      email: person.email || master?.email || '',
      monthly_target: (master?.monthly_target || person.monthly_target || ''),
      quarterly_target: (master?.quarterly_target || person.quarterly_target || ''),
      customers: master?.customers || person.mapped_customers || [],
      isEdit: true,
    });
    setShowAddForm(true);
  };

  const handleExport = async (salesmanName, dur) => {
    setExporting(`${salesmanName}-${dur}`);
    try {
      const fyParam = selectedFY ? `fy=${selectedFY}` : '';
      const res = await axios.get(
        `${API}/salesman/export?salesman_name=${encodeURIComponent(salesmanName)}&${fyParam}&duration=${dur}`,
        { responseType: 'blob' }
      );
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `salesman_${salesmanName.replace(/ /g, '_')}_${selectedFY}_${dur}.xlsx`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      toast.success('Excel exported');
    } catch {
      toast.error('Export failed');
    } finally {
      setExporting(null);
    }
  };

  const resetForm = () => {
    setFormData({ salesman_name: '', phone: '', email: '', monthly_target: '', quarterly_target: '', customers: [], isEdit: false });
  };

  const topPerformer = performance.length > 0
    ? performance.reduce((best, p) => (p.achievement_percentage > (best?.achievement_percentage || 0) ? p : best), performance[0])
    : null;

  const tabs = [
    { id: 'performance', label: 'Performance', icon: TrendingUp },
    { id: 'items', label: 'Item-wise Sales', icon: Package },
    { id: 'orders', label: 'Orders', icon: ShoppingCart },
    { id: 'manage', label: 'Manage Salesmen', icon: Users },
  ];

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64" data-testid="salesman-loading">
        <div className="w-8 h-8 border-2 border-slate-200 border-t-blue-600 rounded-full animate-spin" />
      </div>
    );
  }

  // Empty state: show Manage option even with no performance data
  const hasData = performance.length > 0;
  const hasMaster = masterList.length > 0;

  return (
    <div data-testid="salesman-page" className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-slate-900" data-testid="salesman-title">Salesman Performance</h1>
          <p className="text-xs text-slate-500 mt-0.5">
            FY {selectedFY || currentFy}
            {fyLocked && <span className="ml-2 inline-flex items-center gap-1 text-amber-600"><Lock size={10} /> Locked</span>}
          </p>
        </div>
        <p className="text-xs text-slate-400">Create salesman users from Profile &gt; Employees with role "Salesman"</p>
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-1 bg-white rounded-xl border border-slate-200 p-1" data-testid="salesman-tabs">
        {tabs.map(tab => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              data-testid={`salesman-tab-${tab.id}`}
              className={`flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs font-medium transition-colors ${
                isActive ? 'bg-[#2563EB] text-white shadow-sm' : 'text-slate-600 hover:bg-slate-50'
              }`}
            >
              <Icon size={14} /> {tab.label}
            </button>
          );
        })}
      </div>

      {/* ========== PERFORMANCE TAB ========== */}
      {activeTab === 'performance' && (
        <>
          {!hasData ? (
            <div className="bg-white border border-slate-200 rounded-xl p-12 text-center" data-testid="no-salesman-message">
              <Users size={48} className="mx-auto text-slate-300 mb-4" />
              <h3 className="text-lg font-semibold text-slate-700 mb-2">No salesman data for this FY</h3>
              <p className="text-sm text-slate-500">Add salesmen and map customers in the Manage tab to see performance data.</p>
            </div>
          ) : (
            <>
              {/* Top Performer */}
              {topPerformer && topPerformer.achieved_amount > 0 && (
                <div className="bg-gradient-to-r from-[#2563EB] to-[#7C3AED] text-white rounded-xl p-6" data-testid="top-performer-card">
                  <div className="flex items-center gap-2 mb-3">
                    <Award size={24} />
                    <h2 className="text-base font-semibold">Best Performer (Weighted Avg)</h2>
                  </div>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                    <div><div className="text-xs opacity-80">Salesman</div><div className="text-lg font-bold mt-0.5">{topPerformer.salesman_name}</div></div>
                    <div><div className="text-xs opacity-80">Achievement</div><div className="text-lg font-bold mt-0.5">{topPerformer.achievement_percentage.toFixed(1)}%</div></div>
                    <div><div className="text-xs opacity-80">Total Sales</div><div className="text-lg font-bold mt-0.5">Rs.{fmt(topPerformer.achieved_amount)}</div></div>
                    <div><div className="text-xs opacity-80">Customers</div><div className="text-lg font-bold mt-0.5">{topPerformer.total_customers}</div></div>
                  </div>
                </div>
              )}

              {/* Duration Toggle */}
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-1 bg-slate-100 rounded-lg p-0.5" data-testid="duration-toggle">
                  {DURATION_TABS.map(d => (
                    <button
                      key={d.id}
                      onClick={() => setDuration(d.id)}
                      data-testid={`duration-${d.id}`}
                      className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
                        duration === d.id ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500 hover:text-slate-700'
                      }`}
                    >
                      {d.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* Per-Salesman Expandable Cards */}
              <div className="space-y-3">
                {performance.map((person, idx) => {
                  const isExpanded = expandedSalesman === idx;
                  return (
                    <div key={idx} className="bg-white border border-slate-200 rounded-xl overflow-hidden" data-testid={`salesman-card-${idx}`}>
                      {/* Summary Row */}
                      <button
                        onClick={() => setExpandedSalesman(isExpanded ? null : idx)}
                        className="w-full flex items-center justify-between p-4 hover:bg-slate-25 transition-colors"
                        data-testid={`salesman-expand-${idx}`}
                      >
                        <div className="flex items-center gap-3">
                          <div className="w-9 h-9 bg-[#2563EB] rounded-full flex items-center justify-center text-white text-sm font-bold">
                            {(person.salesman_name || '?').charAt(0)}
                          </div>
                          <div className="text-left">
                            <div className="text-sm font-semibold text-slate-900">{person.salesman_name}</div>
                            <div className="text-xs text-slate-500">
                              {person.total_customers} customers | {person.total_transactions} txns | Rs.{fmt(person.achieved_amount)}
                            </div>
                          </div>
                        </div>
                        <div className="flex items-center gap-3">
                          <div className="text-right hidden sm:block">
                            <div className="text-xs text-slate-500">Target: Rs.{fmt(person.monthly_target)}/mo</div>
                            <div className="flex items-center gap-1.5 mt-0.5">
                              <div className="w-20 h-1.5 bg-slate-100 rounded-full overflow-hidden">
                                <div
                                  className={`h-full rounded-full ${person.achievement_percentage >= 100 ? 'bg-green-500' : person.achievement_percentage >= 75 ? 'bg-amber-500' : 'bg-red-500'}`}
                                  style={{ width: `${Math.min(person.achievement_percentage, 100)}%` }}
                                />
                              </div>
                              <span className={`text-xs font-semibold ${person.achievement_percentage >= 100 ? 'text-green-600' : person.achievement_percentage >= 75 ? 'text-amber-600' : 'text-red-600'}`}>
                                {person.achievement_percentage.toFixed(1)}%
                              </span>
                            </div>
                          </div>
                          {isExpanded ? <ChevronUp size={18} className="text-slate-400" /> : <ChevronDown size={18} className="text-slate-400" />}
                        </div>
                      </button>

                      {/* Expanded: Customer-wise Breakdown */}
                      {isExpanded && (
                        <div className="border-t border-slate-100">
                          <div className="p-3 flex items-center justify-between bg-slate-50 border-b border-slate-100">
                            <span className="text-xs font-medium text-slate-600">
                              Customer-wise {duration.charAt(0).toUpperCase() + duration.slice(1)} Breakdown
                            </span>
                            <button
                              onClick={() => handleExport(person.salesman_name, duration)}
                              disabled={exporting === `${person.salesman_name}-${duration}`}
                              className="flex items-center gap-1 px-2 py-1 text-[10px] font-medium bg-green-600 text-white rounded-md hover:bg-green-700 disabled:opacity-50 transition-colors"
                              data-testid={`export-${idx}`}
                            >
                              <Download size={10} />
                              {exporting === `${person.salesman_name}-${duration}` ? 'Exporting...' : 'Export Excel'}
                            </button>
                          </div>
                          <div className="overflow-x-auto">
                            <table className="w-full text-xs" data-testid={`breakdown-table-${idx}`}>
                              <thead className="bg-slate-50">
                                <tr>
                                  <th className="px-3 py-2 text-left text-xs font-semibold text-slate-600 sticky left-0 bg-slate-50 z-10">Customer</th>
                                  {duration === 'monthly' && periods.months.map(m => (
                                    <th key={m} className="px-2 py-2 text-center text-[10px] font-semibold text-slate-600 whitespace-nowrap">
                                      {periods.month_labels[m] || m}
                                    </th>
                                  ))}
                                  {duration === 'quarterly' && periods.quarters.map(q => (
                                    <th key={q} className="px-2 py-2 text-center text-[10px] font-semibold text-slate-600 whitespace-nowrap">{q}</th>
                                  ))}
                                  <th className="px-3 py-2 text-right text-xs font-semibold text-slate-600">Total</th>
                                </tr>
                              </thead>
                              <tbody>
                                {(person.customers || []).length > 0 ? (
                                  <>
                                    {person.customers.map((c, ci) => (
                                      <tr key={ci} className="border-t border-slate-50 hover:bg-slate-25">
                                        <td className="px-3 py-2 font-medium text-slate-800 sticky left-0 bg-white z-10 max-w-[180px] truncate">{c.customer_name}</td>
                                        {duration === 'monthly' && periods.months.map(m => {
                                          const val = c.monthly?.[m]?.amount || 0;
                                          return (
                                            <td key={m} className={`px-2 py-2 text-center ${val > 0 ? 'text-slate-800 font-medium' : 'text-slate-300'}`}>
                                              {val > 0 ? fmt(val) : '-'}
                                            </td>
                                          );
                                        })}
                                        {duration === 'quarterly' && periods.quarters.map(q => {
                                          const val = c.quarterly?.[q]?.amount || 0;
                                          return (
                                            <td key={q} className={`px-2 py-2 text-center ${val > 0 ? 'text-slate-800 font-medium' : 'text-slate-300'}`}>
                                              {val > 0 ? fmt(val) : '-'}
                                            </td>
                                          );
                                        })}
                                        <td className="px-3 py-2 text-right font-semibold text-blue-700">{fmt(c.annual_amount)}</td>
                                      </tr>
                                    ))}
                                    {/* Totals Row */}
                                    <tr className="border-t-2 border-slate-200 bg-slate-50 font-semibold">
                                      <td className="px-3 py-2 text-slate-700 sticky left-0 bg-slate-50 z-10">Total</td>
                                      {duration === 'monthly' && periods.months.map(m => {
                                        const total = (person.customers || []).reduce((s, c) => s + (c.monthly?.[m]?.amount || 0), 0);
                                        return <td key={m} className="px-2 py-2 text-center text-slate-800">{total > 0 ? fmt(total) : '-'}</td>;
                                      })}
                                      {duration === 'quarterly' && periods.quarters.map(q => {
                                        const total = (person.customers || []).reduce((s, c) => s + (c.quarterly?.[q]?.amount || 0), 0);
                                        return <td key={q} className="px-2 py-2 text-center text-slate-800">{total > 0 ? fmt(total) : '-'}</td>;
                                      })}
                                      <td className="px-3 py-2 text-right text-blue-700">{fmt(person.achieved_amount)}</td>
                                    </tr>
                                  </>
                                ) : (
                                  <tr><td colSpan={99} className="px-3 py-6 text-center text-slate-400">No customer data for this period</td></tr>
                                )}
                              </tbody>
                            </table>
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </>
          )}
        </>
      )}

      {/* ========== ITEM-WISE SALES TAB ========== */}
      {activeTab === 'items' && (
        <div className="space-y-3">
          {!hasData ? (
            <div className="bg-white border border-slate-200 rounded-xl p-12 text-center" data-testid="no-items-message">
              <Package size={48} className="mx-auto text-slate-300 mb-4" />
              <h3 className="text-lg font-semibold text-slate-700 mb-2">No item-wise sales data for this FY</h3>
              <p className="text-sm text-slate-500">Map salesmen to customers and ensure vouchers have line items to see item-wise breakdown.</p>
            </div>
          ) : (
            performance.map((person, idx) => {
              const isExpanded = expandedSalesman === idx;
              const items = person.items_sold || [];
              return (
                <div key={idx} className="bg-white border border-slate-200 rounded-xl overflow-hidden" data-testid={`item-card-${idx}`}>
                  <button
                    onClick={() => setExpandedSalesman(isExpanded ? null : idx)}
                    className="w-full flex items-center justify-between p-4 hover:bg-slate-25 transition-colors"
                    data-testid={`salesman-item-expand-${idx}`}
                  >
                    <div className="flex items-center gap-3">
                      <div className="w-9 h-9 bg-[#2563EB] rounded-full flex items-center justify-center text-white text-sm font-bold">
                        {(person.salesman_name || '?').charAt(0)}
                      </div>
                      <div className="text-left">
                        <div className="text-sm font-semibold text-slate-900">{person.salesman_name}</div>
                        <div className="text-xs text-slate-500">
                          {items.length} items sold | Rs.{fmt(person.achieved_amount)} total
                        </div>
                      </div>
                    </div>
                    {isExpanded ? <ChevronUp size={18} className="text-slate-400" /> : <ChevronDown size={18} className="text-slate-400" />}
                  </button>

                  {isExpanded && (
                    <div className="border-t border-slate-100 overflow-x-auto">
                      <table className="w-full text-xs" data-testid={`item-table-${idx}`}>
                        <thead className="bg-slate-50">
                          <tr>
                            <th className="px-3 py-2.5 text-left text-xs font-semibold text-slate-600">Item Name</th>
                            <th className="px-3 py-2.5 text-right text-xs font-semibold text-slate-600">Qty Sold</th>
                            <th className="px-3 py-2.5 text-right text-xs font-semibold text-slate-600">Revenue</th>
                            <th className="px-3 py-2.5 text-right text-xs font-semibold text-slate-600">Transactions</th>
                            <th className="px-3 py-2.5 text-right text-xs font-semibold text-slate-600">Avg Qty/Txn</th>
                          </tr>
                        </thead>
                        <tbody>
                          {items.length > 0 ? items.map((item, itemIdx) => (
                            <tr key={itemIdx} className="border-t border-slate-50 hover:bg-slate-25" data-testid={`item-row-${idx}-${itemIdx}`}>
                              <td className="px-3 py-2.5 font-medium text-slate-800">{item.item_name || '-'}</td>
                              <td className="px-3 py-2.5 text-right font-semibold text-slate-800">{(item.total_quantity || 0).toFixed(1)}</td>
                              <td className="px-3 py-2.5 text-right font-semibold text-blue-700">Rs.{fmt(item.total_revenue)}</td>
                              <td className="px-3 py-2.5 text-right text-slate-600">{item.transaction_count || 0}</td>
                              <td className="px-3 py-2.5 text-right text-slate-600">{item.transaction_count > 0 ? ((item.total_quantity || 0) / item.transaction_count).toFixed(1) : '0'}</td>
                            </tr>
                          )) : (
                            <tr><td colSpan="5" className="px-3 py-6 text-center text-slate-400">No item-wise data. Voucher line items needed.</td></tr>
                          )}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              );
            })
          )}
        </div>
      )}

      {/* ========== ORDERS TAB ========== */}
      {activeTab === 'orders' && (
        <SalesmanOrderApp user={{role: 'admin'}} selectedFY={selectedFY} companyId={companyId} />
      )}

      {/* ========== MANAGE TAB ========== */}
      {activeTab === 'manage' && (
        <div className="space-y-3">
          {fyLocked && (
            <div className="bg-amber-50 border border-amber-200 rounded-xl p-3 flex items-center gap-2" data-testid="fy-locked-banner">
              <Lock size={16} className="text-amber-600 flex-shrink-0" />
              <p className="text-xs text-amber-700">
                FY {selectedFY} has ended. Targets and customer mappings are locked for this FY. Switch to the current FY to make changes.
              </p>
            </div>
          )}
          {masterList.length === 0 && !hasData ? (
            <div className="bg-white border border-slate-200 rounded-xl p-12 text-center" data-testid="no-master-message">
              <Users size={48} className="mx-auto text-slate-300 mb-4" />
              <h3 className="text-lg font-semibold text-slate-700 mb-2">No salesmen configured</h3>
              <p className="text-sm text-slate-500">Click "Add Salesman" to create a salesman and map customers.</p>
            </div>
          ) : (
            (masterList.length > 0 ? masterList : performance).map((person, idx) => (
              <div key={idx} className="bg-white border border-slate-200 rounded-xl p-4" data-testid={`manage-card-${idx}`}>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-9 h-9 bg-[#2563EB] rounded-full flex items-center justify-center text-white text-sm font-bold">
                      {(person.salesman_name || '?').charAt(0)}
                    </div>
                    <div>
                      <div className="text-sm font-semibold text-slate-900">{person.salesman_name}</div>
                      <div className="text-xs text-slate-500">
                        {person.phone && <span className="mr-3">Ph: {person.phone}</span>}
                        {person.email && <span>Email: {person.email}</span>}
                      </div>
                      <div className="text-[10px] text-slate-400 mt-0.5 flex flex-wrap gap-x-4">
                        <span>Monthly Target: Rs.{fmt(person.monthly_target || 0)}</span>
                        <span>Quarterly: Rs.{fmt(person.quarterly_target || 0)}</span>
                        <span>Customers: {(person.customers || person.mapped_customers || []).length}</span>
                      </div>
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <button
                      onClick={() => handleEditSalesman(person)}
                      className="px-3 py-1.5 text-xs font-medium border border-slate-200 rounded-lg hover:bg-slate-50 text-slate-700 transition-colors"
                      data-testid={`edit-salesman-${idx}`}
                    >
                      Edit
                    </button>
                    <button
                      onClick={() => handleDeleteSalesman(person.salesman_name)}
                      className="p-1.5 text-red-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                      data-testid={`delete-salesman-${idx}`}
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      )}

      {/* ========== ADD/EDIT MODAL ========== */}
      {showAddForm && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50" onClick={() => setShowAddForm(false)}>
          <div className="bg-white rounded-xl max-w-lg w-full max-h-[90vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
            <div className="sticky top-0 bg-white border-b border-slate-200 p-5 flex items-center justify-between z-10">
              <div>
                <h2 className="text-base font-semibold text-slate-900">
                  {formData.isEdit ? `Edit: ${formData.salesman_name}` : 'Add Salesman'}
                </h2>
                <p className="text-xs text-slate-500 mt-0.5">
                  FY {selectedFY || currentFy}
                  {fyLocked && <span className="ml-1 text-amber-600">(Locked - cannot save)</span>}
                </p>
              </div>
              <button onClick={() => setShowAddForm(false)} className="text-slate-400 hover:text-slate-600"><X size={18} /></button>
            </div>

            <form onSubmit={handleSaveSalesman} className="p-5 space-y-4">
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">Name *</label>
                <input
                  type="text"
                  value={formData.salesman_name}
                  onChange={(e) => setFormData({ ...formData, salesman_name: e.target.value })}
                  className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#2563EB]"
                  placeholder="Salesman name"
                  disabled={formData.isEdit}
                  data-testid="salesman-name-input"
                  required
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">Phone</label>
                  <input type="text" value={formData.phone} onChange={(e) => setFormData({ ...formData, phone: e.target.value })} className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#2563EB]" placeholder="Phone" data-testid="salesman-phone-input" />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">Email</label>
                  <input type="email" value={formData.email} onChange={(e) => setFormData({ ...formData, email: e.target.value })} className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#2563EB]" placeholder="Email" data-testid="salesman-email-input" />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">Monthly Target (Rs.) - FY {selectedFY || currentFy}</label>
                  <input type="number" value={formData.monthly_target} onChange={(e) => setFormData({ ...formData, monthly_target: e.target.value })} className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#2563EB]" placeholder="0" data-testid="salesman-monthly-target" />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">Quarterly Target (Rs.)</label>
                  <input type="number" value={formData.quarterly_target} onChange={(e) => setFormData({ ...formData, quarterly_target: e.target.value })} className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#2563EB]" placeholder="0" data-testid="salesman-quarterly-target" />
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1.5">Map Customers - FY {selectedFY || currentFy}</label>
                <SearchableSelect
                  options={customers}
                  value={formData.customers}
                  onChange={(val) => setFormData({ ...formData, customers: val })}
                  placeholder="Search and select customers..."
                  multiple={true}
                  disabled={fyLocked}
                  testId="customer-mapping-select"
                />
              </div>

              <div className="flex gap-3 pt-2">
                <button
                  type="submit"
                  disabled={fyLocked}
                  className="flex-1 flex items-center justify-center gap-2 py-2.5 bg-[#2563EB] text-white text-sm font-medium rounded-lg hover:bg-[#1D4ED8] disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                  data-testid="save-salesman-button"
                >
                  <Save size={14} />
                  {fyLocked ? 'FY Locked' : 'Save'}
                </button>
                <button type="button" onClick={() => setShowAddForm(false)} className="flex-1 py-2.5 border border-slate-200 text-sm font-medium rounded-lg text-slate-700 hover:bg-slate-50 transition-colors">
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
