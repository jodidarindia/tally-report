import React, { useState, useEffect, useCallback, useMemo } from 'react';
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
  // iter-110: Copy-from-another-salesman modal state.
  const [copyModal, setCopyModal] = useState(null); // { to_salesman }
  const [copyFrom, setCopyFrom] = useState('');
  const [copyCustomers, setCopyCustomers] = useState(true);
  const [copyBeats, setCopyBeats] = useState(true);
  const [copyReleaseSource, setCopyReleaseSource] = useState(true);
  const [copyBusy, setCopyBusy] = useState(false);
  // ownership[customer_lower] = owner_salesman_name (FY-scoped)
  const [ownership, setOwnership] = useState({});

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
      const [perfRes, custRes, masterRes, ownRes] = await Promise.all([
        axios.get(`${API}/salesman/performance-detailed?${fyParam}&duration=${duration}`),
        axios.get(`${API}/customers/outstanding?${fyParam}`),
        axios.get(`${API}/salesman/master?${fyParam}`),
        axios.get(`${API}/salesman/customer-ownership?${fyParam}`),
      ]);
      setPerformance(perfRes.data?.data?.salesman || []);
      setPeriods(perfRes.data?.data?.periods || { months: [], month_labels: {}, quarters: [] });
      setCurrentFy(perfRes.data?.data?.current_fy || '');

      const custList = custRes.data?.data?.customers || [];
      setCustomers(custList.map(c => c.customer_name).sort((a, b) => a.localeCompare(b, 'en', { sensitivity: 'base' })));

      const mData = masterRes.data?.data || {};
      setMasterList(mData.salesmen || []);
      setFyLocked(mData.fy_locked || false);
      setOwnership(ownRes.data?.data?.ownership || {});
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
        // Conflict: show details with longer duration so user can read the list
        const conflicts = res.data?.data?.conflicts;
        if (conflicts && conflicts.length) {
          toast.error(res.data.error, { duration: 8000 });
        } else {
          toast.error(res.data?.error || 'Failed to save');
        }
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

  const openCopyModal = (toSalesman) => {
    setCopyFrom('');
    setCopyCustomers(true);
    setCopyBeats(true);
    setCopyReleaseSource(true);
    setCopyModal({ to_salesman: toSalesman });
  };

  const handleCopySalesmanData = async () => {
    if (!copyFrom) { toast.error('Pick a source salesman'); return; }
    if (!copyCustomers && !copyBeats) { toast.error('Tick at least one item to copy'); return; }
    setCopyBusy(true);
    try {
      const res = await axios.post(`${API}/salesman/copy-from`, {
        from_salesman: copyFrom,
        to_salesman: copyModal.to_salesman,
        copy_customers: copyCustomers,
        copy_beats: copyBeats,
        release_source: copyReleaseSource,
        fy: selectedFY || currentFy,
      });
      if (res.data?.success) {
        const d = res.data.data || {};
        toast.success(`Copied: ${d.customers_copied || 0} customers, ${d.beats_copied || 0} beats${d.source_released ? ' · source released' : ''}`);
        setCopyModal(null);
        fetchData();
      } else {
        toast.error(res.data?.error || 'Copy failed');
      }
    } catch (err) {
      toast.error(err.response?.data?.error || 'Copy failed');
    } finally {
      setCopyBusy(false);
    }
  };

  const topPerformer = performance.length > 0
    ? performance.reduce((best, p) => (p.achievement_percentage > (best?.achievement_percentage || 0) ? p : best), performance[0])
    : null;

  const tabs = [
    { id: 'performance', label: 'Performance', icon: TrendingUp },
    { id: 'items', label: 'Item-wise Sales', icon: Package },
    { id: 'orders', label: 'Orders', icon: ShoppingCart },
    { id: 'beats', label: 'Beat Plans', icon: Calendar },
    { id: 'beat-runs', label: 'Beat Runs', icon: Calendar },
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

      {/* Tabs — horizontally scrollable on mobile, inline on desktop */}
      <div className="flex items-center gap-1 bg-white rounded-xl border border-slate-200 p-1 overflow-x-auto -mx-2 px-2 sm:mx-0 sm:px-1" data-testid="salesman-tabs">
        {tabs.map(tab => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              data-testid={`salesman-tab-${tab.id}`}
              className={`flex items-center gap-1.5 px-3 sm:px-4 py-2 rounded-lg text-xs font-medium transition-colors flex-shrink-0 whitespace-nowrap ${
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

      {/* ========== BEAT PLANS TAB ========== */}
      {activeTab === 'beats' && (
        <BeatPlansAdmin companyId={companyId} masterList={masterList} customers={customers} />
      )}

      {/* ========== BEAT RUNS (history) TAB ========== */}
      {activeTab === 'beat-runs' && (
        <BeatRunsAdmin companyId={companyId} masterList={masterList} />
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
                      onClick={() => openCopyModal(person.salesman_name)}
                      className="px-3 py-1.5 text-xs font-medium border border-slate-200 rounded-lg hover:bg-blue-50 hover:text-blue-700 text-slate-700 transition-colors"
                      title="Copy customer mapping and/or beat plan from another salesman"
                      data-testid={`copy-from-${idx}`}
                    >
                      Copy from…
                    </button>
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

      {/* ========== COPY-FROM MODAL ========== */}
      {copyModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50" onClick={() => !copyBusy && setCopyModal(null)} data-testid="copy-from-modal">
          <div className="bg-white rounded-xl max-w-md w-full" onClick={(e) => e.stopPropagation()}>
            <div className="border-b border-slate-200 p-5 flex items-center justify-between">
              <div>
                <h2 className="text-base font-semibold text-slate-900">Copy data to: {copyModal.to_salesman}</h2>
                <p className="text-xs text-slate-500 mt-0.5">FY {selectedFY || currentFy}</p>
              </div>
              <button onClick={() => setCopyModal(null)} className="text-slate-400 hover:text-slate-600"><X size={18} /></button>
            </div>
            <div className="p-5 space-y-4">
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">Source salesman (leaving / replaced)</label>
                <select
                  value={copyFrom}
                  onChange={(e) => setCopyFrom(e.target.value)}
                  className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#2563EB]"
                  data-testid="copy-from-source-select"
                >
                  <option value="">— pick a source salesman —</option>
                  {masterList.filter(m => m.salesman_name !== copyModal.to_salesman).map(m => (
                    <option key={m.salesman_name} value={m.salesman_name}>{m.salesman_name}</option>
                  ))}
                </select>
              </div>
              <div className="space-y-2">
                <label className="flex items-center gap-2 text-sm cursor-pointer">
                  <input type="checkbox" checked={copyCustomers} onChange={(e) => setCopyCustomers(e.target.checked)} data-testid="copy-customers-checkbox" />
                  <span>Copy customer mapping for this FY</span>
                </label>
                <label className="flex items-center gap-2 text-sm cursor-pointer">
                  <input type="checkbox" checked={copyBeats} onChange={(e) => setCopyBeats(e.target.checked)} data-testid="copy-beats-checkbox" />
                  <span>Copy beat plan (weekly schedule)</span>
                </label>
                <label className="flex items-center gap-2 text-sm cursor-pointer pt-2 border-t border-slate-100">
                  <input type="checkbox" checked={copyReleaseSource} onChange={(e) => setCopyReleaseSource(e.target.checked)} data-testid="copy-release-source-checkbox" />
                  <span className="text-amber-700">Release customers from source salesman</span>
                </label>
                <p className="text-[11px] text-slate-500 pl-6">
                  Recommended ON when the source salesman has left.
                  A customer can only belong to one salesman per FY.
                </p>
              </div>
            </div>
            <div className="border-t border-slate-200 p-4 flex justify-end gap-2">
              <button onClick={() => setCopyModal(null)} disabled={copyBusy} className="px-4 py-2 text-sm border border-slate-200 rounded-lg hover:bg-slate-50">Cancel</button>
              <button onClick={handleCopySalesmanData} disabled={copyBusy} className="px-4 py-2 text-sm bg-[#2563EB] text-white rounded-lg hover:bg-[#1D4ED8] disabled:opacity-50" data-testid="copy-from-confirm">
                {copyBusy ? 'Copying…' : 'Copy'}
              </button>
            </div>
          </div>
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
                  disabledOptions={(() => {
                    // Lock customers already mapped to a DIFFERENT salesman.
                    // Customers mapped to the salesman being edited remain selectable
                    // (so they show as already-checked and can be unchecked to unmap).
                    const editingName = (formData.salesman_name || '').trim().toLowerCase();
                    const out = {};
                    for (const [cust, owner] of Object.entries(ownership || {})) {
                      if ((owner || '').trim().toLowerCase() !== editingName) {
                        out[cust] = owner;
                      }
                    }
                    return out;
                  })()}
                />
                <p className="text-[10px] text-slate-400 mt-1">A customer can only be mapped to one salesman per FY. Customers locked here are owned by another salesman — unmap them there first if you want to reassign.</p>
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

// ─── Beat Runs Admin (read-only history viewer for any salesman) ─────────
function BeatRunsAdmin({ companyId, masterList }) {
  const [view, setView] = useState('daily');
  const [salesman, setSalesman] = useState('');
  const [runs, setRuns] = useState([]);
  const [loading, setLoading] = useState(false);
  const [selRun, setSelRun] = useState(null);
  const [todayRun, setTodayRun] = useState(null);

  const hdr = useCallback(() => ({
    Authorization: `Bearer ${localStorage.getItem('flowra_token')}`,
    'X-Company-Id': companyId || '',
  }), [companyId]);

  const fetchHistory = useCallback(async () => {
    setLoading(true);
    setRuns([]); setTodayRun(null); setSelRun(null);
    try {
      const url = `${API}/salesman-orders/beat-run/history?company_id=${companyId || ''}${salesman ? `&salesman=${encodeURIComponent(salesman)}` : ''}&limit=90`;
      const r = await axios.get(url, { headers: hdr() });
      if (r.data?.success) setRuns(r.data.data.runs || []);
      if (salesman) {
        const t = await axios.get(`${API}/salesman-orders/beat-run/today?company_id=${companyId || ''}&salesman=${encodeURIComponent(salesman)}`, { headers: hdr() });
        if (t.data?.success) setTodayRun(t.data.data);
      }
    } catch { /* ignore */ }
    setLoading(false);
  }, [companyId, hdr, salesman]);

  useEffect(() => { if (view === 'daily') fetchHistory(); }, [fetchHistory, view]);

  return (
    <div className="space-y-3" data-testid="beat-runs-admin">
      <div className="bg-white border border-slate-200 rounded-xl p-3 sm:p-4 space-y-3">
        <div className="flex flex-wrap items-end gap-3">
          <div className="flex-1 min-w-[200px]">
            <label className="text-[11px] text-slate-500 font-semibold uppercase block mb-1">Salesman</label>
            <select value={salesman} onChange={e => setSalesman(e.target.value)}
              className="w-full sm:max-w-xs px-3 py-2 text-sm border border-slate-200 rounded-lg" data-testid="beat-runs-salesman-select">
              <option value="">— All salesmen —</option>
              {masterList.map((m, i) => <option key={i} value={m.salesman_name}>{m.salesman_name}</option>)}
            </select>
          </div>
          <div className="flex bg-slate-100 rounded-lg p-1" data-testid="beat-runs-view-toggle">
            <button
              onClick={() => setView('daily')}
              className={`px-3 py-1.5 text-xs font-semibold rounded ${view === 'daily' ? 'bg-white text-slate-800 shadow-sm' : 'text-slate-500'}`}
              data-testid="beat-runs-tab-daily"
            >Daily History</button>
            <button
              onClick={() => setView('monthly')}
              className={`px-3 py-1.5 text-xs font-semibold rounded ${view === 'monthly' ? 'bg-white text-slate-800 shadow-sm' : 'text-slate-500'}`}
              data-testid="beat-runs-tab-monthly"
            >Monthly Report</button>
          </div>
        </div>
      </div>

      {view === 'monthly' ? (
        <BeatRunMonthlyReport companyId={companyId} salesman={salesman} hdr={hdr} />
      ) : loading ? <div className="flex items-center justify-center h-32"><div className="w-6 h-6 border-2 border-slate-200 border-t-blue-600 rounded-full animate-spin" /></div> :
        selRun ? (
          <div data-testid="admin-history-detail">
            <button onClick={() => setSelRun(null)} className="text-xs text-blue-600 mb-2 flex items-center gap-1" data-testid="admin-back-history">‹ Back</button>
            <BeatRunReadOnlyView runDate={selRun.run_date} salesman={selRun.salesman} companyId={companyId} hdr={hdr} />
          </div>
        ) : (
          <>
            {todayRun && salesman && (
              <div className="bg-blue-50 border-l-4 border-blue-500 rounded-r-lg p-3" data-testid="admin-today-run">
                <p className="text-[10px] uppercase font-bold text-blue-700 tracking-wider mb-0.5">Today's Run</p>
                <BeatRunReadOnlyView runDate={todayRun.run_date} salesman={todayRun.salesman} companyId={companyId} hdr={hdr} embedded />
              </div>
            )}
            <div className="space-y-2">
              {runs.length === 0 && <p className="text-center text-xs text-slate-400 py-8 italic">No beat runs recorded yet.</p>}
              {runs.map((r, i) => {
                const date = (() => { try { return new Date(r.run_date).toLocaleDateString('en-IN', { weekday: 'short', day: '2-digit', month: 'short', year: 'numeric' }); } catch { return r.run_date; } })();
                const pct = r.planned_count ? Math.round(r.visited_count / r.planned_count * 100) : 0;
                return (
                  <button key={i} onClick={() => setSelRun(r)} className="w-full text-left bg-white rounded-lg border border-slate-200 p-3 hover:border-blue-300" data-testid={`admin-history-${i}`}>
                    <div className="flex items-center justify-between gap-2">
                      <div className="min-w-0">
                        <div className="text-xs sm:text-sm font-semibold text-slate-800">{date}</div>
                        <p className="text-[11px] text-slate-500">{r.salesman} · {r.visited_count}/{r.planned_count} planned · {r.unplanned_count} unplanned</p>
                      </div>
                      <div className="text-right">
                        <div className={`text-base font-bold ${pct >= 80 ? 'text-green-600' : pct >= 50 ? 'text-blue-600' : pct >= 20 ? 'text-amber-600' : 'text-slate-400'}`}>{pct}%</div>
                        <div className="text-[9px] text-slate-400">coverage</div>
                      </div>
                    </div>
                  </button>
                );
              })}
            </div>
          </>
        )
      }
    </div>
  );
}


// ── Monthly Report (admin/super_admin) ─────────────────────────────────────
function BeatRunMonthlyReport({ companyId, salesman, hdr }) {
  const todayMonth = new Date().toISOString().slice(0, 7);
  const [month, setMonth] = useState(todayMonth);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [showAllCustomers, setShowAllCustomers] = useState(false);

  const fetchReport = useCallback(async () => {
    setLoading(true);
    setData(null);
    try {
      const url = `${API}/salesman-orders/beat-run/monthly-report?month=${month}${salesman ? `&salesman=${encodeURIComponent(salesman)}` : ''}&company_id=${companyId || ''}&trend_months=6`;
      const r = await axios.get(url, { headers: hdr() });
      if (r.data?.success) setData(r.data.data);
      else toast.error(r.data?.error || 'Failed to load monthly report');
    } catch (e) {
      toast.error(e?.response?.data?.error || 'Failed to load monthly report');
    }
    setLoading(false);
  }, [companyId, hdr, month, salesman]);

  useEffect(() => { fetchReport(); }, [fetchReport]);

  const handleExport = async (fmt) => {
    setExporting(true);
    try {
      const url = `${API}/salesman-orders/beat-run/monthly-report/export?month=${month}${salesman ? `&salesman=${encodeURIComponent(salesman)}` : ''}&company_id=${companyId || ''}&format=${fmt}`;
      const r = await axios.get(url, { headers: hdr(), responseType: 'blob' });
      const blob = new Blob([r.data], {
        type: fmt === 'csv' ? 'text/csv' : 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      });
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = `flowra-beat-run-${month}${salesman ? `-${salesman}` : ''}.${fmt === 'csv' ? 'csv' : 'xlsx'}`;
      document.body.appendChild(a); a.click(); a.remove();
      URL.revokeObjectURL(a.href);
      toast.success(`Downloaded ${fmt.toUpperCase()}`);
    } catch (e) {
      toast.error(e?.response?.data?.error || 'Export failed');
    }
    setExporting(false);
  };

  // Tiny inline SVG sparkline (no recharts overhead)
  const Sparkline = ({ trend }) => {
    if (!trend || trend.length === 0) return null;
    const w = 220, h = 48, pad = 4;
    const max = Math.max(100, ...trend.map(t => t.coverage_pct));
    const stepX = (w - pad * 2) / Math.max(1, trend.length - 1);
    const points = trend.map((t, i) => {
      const x = pad + i * stepX;
      const y = h - pad - (t.coverage_pct / max) * (h - pad * 2);
      return [x, y, t];
    });
    const path = points.map(([x, y], i) => `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`).join(' ');
    const last = points[points.length - 1];
    return (
      <svg width={w} height={h} className="overflow-visible" data-testid="beat-runs-trend-sparkline">
        <path d={path} fill="none" stroke="#2563EB" strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
        {points.map(([x, y], i) => (
          <circle key={i} cx={x} cy={y} r={2.5} fill={i === points.length - 1 ? '#2563EB' : '#93C5FD'} />
        ))}
        <text x={last[0] + 6} y={last[1] + 4} fontSize="11" fontWeight="700" fill="#1E40AF">{last[2].coverage_pct}%</text>
      </svg>
    );
  };

  if (loading) {
    return <div className="flex items-center justify-center h-40" data-testid="monthly-report-loading">
      <div className="w-6 h-6 border-2 border-slate-200 border-t-blue-600 rounded-full animate-spin" />
    </div>;
  }

  const summary = data?.summary || {};
  const perSalesman = data?.per_salesman || [];
  const perCustomer = data?.per_customer || [];
  const daily = data?.daily_breakdown || [];
  const trend = data?.trend || [];
  const empty = !summary.run_days;
  const customersToShow = showAllCustomers ? perCustomer : perCustomer.slice(0, 20);
  const monthLabel = (() => {
    try {
      const [y, m] = month.split('-');
      return new Date(Number(y), Number(m) - 1, 1).toLocaleDateString('en-IN', { month: 'long', year: 'numeric' });
    } catch { return month; }
  })();

  return (
    <div className="space-y-3" data-testid="beat-runs-monthly-report">
      {/* Month picker + export */}
      <div className="bg-white border border-slate-200 rounded-xl p-3 sm:p-4 flex flex-wrap items-end gap-3">
        <div>
          <label className="text-[11px] text-slate-500 font-semibold uppercase block mb-1">Month</label>
          <input type="month" value={month} onChange={e => setMonth(e.target.value)} max={todayMonth}
            className="px-3 py-2 text-sm border border-slate-200 rounded-lg" data-testid="monthly-report-month-input" />
        </div>
        <div className="ml-auto flex gap-2">
          <button onClick={() => handleExport('csv')} disabled={exporting || empty}
            className="px-3 py-2 text-xs font-semibold bg-slate-100 text-slate-700 rounded-lg flex items-center gap-1.5 disabled:opacity-40"
            data-testid="monthly-report-export-csv">
            <Download size={14} /> CSV
          </button>
          <button onClick={() => handleExport('excel')} disabled={exporting || empty}
            className="px-3 py-2 text-xs font-semibold bg-blue-600 text-white rounded-lg flex items-center gap-1.5 disabled:opacity-40"
            data-testid="monthly-report-export-excel">
            <Download size={14} /> Excel (4 sheets)
          </button>
        </div>
      </div>

      {empty ? (
        <div className="bg-white border border-slate-200 rounded-xl p-12 text-center" data-testid="monthly-report-empty">
          <BarChart3 size={36} className="mx-auto text-slate-300 mb-3" />
          <p className="text-sm text-slate-600 font-semibold">No beat runs in {monthLabel}</p>
          <p className="text-xs text-slate-400 mt-1">{salesman ? `for ${salesman}` : 'for any salesman'}.</p>
        </div>
      ) : (
        <>
          {/* Summary cards */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2" data-testid="monthly-report-summary">
            <div className="bg-white border border-slate-200 rounded-xl p-3">
              <p className="text-[10px] uppercase text-slate-500 font-bold tracking-wider">Coverage</p>
              <p className={`text-2xl font-extrabold mt-1 ${summary.coverage_pct >= 80 ? 'text-green-600' : summary.coverage_pct >= 50 ? 'text-blue-600' : 'text-amber-600'}`}>
                {summary.coverage_pct}%
              </p>
              <p className="text-[10px] text-slate-400 mt-0.5">{summary.visited}/{summary.planned} visited</p>
            </div>
            <div className="bg-white border border-slate-200 rounded-xl p-3">
              <p className="text-[10px] uppercase text-slate-500 font-bold tracking-wider">Run Days</p>
              <p className="text-2xl font-extrabold mt-1 text-slate-800">{summary.run_days}</p>
              <p className="text-[10px] text-slate-400 mt-0.5">{summary.salesmen_count} salesmen</p>
            </div>
            <div className="bg-white border border-slate-200 rounded-xl p-3">
              <p className="text-[10px] uppercase text-slate-500 font-bold tracking-wider">Planned</p>
              <p className="text-2xl font-extrabold mt-1 text-slate-800">{summary.planned}</p>
            </div>
            <div className="bg-white border border-slate-200 rounded-xl p-3">
              <p className="text-[10px] uppercase text-slate-500 font-bold tracking-wider">Unplanned</p>
              <p className="text-2xl font-extrabold mt-1 text-purple-600">{summary.unplanned}</p>
              <p className="text-[10px] text-slate-400 mt-0.5">walk-ins / new prospects</p>
            </div>
          </div>

          {/* Trend sparkline */}
          {trend.length > 0 && (
            <div className="bg-white border border-slate-200 rounded-xl p-3 sm:p-4 flex items-center gap-4 flex-wrap" data-testid="monthly-report-trend">
              <div>
                <p className="text-[10px] uppercase text-slate-500 font-bold tracking-wider">6-Month Coverage Trend</p>
                <p className="text-[11px] text-slate-400 mt-0.5">{trend[0]?.month} → {trend[trend.length - 1]?.month}</p>
              </div>
              <Sparkline trend={trend} />
              <div className="text-[10px] text-slate-500 ml-auto grid grid-cols-3 sm:grid-cols-6 gap-2">
                {trend.map((t, i) => (
                  <div key={i} className="text-center">
                    <p className="text-[9px] text-slate-400">{t.month.slice(5)}</p>
                    <p className={`font-bold ${t.coverage_pct >= 80 ? 'text-green-600' : t.coverage_pct >= 50 ? 'text-blue-600' : t.coverage_pct >= 1 ? 'text-amber-600' : 'text-slate-300'}`}>{t.coverage_pct}%</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Per-salesman table */}
          {perSalesman.length > 0 && (
            <div className="bg-white border border-slate-200 rounded-xl overflow-hidden" data-testid="monthly-report-per-salesman">
              <div className="px-4 py-2.5 border-b border-slate-200 bg-slate-50">
                <h4 className="text-xs font-bold text-slate-700 uppercase tracking-wider">By Salesman ({perSalesman.length})</h4>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead className="bg-slate-50 text-slate-500 uppercase tracking-wider text-[10px]">
                    <tr>
                      <th className="px-3 py-2 text-left">Salesman</th>
                      <th className="px-3 py-2 text-right">Run Days</th>
                      <th className="px-3 py-2 text-right">Planned</th>
                      <th className="px-3 py-2 text-right">Visited</th>
                      <th className="px-3 py-2 text-right">Unplanned</th>
                      <th className="px-3 py-2 text-right">Coverage</th>
                    </tr>
                  </thead>
                  <tbody>
                    {perSalesman.map((s, i) => (
                      <tr key={i} className="border-t border-slate-100" data-testid={`monthly-report-sm-${i}`}>
                        <td className="px-3 py-2 font-semibold text-slate-800">{s.salesman}</td>
                        <td className="px-3 py-2 text-right text-slate-600">{s.run_days}</td>
                        <td className="px-3 py-2 text-right text-slate-600">{s.planned}</td>
                        <td className="px-3 py-2 text-right text-slate-600">{s.visited}</td>
                        <td className="px-3 py-2 text-right text-purple-600 font-semibold">{s.unplanned}</td>
                        <td className={`px-3 py-2 text-right font-bold ${s.coverage_pct >= 80 ? 'text-green-600' : s.coverage_pct >= 50 ? 'text-blue-600' : 'text-amber-600'}`}>{s.coverage_pct}%</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Per-customer visit frequency */}
          {perCustomer.length > 0 && (
            <div className="bg-white border border-slate-200 rounded-xl overflow-hidden" data-testid="monthly-report-per-customer">
              <div className="px-4 py-2.5 border-b border-slate-200 bg-slate-50 flex items-center justify-between">
                <h4 className="text-xs font-bold text-slate-700 uppercase tracking-wider">Customer Visit Frequency ({perCustomer.length})</h4>
                {perCustomer.length > 20 && (
                  <button onClick={() => setShowAllCustomers(s => !s)} className="text-[11px] text-blue-600 font-semibold" data-testid="monthly-report-customers-toggle">
                    {showAllCustomers ? 'Show top 20' : `Show all ${perCustomer.length}`}
                  </button>
                )}
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead className="bg-slate-50 text-slate-500 uppercase tracking-wider text-[10px]">
                    <tr>
                      <th className="px-3 py-2 text-left">Customer</th>
                      <th className="px-3 py-2 text-right">Visits</th>
                      <th className="px-3 py-2 text-left">Last Visit</th>
                      <th className="px-3 py-2 text-left">Salesmen</th>
                      <th className="px-3 py-2 text-center">Type</th>
                    </tr>
                  </thead>
                  <tbody>
                    {customersToShow.map((c, i) => (
                      <tr key={i} className="border-t border-slate-100" data-testid={`monthly-report-cust-${i}`}>
                        <td className="px-3 py-2 font-medium text-slate-800">{c.customer_name}</td>
                        <td className="px-3 py-2 text-right font-bold text-slate-700">{c.visit_count}</td>
                        <td className="px-3 py-2 text-slate-500">{c.last_visit_date || '—'}</td>
                        <td className="px-3 py-2 text-slate-500 truncate max-w-[180px]">{(c.salesmen || []).join(', ') || '—'}</td>
                        <td className="px-3 py-2 text-center">
                          {c.unplanned ? (
                            <span className="px-1.5 py-0.5 text-[9px] font-bold bg-purple-50 text-purple-700 rounded">UNPLANNED</span>
                          ) : (
                            <span className="px-1.5 py-0.5 text-[9px] font-bold bg-blue-50 text-blue-700 rounded">PLANNED</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Daily breakdown */}
          {daily.length > 0 && (
            <div className="bg-white border border-slate-200 rounded-xl overflow-hidden" data-testid="monthly-report-daily">
              <div className="px-4 py-2.5 border-b border-slate-200 bg-slate-50">
                <h4 className="text-xs font-bold text-slate-700 uppercase tracking-wider">Daily Breakdown ({daily.length} days)</h4>
              </div>
              <div className="overflow-x-auto max-h-96">
                <table className="w-full text-xs">
                  <thead className="bg-slate-50 text-slate-500 uppercase tracking-wider text-[10px] sticky top-0">
                    <tr>
                      <th className="px-3 py-2 text-left">Date</th>
                      <th className="px-3 py-2 text-left">Day</th>
                      <th className="px-3 py-2 text-right">Planned</th>
                      <th className="px-3 py-2 text-right">Visited</th>
                      <th className="px-3 py-2 text-right">Unplanned</th>
                      <th className="px-3 py-2 text-right">Coverage</th>
                    </tr>
                  </thead>
                  <tbody>
                    {daily.map((d, i) => (
                      <tr key={i} className="border-t border-slate-100" data-testid={`monthly-report-day-${i}`}>
                        <td className="px-3 py-2 font-medium text-slate-800">{d.date}</td>
                        <td className="px-3 py-2 text-slate-500">{d.day_of_week}</td>
                        <td className="px-3 py-2 text-right text-slate-600">{d.planned}</td>
                        <td className="px-3 py-2 text-right text-slate-600">{d.visited}</td>
                        <td className="px-3 py-2 text-right text-purple-600">{d.unplanned}</td>
                        <td className={`px-3 py-2 text-right font-bold ${d.coverage_pct >= 80 ? 'text-green-600' : d.coverage_pct >= 50 ? 'text-blue-600' : 'text-amber-600'}`}>{d.coverage_pct}%</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}


// Read-only renderer (used by Useradmin Beat Runs tab — no check-in allowed)
function BeatRunReadOnlyView({ runDate, salesman, companyId, hdr, embedded = false }) {
  const [run, setRun] = useState(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    setLoading(true);
    axios.get(`${API}/salesman-orders/beat-run/today?company_id=${companyId || ''}&run_date=${runDate}&salesman=${encodeURIComponent(salesman)}`, { headers: hdr() })
      .then(r => { if (r.data?.success) setRun(r.data.data); })
      .finally(() => setLoading(false));
  }, [runDate, salesman, companyId, hdr]);
  if (loading) return <div className="flex items-center justify-center h-24"><div className="w-5 h-5 border-2 border-slate-200 border-t-blue-600 rounded-full animate-spin" /></div>;
  if (!run) return <p className="text-center text-xs text-slate-400 py-6">Not found.</p>;
  const dateLabel = (() => { try { return new Date(run.run_date).toLocaleDateString('en-IN', { weekday: 'long', day: '2-digit', month: 'short', year: 'numeric' }); } catch { return run.run_date; } })();
  const visitedCount = (run.planned || []).filter(p => p.visited_at).length;
  return (
    <div className={embedded ? '' : 'space-y-3'}>
      {!embedded && (
        <div className="bg-white rounded-lg border border-slate-200 p-3 flex items-center justify-between gap-2">
          <div><h3 className="text-sm font-semibold text-slate-800">{dateLabel}</h3>
            <p className="text-[11px] text-slate-500">{run.salesman} · {run.day_of_week}</p>
          </div>
          <div className="text-right"><div className="text-lg font-bold text-blue-600">{visitedCount}/{(run.planned || []).length}</div></div>
        </div>
      )}
      <div className={embedded ? 'mt-2' : 'bg-white rounded-lg border border-slate-200 overflow-hidden'}>
        {(run.planned || []).map((p, i) => {
          const done = !!p.visited_at;
          return (
            <div key={i} className={`px-3 py-2 ${embedded ? '' : 'border-b border-slate-50 last:border-0'} flex items-center gap-2.5`}>
              <div className={`w-4 h-4 rounded-full flex items-center justify-center flex-shrink-0 ${done ? 'bg-green-500 text-white' : 'border-2 border-slate-300'}`}>
                {done && <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3"><polyline points="20 6 9 17 4 12"/></svg>}
              </div>
              <div className="min-w-0 flex-1">
                <div className={`text-xs ${done ? 'text-green-800 line-through' : 'text-slate-800'} truncate`}>{p.customer_name}</div>
                {p.visited_at && <div className="text-[9px] text-slate-500">at {new Date(p.visited_at).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', hour12: true, timeZone: 'Asia/Kolkata' })}</div>}
              </div>
            </div>
          );
        })}
        {(run.unplanned || []).length > 0 && (
          <>
            <div className="px-3 py-1 text-[9px] uppercase font-bold text-amber-700 bg-amber-50">Unplanned</div>
            {(run.unplanned || []).map((u, i) => (
              <div key={i} className="px-3 py-2 border-b border-slate-50 last:border-0 flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <div className="flex items-center gap-1.5"><span className="text-xs text-slate-800 truncate">{u.customer_name}</span>
                    <span className="text-[8px] px-1 py-0.5 rounded-full bg-amber-100 text-amber-700 font-bold">NEW</span>
                  </div>
                  {u.details && <p className="text-[10px] text-slate-500">{u.details}</p>}
                </div>
                <span className="text-[9px] text-slate-400 flex-shrink-0">{new Date(u.added_at).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', hour12: true, timeZone: 'Asia/Kolkata' })}</span>
              </div>
            ))}
          </>
        )}
      </div>
    </div>
  );
}

// ─── Beat Plans Admin Tab ────────────────────────────────────────────────
const DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

function BeatPlansAdmin({ companyId, masterList, customers }) {
  const [selSalesman, setSelSalesman] = useState('');
  const [beats, setBeats] = useState([]); // [{customer_name, day_of_week, frequency}]
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);

  // Customers mapped to the SELECTED salesman only — not the global customer list.
  // Falls back to global list when no salesman is selected (rare; UI gates it).
  const mappedCustomers = useMemo(() => {
    if (!selSalesman) return [];
    const m = (masterList || []).find(x => x.salesman_name === selSalesman);
    if (!m) return [];
    const list = m.customers || m.mapped_customers || [];
    return Array.isArray(list) && list.length > 0 ? list : (customers || []);
  }, [selSalesman, masterList, customers]);

  const hdr = useCallback(() => ({
    Authorization: `Bearer ${localStorage.getItem('flowra_token')}`,
    'X-Company-Id': companyId || '',
  }), [companyId]);

  const loadBeats = useCallback(async (sm) => {
    if (!sm) { setBeats([]); return; }
    setLoading(true);
    try {
      const r = await axios.get(`${API}/salesman-orders/beats?salesman=${encodeURIComponent(sm)}&company_id=${companyId || ''}`, { headers: hdr() });
      if (r.data.success) setBeats((r.data.data.beats || []).map(b => ({
        customer_name: b.customer_name, day_of_week: b.day_of_week, frequency: b.frequency || 'weekly',
      })));
    } catch { /* ignore */ }
    setLoading(false);
  }, [companyId, hdr]);

  useEffect(() => { loadBeats(selSalesman); }, [selSalesman, loadBeats]);

  const addRow = () => setBeats(p => [...p, { customer_name: '', day_of_week: 'Mon', frequency: 'weekly' }]);
  const updateRow = (i, key, val) => setBeats(p => p.map((b, idx) => idx === i ? { ...b, [key]: val } : b));
  const removeRow = (i) => setBeats(p => p.filter((_, idx) => idx !== i));

  const save = async () => {
    if (!selSalesman) { toast.error('Select a salesman first'); return; }
    setSaving(true);
    try {
      const r = await axios.post(`${API}/salesman-orders/beats`,
        { salesman: selSalesman, beats: beats.filter(b => b.customer_name) },
        { headers: hdr() });
      if (r.data.success) toast.success(r.data.message); else toast.error(r.data.error);
    } catch { toast.error('Save failed'); }
    setSaving(false);
  };

  // Group beats by day for visualization
  const byDay = DAYS.reduce((acc, d) => {
    acc[d] = beats.filter(b => b.day_of_week === d);
    return acc;
  }, {});

  return (
    <div className="space-y-4" data-testid="beat-plans-admin">
      <div className="bg-white border border-slate-200 rounded-xl p-3 sm:p-4">
        <div className="flex flex-col sm:flex-row sm:items-end gap-3 mb-3">
          <div className="flex-1">
            <label className="text-[11px] text-slate-500 font-semibold uppercase block mb-1">Salesman</label>
            <select value={selSalesman} onChange={e => setSelSalesman(e.target.value)}
              className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg" data-testid="beat-salesman-select">
              <option value="">— Select salesman —</option>
              {masterList.map((m, i) => <option key={i} value={m.salesman_name}>{m.salesman_name}</option>)}
            </select>
          </div>
          {selSalesman && <>
            <button onClick={addRow} className="px-3 py-2 text-xs bg-blue-50 text-blue-600 rounded-lg hover:bg-blue-100 flex items-center gap-1.5" data-testid="add-beat-btn">
              <Plus size={13} /> Add Beat
            </button>
            <button onClick={save} disabled={saving} className="px-3 py-2 text-xs bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 disabled:opacity-50 flex items-center gap-1.5" data-testid="save-beats-btn">
              <Save size={13} /> {saving ? 'Saving...' : 'Save Plan'}
            </button>
          </>}
        </div>
        {!selSalesman && <p className="text-xs text-slate-400 italic">Select a salesman to view or edit their beat plan.</p>}
        {selSalesman && mappedCustomers.length === 0 && (
          <div className="bg-amber-50 border border-amber-200 rounded-lg p-2 text-[11px] text-amber-800 mt-1" data-testid="no-mapped-customers">
            <strong>{selSalesman}</strong> has no mapped customers yet. Open the <em>Manage Salesmen</em> tab and assign customers to this salesman before creating a beat plan.
          </div>
        )}
      </div>

      {selSalesman && (loading ? (
        <div className="flex items-center justify-center h-32"><div className="w-6 h-6 border-2 border-slate-200 border-t-blue-600 rounded-full animate-spin" /></div>
      ) : (
        <>
          {/* Grid view: per-day customer mapping */}
          <div className="bg-white border border-slate-200 rounded-xl overflow-hidden">
            <div className="px-3 py-2 border-b border-slate-100"><h3 className="text-xs font-semibold text-slate-700">Weekly Plan ({beats.length} beat{beats.length !== 1 ? 's' : ''})</h3></div>
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2 p-3">
              {DAYS.map(day => (
                <div key={day} className="bg-slate-50 rounded-lg p-2 min-h-[100px]" data-testid={`day-col-${day}`}>
                  <div className="text-[10px] uppercase font-bold text-slate-600 mb-1.5">{day}</div>
                  {byDay[day].length === 0 && <p className="text-[9px] text-slate-400 italic">No visits</p>}
                  {byDay[day].map((b, i) => (
                    <div key={i} className="bg-white rounded px-1.5 py-1 text-[10px] mb-1 border border-slate-100">
                      {b.customer_name || <span className="text-slate-400 italic">(unset)</span>}
                    </div>
                  ))}
                </div>
              ))}
            </div>
          </div>

          {/* Editable rows — overflow-visible so the SearchableSelect dropdown isn't clipped */}
          <div className="bg-white border border-slate-200 rounded-xl">
            <div className="px-3 py-2 border-b border-slate-100"><h3 className="text-xs font-semibold text-slate-700">Edit Beats</h3></div>
            <div className="divide-y divide-slate-100 overflow-visible">
              {beats.length === 0 && <p className="text-xs text-slate-400 italic px-3 py-6 text-center">No beats yet. Click "Add Beat" to create one.</p>}
              {beats.map((b, i) => (
                <div key={i} className="px-3 py-2 flex flex-col sm:flex-row gap-2 items-start sm:items-center relative" data-testid={`beat-row-${i}`}>
                  <div className="flex-1 min-w-0 w-full sm:w-auto">
                    <SearchableSelect value={b.customer_name} onChange={v => updateRow(i, 'customer_name', v)}
                      options={mappedCustomers} placeholder={mappedCustomers.length ? "Select mapped customer" : "No customers mapped — open Manage tab to assign first"} />
                  </div>
                  <select value={b.day_of_week} onChange={e => updateRow(i, 'day_of_week', e.target.value)}
                    className="text-xs border border-slate-200 rounded px-2 py-1.5" data-testid={`beat-day-${i}`}>
                    {DAYS.map(d => <option key={d} value={d}>{d}</option>)}
                  </select>
                  <select value={b.frequency} onChange={e => updateRow(i, 'frequency', e.target.value)}
                    className="text-xs border border-slate-200 rounded px-2 py-1.5" data-testid={`beat-freq-${i}`}>
                    <option value="weekly">Weekly</option>
                    <option value="biweekly">Bi-weekly</option>
                    <option value="monthly">Monthly</option>
                  </select>
                  <button onClick={() => removeRow(i)} className="text-red-500 hover:bg-red-50 p-1.5 rounded" data-testid={`beat-remove-${i}`}><Trash2 size={13} /></button>
                </div>
              ))}
            </div>
          </div>
        </>
      ))}
    </div>
  );
}
