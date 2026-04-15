import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Users, Calendar, TrendingUp, AlertTriangle, CheckCircle, Target, Download, ChevronDown, ChevronUp, X, Phone, MapPin, Clock, Trash2, Plus, RotateCcw } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { toast } from 'sonner';
import SearchableSelect from '../components/SearchableSelect';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const CustomerCRM = ({ user, selectedFY, excludeBranches }) => {
  const [activeTab, setActiveTab] = useState('targets');
  const [outstanding, setOutstanding] = useState([]);
  const [followups, setFollowups] = useState([]);
  const [targets, setTargets] = useState([]);
  const [paymentBehavior, setPaymentBehavior] = useState([]);
  const [loading, setLoading] = useState(true);
  const [customerNames, setCustomerNames] = useState([]);
  const [customerGroups, setCustomerGroups] = useState([]);
  const [customerStates, setCustomerStates] = useState([]);
  const [selectedGroup, setSelectedGroup] = useState('all');
  const [showAddFollowup, setShowAddFollowup] = useState(false);
  const [showSetTarget, setShowSetTarget] = useState(null);
  const [expandedTarget, setExpandedTarget] = useState(null);
  const [exportingLedger, setExportingLedger] = useState(null);
  const [sortField, setSortField] = useState('customer_name');
  const [sortDir, setSortDir] = useState('asc');
  const [selectedForRemoval, setSelectedForRemoval] = useState([]);
  const [removedCustomers, setRemovedCustomers] = useState([]);
  const [showBulkPercentage, setShowBulkPercentage] = useState(false);
  const [bulkPct, setBulkPct] = useState(115);
  const [selectedForReactivate, setSelectedForReactivate] = useState([]);
  const [newFollowup, setNewFollowup] = useState({
    customer_name: '',
    followup_date: '',
    followup_type: 'call',
    notes: ''
  });
  const [targetForm, setTargetForm] = useState({
    customer_name: '',
    last_fy_sales: '',
    target_amount: ''
  });

  useEffect(() => {
    fetchCustomerNames();
  }, [selectedFY, excludeBranches]);

  useEffect(() => {
    fetchData();
  }, [activeTab, selectedFY, excludeBranches]);

  const fetchCustomerNames = async () => {
    try {
      const fyParam = selectedFY ? `?fy=${selectedFY}` : '';
      const res = await axios.get(`${API}/customers/outstanding${fyParam}`);
      const custs = res.data?.data?.customers || [];
      setCustomerNames(custs.map(c => c.customer_name));
      const groups = res.data?.data?.groups || [];
      const states = res.data?.data?.states || [];
      setCustomerGroups(groups);
      setCustomerStates(states);
    } catch (error) {
      console.error('Error fetching customer names:', error);
    }
  };

  const fetchData = async () => {
    setLoading(true);
    try {
      const fyParam = selectedFY ? `fy=${selectedFY}` : '';
      if (activeTab === 'outstanding') {
        const res = await axios.get(`${API}/customers/outstanding?${fyParam}`);
        setOutstanding(res.data?.data?.customers || []);
        // Also set groups from response
        const groups = res.data?.data?.groups || [];
        if (groups.length) setCustomerGroups(groups);
      } else if (activeTab === 'followups') {
        const res = await axios.get(`${API}/customers/followups`);
        setFollowups(res.data?.data?.followups || []);
      } else if (activeTab === 'targets') {
        const res = await axios.get(`${API}/customers/targets?${fyParam}`);
        setTargets(res.data?.data?.targets || []);
      } else if (activeTab === 'behavior') {
        const res = await axios.get(`${API}/customers/payment-behavior?${fyParam}`);
        setPaymentBehavior(res.data?.data?.customers || []);
      }
    } catch (error) {
      console.error('Error fetching data:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleAddFollowup = async () => {
    if (!newFollowup.customer_name) {
      toast.error('Please select a customer');
      return;
    }
    if (!newFollowup.followup_date) {
      toast.error('Please select a date');
      return;
    }
    try {
      await axios.post(`${API}/customers/followups`, newFollowup);
      toast.success('Follow-up created!');
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

  // Check if selected FY has ended
  const isFYCompleted = () => {
    if (!selectedFY) return false;
    const parts = selectedFY.split('-');
    const endShort = parseInt(parts[1]);
    const startYear = parseInt(parts[0]);
    const endYear = startYear + 1;
    const fyEndDate = new Date(endYear, 2, 31); // March 31
    return new Date() > fyEndDate;
  };

  const handleSetTarget = async () => {
    if (!targetForm.customer_name || !targetForm.target_amount) {
      toast.error('Customer name and target are required');
      return;
    }
    if (isFYCompleted()) {
      toast.error(`FY ${selectedFY} has ended. Targets cannot be modified for completed financial years.`);
      return;
    }
    try {
      const res = await axios.post(`${API}/customers/targets/set`, {
        customer_name: targetForm.customer_name,
        target_amount: parseFloat(targetForm.target_amount),
        last_fy_sales: parseFloat(targetForm.last_fy_sales) || 0,
        fy: selectedFY || ''
      });
      if (res.data?.success) {
        toast.success(`Target set for ${targetForm.customer_name}`);
        setShowSetTarget(null);
        setTargetForm({ customer_name: '', last_fy_sales: '', target_amount: '' });
        fetchData();
      } else {
        toast.error(res.data?.error || 'Failed to set target');
      }
    } catch (error) {
      toast.error(error.response?.data?.error || 'Failed to set target');
    }
  };

  const exportLedger = async (customerName) => {
    setExportingLedger(customerName);
    try {
      const response = await axios.post(
        `${API}/customers/ledger/export`,
        { customer_name: customerName, fy: selectedFY || '' },
        { responseType: 'blob' }
      );
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `ledger_${customerName.replace(/\s/g, '_')}_${selectedFY || 'all'}.pdf`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      toast.success(`Tally*-format ledger exported for ${customerName}`);
    } catch (error) {
      toast.error('Failed to export ledger');
    } finally {
      setExportingLedger(null);
    }
  };

  const exportOutstandingExcel = async (data) => {
    try {
      const response = await axios.post(`${API}/customers/outstanding/export`, { data, fy: selectedFY || '' }, { responseType: 'blob' });
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `outstanding_${selectedFY || 'all'}.xlsx`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      toast.success('Outstanding exported to Excel');
    } catch { toast.error('Export failed'); }
  };

  const exportTargetsExcel = async (data) => {
    try {
      const response = await axios.post(`${API}/customers/targets/export`, { data, fy: selectedFY || '' }, { responseType: 'blob' });
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `targets_${selectedFY || 'all'}.xlsx`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      toast.success('Targets exported to Excel');
    } catch { toast.error('Export failed'); }
  };

  const openTargetForm = (customer) => {
    setTargetForm({
      customer_name: customer.customer_name,
      last_fy_sales: customer.last_fy_sales || customer.achieved_amount || '',
      target_amount: customer.has_custom_target ? customer.target_amount : ''
    });
    setShowSetTarget(customer.customer_name);
  };

  const handleRemoveSelected = async () => {
    if (!selectedForRemoval.length) return;
    try {
      const res = await axios.post(`${API}/customers/targets/remove`, { fy: selectedFY, customer_names: selectedForRemoval });
      if (res.data?.success) {
        toast.success(`${selectedForRemoval.length} customers removed from targets`);
        setSelectedForRemoval([]);
        fetchData();
        fetchRemovedCustomers();
      }
    } catch { toast.error('Failed to remove customers'); }
  };

  const handleReactivateSelected = async () => {
    if (!selectedForReactivate.length) return;
    try {
      const res = await axios.post(`${API}/customers/targets/reactivate`, { fy: selectedFY, customer_names: selectedForReactivate });
      if (res.data?.success) {
        toast.success(`${res.data.data.reactivated} customers reactivated`);
        setSelectedForReactivate([]);
        fetchData();
        fetchRemovedCustomers();
      }
    } catch { toast.error('Failed to reactivate'); }
  };

  const handleBulkPercentage = async () => {
    try {
      const res = await axios.post(`${API}/customers/targets/bulk-percentage`, { fy: selectedFY, percentage: bulkPct });
      if (res.data?.success) {
        toast.success(res.data.data.message);
        setShowBulkPercentage(false);
        fetchData();
      }
    } catch { toast.error('Failed to set bulk targets'); }
  };

  const fetchRemovedCustomers = async () => {
    try {
      const res = await axios.get(`${API}/customers/targets/removed?fy=${selectedFY}`);
      if (res.data?.success) setRemovedCustomers(res.data.data.removed || []);
    } catch {}
  };

  useEffect(() => { fetchRemovedCustomers(); }, [selectedFY, excludeBranches]);



  const tabs = [
    { id: 'targets', label: 'Targets', icon: TrendingUp },
    { id: 'outstanding', label: 'Outstanding', icon: AlertTriangle },
    { id: 'followups', label: 'Follow-ups', icon: Calendar },
    { id: 'behavior', label: 'Payment Behavior', icon: Users }
  ];

  const getFollowupDateColor = (dateStr) => {
    const fDate = new Date(dateStr);
    const now = new Date();
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const fDay = new Date(fDate.getFullYear(), fDate.getMonth(), fDate.getDate());
    if (fDay < today) return 'text-red-600 bg-red-50 border-red-200';
    if (fDay.getTime() === today.getTime()) return 'text-amber-600 bg-amber-50 border-amber-200';
    return 'text-slate-600 bg-slate-50 border-slate-200';
  };

  return (
    <div data-testid="crm-page">
      <div className="mb-6">
        <h1 className="text-2xl sm:text-4xl font-light tracking-tight text-slate-900" style={{ fontFamily: 'Outfit, sans-serif' }}>
          Customer CRM
        </h1>
        <p className="mt-1 text-sm text-slate-600">Manage customers, targets, follow-ups, and export ledgers</p>
      </div>

      <div className="bg-white border border-slate-200 rounded-xl p-1.5 sm:p-2 mb-6 flex gap-1.5 sm:gap-2 overflow-x-auto">
        {tabs.map(tab => {
          const Icon = tab.icon;
          return (
            <button
              key={tab.id}
              data-testid={`tab-${tab.id}`}
              onClick={() => setActiveTab(tab.id)}
              className={`flex-1 min-w-[80px] flex items-center justify-center gap-1.5 px-2 sm:px-4 py-2.5 sm:py-3 rounded-lg transition-all ${
                activeTab === tab.id ? 'bg-[#2563EB] text-white' : 'text-slate-600 hover:bg-slate-50'
              }`}
            >
              <Icon size={16} />
              <span className="text-xs sm:text-sm font-medium text-center leading-tight sm:whitespace-nowrap">{tab.label}</span>
            </button>
          );
        })}
      </div>

      {/* Customer Group / State Filter */}
      {(customerGroups.length > 0 || customerStates.length > 0) && (activeTab === 'outstanding' || activeTab === 'targets') && (
        <div className="mb-4">
          <select
            value={selectedGroup}
            onChange={(e) => setSelectedGroup(e.target.value)}
            className="px-4 py-2 border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-[#2563EB] focus:border-transparent"
            data-testid="customer-group-filter"
          >
            <option value="all">All Customers</option>
            {customerGroups.length > 1 && (
              <optgroup label="Ledger Group">
                {[...customerGroups].sort((a, b) => a.localeCompare(b, 'en', { sensitivity: 'base' })).map(g => <option key={`grp-${g}`} value={`group:${g}`}>{g}</option>)}
              </optgroup>
            )}
            {customerStates.length > 0 && (
              <optgroup label="State / Region">
                {[...customerStates].sort((a, b) => a.localeCompare(b, 'en', { sensitivity: 'base' })).map(s => <option key={`st-${s}`} value={`state:${s}`}>{s}</option>)}
              </optgroup>
            )}
          </select>
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center h-64"><div className="loading-spinner" /></div>
      ) : (
        <>
          {/* Outstanding Payments - Proper Aging */}
          {activeTab === 'outstanding' && (() => {
            const handleSort = (field) => {
              if (sortField === field) setSortDir(sortDir === 'asc' ? 'desc' : 'asc');
              else { setSortField(field); setSortDir('desc'); }
            };
            const SortTh = ({ field, label, className = '' }) => (
              <th className={`cursor-pointer select-none hover:bg-slate-50 ${className}`} onClick={() => handleSort(field)} data-testid={`sort-crm-${field}`}>
                <span className="flex items-center gap-1">{label} {sortField === field ? (sortDir === 'asc' ? '↑' : '↓') : ''}</span>
              </th>
            );
            const sorted = outstanding
              .filter(c => {
                if (selectedGroup === 'all') return true;
                if (selectedGroup.startsWith('group:')) return c.ledger_group === selectedGroup.slice(6);
                if (selectedGroup.startsWith('state:')) return c.state === selectedGroup.slice(6);
                return c.ledger_group === selectedGroup;
              })
              .sort((a, b) => {
                const dir = sortDir === 'asc' ? 1 : -1;
                if (sortField === 'customer_name') return dir * (a.customer_name || '').localeCompare(b.customer_name || '');
                return dir * ((a[sortField] || 0) - (b[sortField] || 0));
              });
            return (
            <div>
              <div className="flex justify-end mb-3">
                <button onClick={() => exportOutstandingExcel(sorted)} className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white rounded-lg text-sm font-medium hover:bg-green-700" data-testid="export-outstanding-excel">
                  <Download size={14} /> Export Excel
                </button>
              </div>
            <div className="bg-white border border-slate-200 rounded-xl overflow-x-auto">
                <table className="data-table min-w-[700px]" data-testid="outstanding-table">
                  <thead>
                    <tr>
                      <SortTh field="customer_name" label="Customer Name" />
                      <th>Group</th>
                      <SortTh field="opening_balance" label="Opening Bal" className="numeric" />
                      <SortTh field="total_sales" label="Total Sales" className="numeric" />
                      <SortTh field="paid_amount" label="Paid" className="numeric" />
                      <SortTh field="outstanding_amount" label="Outstanding" className="numeric" />
                      <th className="numeric">0-30d</th>
                      <th className="numeric">30-60d</th>
                      <th className="numeric">60-90d</th>
                      <th className="numeric">90+d</th>
                      <th>Status</th>
                      <th>Ledger</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sorted.map((customer, idx) => {
                        const statusColors = {
                          normal: 'bg-green-100 text-green-700',
                          at_risk: 'bg-amber-100 text-amber-700',
                          overdue: 'bg-orange-100 text-orange-700',
                          critical: 'bg-red-100 text-red-700'
                        };
                        return (
                      <tr key={idx}>
                        <td className="font-medium text-slate-900">{customer.customer_name}</td>
                        <td className="text-slate-500 text-xs">{customer.ledger_group || '-'}</td>
                        <td className="numeric text-slate-500">
                          {(customer.opening_balance || 0) !== 0 ? `Rs.${(customer.opening_balance || 0).toLocaleString('en-IN', {maximumFractionDigits: 0})}` : '-'}
                        </td>
                        <td className="numeric text-slate-600">
                          Rs.{(customer.total_sales || 0).toLocaleString('en-IN', {maximumFractionDigits: 0})}
                        </td>
                        <td className="numeric text-emerald-600">
                          Rs.{(customer.paid_amount || 0).toLocaleString('en-IN', {maximumFractionDigits: 0})}
                        </td>
                        <td className="numeric font-semibold text-[#2563EB]">
                          Rs.{(customer.outstanding_amount || 0).toLocaleString('en-IN', {maximumFractionDigits: 0})}
                        </td>
                        <td className="numeric">Rs.{(customer.aging_0_30 || 0).toLocaleString('en-IN', {maximumFractionDigits: 0})}</td>
                        <td className="numeric">Rs.{(customer.aging_30_60 || 0).toLocaleString('en-IN', {maximumFractionDigits: 0})}</td>
                        <td className="numeric text-orange-600">Rs.{(customer.aging_60_90 || 0).toLocaleString('en-IN', {maximumFractionDigits: 0})}</td>
                        <td className="numeric text-red-600 font-medium">Rs.{(customer.aging_90_plus || 0).toLocaleString('en-IN', {maximumFractionDigits: 0})}</td>
                        <td>
                          <span className={`px-3 py-1 rounded-full text-xs font-medium ${statusColors[customer.status] || statusColors.normal}`}>
                            {customer.status_label || 'Normal'}
                          </span>
                        </td>
                        <td>
                          <button
                            onClick={() => exportLedger(customer.customer_name)}
                            disabled={exportingLedger === customer.customer_name}
                            className="px-3 py-1.5 text-xs rounded-lg bg-[#2563EB] text-white hover:bg-[#1D4ED8] disabled:opacity-50 flex items-center gap-1.5"
                            data-testid={`export-ledger-pdf-${idx}`}
                          >
                            {exportingLedger === customer.customer_name ? 'Exporting...' : 'Ledger PDF'}
                          </button>
                        </td>
                      </tr>
                        );
                    })}
                  </tbody>
                </table>
            </div>
            </div>
            );
          })()}

          {/* Follow-ups with Customer Dropdown */}
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
                <div className="bg-white border border-slate-200 rounded-xl p-3 sm:p-6 mb-6">
                  <div className="flex items-center justify-between mb-4">
                    <h3 className="text-lg font-medium">New Follow-up</h3>
                    <button onClick={() => setShowAddFollowup(false)} className="text-slate-400 hover:text-slate-600"><X size={18} /></button>
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <SearchableSelect
                      options={customerNames}
                      value={newFollowup.customer_name}
                      onChange={(val) => setNewFollowup({...newFollowup, customer_name: val})}
                      placeholder="Select Customer"
                      testId="followup-customer-select"
                    />
                    <input
                      type="datetime-local"
                      value={newFollowup.followup_date}
                      onChange={(e) => setNewFollowup({...newFollowup, followup_date: e.target.value})}
                      className="px-4 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#2563EB]"
                      data-testid="followup-date-input"
                    />
                    <select
                      value={newFollowup.followup_type}
                      onChange={(e) => setNewFollowup({...newFollowup, followup_type: e.target.value})}
                      className="px-4 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#2563EB]"
                      data-testid="followup-type-select"
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
                      className="px-4 py-2 border border-slate-200 rounded-lg col-span-1 sm:col-span-2 focus:outline-none focus:ring-2 focus:ring-[#2563EB]"
                      rows="3"
                      data-testid="followup-notes-input"
                    />
                  </div>
                  <div className="flex gap-2 mt-4">
                    <button onClick={handleAddFollowup} className="btn-primary" data-testid="save-followup-button">Save Follow-up</button>
                    <button onClick={() => setShowAddFollowup(false)} className="btn-secondary">Cancel</button>
                  </div>
                </div>
              )}

              <div className="grid grid-cols-1 gap-4">
                {followups.length === 0 && (
                  <div className="text-center py-12 text-slate-500">No follow-ups yet. Add one to get started.</div>
                )}
                {followups.map((followup, idx) => (
                  <div key={idx} className={`bg-white border rounded-xl p-6 ${getFollowupDateColor(followup.followup_date)}`}>
                    <div className="flex items-center justify-between">
                      <div className="flex-1">
                        <div className="flex items-center gap-3">
                          <h3 className="text-lg font-medium text-slate-900">{followup.customer_name}</h3>
                          {followup.followup_date && new Date(followup.followup_date) < new Date() && followup.status === 'pending' && (
                            <span className="px-2 py-0.5 rounded text-xs font-bold bg-red-600 text-white">OVERDUE</span>
                          )}
                        </div>
                        <div className="flex items-center gap-4 mt-2 text-sm text-slate-600">
                          <span className="flex items-center gap-1">
                            <Calendar size={14} />
                            {(() => { const r = followup.followup_date; const d = (r && (r.includes('+') || r.includes('Z'))) ? new Date(r) : new Date(r + 'Z'); return d.toLocaleString('en-IN', { timeZone: 'Asia/Kolkata' }); })()}
                          </span>
                          <span className="capitalize px-2 py-0.5 rounded bg-slate-100 text-slate-700 text-xs">{followup.followup_type}</span>
                          {followup.created_by_name && (
                            <span className="text-xs text-slate-400">by {followup.created_by_name}</span>
                          )}
                        </div>
                        {followup.notes && <p className="mt-2 text-sm text-slate-700">{followup.notes}</p>}
                      </div>
                      <div className="flex gap-2">
                        {followup.status === 'pending' && (
                          <button
                            onClick={() => updateFollowupStatus(followup.id, 'completed')}
                            className="btn-primary text-sm"
                            data-testid={`complete-followup-${idx}`}
                          >
                            Mark Complete
                          </button>
                        )}
                        {followup.status === 'completed' && (
                          <span className="px-3 py-1 rounded-full text-xs font-medium bg-green-100 text-green-700 flex items-center gap-1">
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

          {/* Targets with Set Target & Monthly Sales */}
          {activeTab === 'targets' && (
            <div>
              <div className="flex flex-wrap items-center gap-2 mb-3">
                {!isFYCompleted() && (
                  <>
                    {selectedForRemoval.length > 0 && (
                      <button onClick={handleRemoveSelected} className="flex items-center gap-1.5 px-3 py-2 bg-red-600 text-white rounded-lg text-sm font-medium hover:bg-red-700" data-testid="remove-selected-btn">
                        <Trash2 size={14} /> Remove {selectedForRemoval.length} Selected
                      </button>
                    )}
                    <button onClick={() => setShowBulkPercentage(true)} className="flex items-center gap-1.5 px-3 py-2 border border-[#2563EB] text-[#2563EB] rounded-lg text-sm font-medium hover:bg-blue-50" data-testid="bulk-pct-btn">
                      <TrendingUp size={14} /> Bulk % Target
                    </button>
                  </>
                )}
                <div className="flex-1" />
                <button onClick={() => exportTargetsExcel(targets)} className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white rounded-lg text-sm font-medium hover:bg-green-700" data-testid="export-targets-excel">
                  <Download size={14} /> Export Excel
                </button>
              </div>
              <div className="bg-white border border-slate-200 rounded-xl overflow-x-auto">
                  <table className="data-table min-w-[800px]" data-testid="targets-table">
                    <thead>
                      <tr>
                        {!isFYCompleted() && <th className="w-10"><input type="checkbox" checked={selectedForRemoval.length === targets.length && targets.length > 0} onChange={(e) => setSelectedForRemoval(e.target.checked ? targets.map(t => t.customer_name) : [])} /></th>}
                        <th>Customer Name</th>
                        <th className="numeric">Prev FY Sales{targets[0]?.previous_fy ? ` (${targets[0].previous_fy})` : ''}</th>
                        <th className="numeric">Target</th>
                        <th className="numeric">Current FY Achieved{targets[0]?.current_fy ? ` (${targets[0].current_fy})` : ''}</th>
                        <th className="numeric">Achievement %</th>
                        <th className="numeric">Remaining</th>
                        <th>Status</th>
                        <th>Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {targets.map((target, idx) => (
                        <React.Fragment key={idx}>
                          <tr>
                            {!isFYCompleted() && (
                              <td><input type="checkbox" checked={selectedForRemoval.includes(target.customer_name)} onChange={(e) => {
                                if (e.target.checked) setSelectedForRemoval(prev => [...prev, target.customer_name]);
                                else setSelectedForRemoval(prev => prev.filter(n => n !== target.customer_name));
                              }} /></td>
                            )}
                            <td className="font-medium text-slate-900">
                              <div className="flex items-center gap-2">
                                {target.customer_name}
                                {target.has_custom_target && (
                                  <span className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-green-100 text-green-700">Custom</span>
                                )}
                              </div>
                            </td>
                            <td className="numeric text-slate-500">Rs.{(target.last_fy_sales || 0).toLocaleString('en-IN', {maximumFractionDigits: 0})}</td>
                            <td className="numeric font-medium">Rs.{target.target_amount.toLocaleString('en-IN', {maximumFractionDigits: 0})}</td>
                            <td className="numeric font-semibold text-[#2563EB]">Rs.{target.achieved_amount.toLocaleString('en-IN', {maximumFractionDigits: 0})}</td>
                            <td className="numeric">
                              <div className="flex items-center gap-2">
                                <div className="flex-1 h-2 bg-slate-200 rounded-full overflow-hidden max-w-[80px]">
                                  <div
                                    className={`h-full ${target.achievement_percentage >= 100 ? 'bg-green-500' : 'bg-[#2563EB]'}`}
                                    style={{ width: `${Math.min(target.achievement_percentage, 100)}%` }}
                                  />
                                </div>
                                <span className="text-sm font-medium">{target.achievement_percentage.toFixed(1)}%</span>
                              </div>
                            </td>
                            <td className="numeric">Rs.{target.remaining.toLocaleString('en-IN', {maximumFractionDigits: 0})}</td>
                            <td>
                              {target.achievement_percentage >= 100 ? (
                                <span className="px-3 py-1 rounded-full text-xs font-medium bg-green-100 text-green-700">Achieved</span>
                              ) : target.achievement_percentage >= 75 ? (
                                <span className="px-3 py-1 rounded-full text-xs font-medium bg-yellow-100 text-yellow-700">On Track</span>
                              ) : (
                                <span className="px-3 py-1 rounded-full text-xs font-medium bg-red-100 text-red-700">Behind</span>
                              )}
                            </td>
                            <td>
                              <div className="flex gap-1">
                                <button
                                  onClick={() => openTargetForm(target)}
                                  className={`px-2 py-1 text-xs rounded ${isFYCompleted() ? 'bg-slate-300 text-slate-500 cursor-not-allowed' : 'bg-[#2563EB] text-white hover:bg-[#1D4ED8]'}`}
                                  disabled={isFYCompleted()}
                                  data-testid={`set-target-${idx}`}
                                  title={isFYCompleted() ? `FY ${selectedFY} has ended` : 'Set Target'}
                                >
                                  <Target size={12} className="inline mr-1" />{isFYCompleted() ? 'Locked' : 'Set Target'}
                                </button>
                                <button
                                  onClick={() => setExpandedTarget(expandedTarget === idx ? null : idx)}
                                  className="px-2 py-1 text-xs rounded border border-slate-300 text-slate-600 hover:bg-slate-50"
                                  data-testid={`monthly-sales-${idx}`}
                                >
                                  {expandedTarget === idx ? <ChevronUp size={12} className="inline" /> : <ChevronDown size={12} className="inline" />}
                                  Monthly
                                </button>
                              </div>
                            </td>
                          </tr>
                          {expandedTarget === idx && target.monthly_sales?.length > 0 && (
                            <tr>
                              <td colSpan="8" className="!p-4 bg-slate-50">
                                <div className="text-sm font-medium text-slate-700 mb-3">Monthly Sales for {target.customer_name}</div>
                                <ResponsiveContainer width="100%" height={200}>
                                  <BarChart data={target.monthly_sales}>
                                    <CartesianGrid strokeDasharray="3 3" stroke="#E0E7FF" />
                                    <XAxis dataKey="month" stroke="#64748B" style={{ fontSize: '11px' }} />
                                    <YAxis stroke="#64748B" style={{ fontSize: '11px' }} />
                                    <Tooltip
                                      contentStyle={{ background: 'white', border: '1px solid #E0E7FF', borderRadius: '8px' }}
                                      formatter={(val) => [`Rs.${val.toLocaleString('en-IN')}`, 'Sales']}
                                    />
                                    <Bar dataKey="amount" fill="#2563EB" radius={[4, 4, 0, 0]} />
                                  </BarChart>
                                </ResponsiveContainer>
                                <div className="mt-2 grid grid-cols-3 md:grid-cols-6 gap-2">
                                  {target.monthly_sales.map((m, mi) => (
                                    <div key={mi} className="text-center p-2 bg-white rounded border border-slate-200">
                                      <div className="text-xs text-slate-500">{m.month}</div>
                                      <div className="text-sm font-semibold text-[#2563EB]">Rs.{m.amount.toLocaleString('en-IN', {maximumFractionDigits: 0})}</div>
                                    </div>
                                  ))}
                                </div>
                              </td>
                            </tr>
                          )}
                        </React.Fragment>
                      ))}
                    </tbody>
                  </table>
              </div>

              {/* Set Target Modal */}
              {showSetTarget && (
                <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-6 z-50" onClick={() => setShowSetTarget(null)}>
                  <div className="bg-white rounded-xl max-w-md w-full" onClick={(e) => e.stopPropagation()}>
                    <div className="border-b border-slate-200 p-6 flex items-center justify-between">
                      <h2 className="text-xl font-semibold text-slate-900" style={{ fontFamily: 'Outfit, sans-serif' }}>
                        Set Target: {targetForm.customer_name}
                      </h2>
                      <button onClick={() => setShowSetTarget(null)} className="text-slate-400 hover:text-slate-600"><X size={20} /></button>
                    </div>
                    <div className="p-6 space-y-4">
                      <div>
                        <label className="block text-sm font-medium text-slate-700 mb-1">Last Financial Year Sales (Rs.)</label>
                        <input
                          type="number"
                          value={targetForm.last_fy_sales}
                          readOnly
                          className="w-full px-4 py-2 border border-slate-200 rounded-lg bg-slate-50 text-slate-500 cursor-not-allowed"
                          data-testid="last-fy-sales-input"
                        />
                        <p className="text-xs text-slate-400 mt-1">Previous FY actual sales (read-only from Tally* data)</p>
                      </div>
                      <div>
                        <label className="block text-sm font-medium text-slate-700 mb-1">Target Amount (Rs.)</label>
                        <input
                          type="number"
                          value={targetForm.target_amount}
                          onChange={(e) => setTargetForm({...targetForm, target_amount: e.target.value})}
                          className="w-full px-4 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#2563EB]"
                          placeholder="Target for this FY"
                          data-testid="target-amount-input"
                        />
                      </div>
                      <div className="flex gap-3 pt-2">
                        <button onClick={handleSetTarget} className="flex-1 btn-primary py-3" data-testid="save-target-button">
                          Save Target
                        </button>
                        <button onClick={() => setShowSetTarget(null)} className="flex-1 btn-secondary py-3">Cancel</button>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* Bulk Percentage Modal */}
              {showBulkPercentage && (
                <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-6 z-50" onClick={() => setShowBulkPercentage(false)}>
                  <div className="bg-white rounded-xl max-w-sm w-full p-6" onClick={(e) => e.stopPropagation()}>
                    <h2 className="text-lg font-semibold text-slate-900 mb-4">Bulk Set Target Percentage</h2>
                    <p className="text-sm text-slate-500 mb-4">Set target for all customers as a percentage of their previous FY sales.</p>
                    <div className="mb-4">
                      <label className="block text-sm font-medium text-slate-700 mb-1">Target Percentage (%)</label>
                      <input type="number" value={bulkPct} onChange={(e) => setBulkPct(Number(e.target.value))}
                        className="w-full px-4 py-2.5 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#2563EB]"
                        placeholder="e.g. 115 for 15% growth" data-testid="bulk-pct-input" />
                      <p className="text-xs text-slate-400 mt-1">Example: 120 = 20% growth over previous FY</p>
                    </div>
                    <div className="flex gap-3">
                      <button onClick={() => setShowBulkPercentage(false)} className="flex-1 px-4 py-2.5 border border-slate-200 rounded-lg text-sm font-medium text-slate-600">Cancel</button>
                      <button onClick={handleBulkPercentage} className="flex-1 px-4 py-2.5 bg-[#2563EB] text-white rounded-lg text-sm font-medium hover:bg-[#1D4ED8]" data-testid="apply-bulk-pct-btn">Apply to All</button>
                    </div>
                  </div>
                </div>
              )}

              {/* Removed Customers Section */}
              {!isFYCompleted() && removedCustomers.length > 0 && (
                <div className="mt-6 bg-slate-50 border border-slate-200 rounded-xl p-4" data-testid="removed-customers-section">
                  <div className="flex items-center justify-between mb-3">
                    <h3 className="text-sm font-semibold text-slate-700">Removed Customers ({removedCustomers.length})</h3>
                    {selectedForReactivate.length > 0 && (
                      <button onClick={handleReactivateSelected} className="flex items-center gap-1.5 px-3 py-1.5 bg-green-600 text-white rounded-lg text-xs font-medium hover:bg-green-700" data-testid="reactivate-btn">
                        <Plus size={12} /> Reactivate {selectedForReactivate.length} Selected
                      </button>
                    )}
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {removedCustomers.map((rc, i) => (
                      <label key={i} className="flex items-center gap-2 px-3 py-1.5 bg-white border border-slate-200 rounded-lg cursor-pointer hover:border-green-300">
                        <input type="checkbox" checked={selectedForReactivate.includes(rc.customer_name)} onChange={(e) => {
                          if (e.target.checked) setSelectedForReactivate(prev => [...prev, rc.customer_name]);
                          else setSelectedForReactivate(prev => prev.filter(n => n !== rc.customer_name));
                        }} />
                        <span className="text-sm text-slate-600">{rc.customer_name}</span>
                      </label>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Payment Behavior */}
          {activeTab === 'behavior' && (
            <PaymentBehaviorTab paymentBehavior={paymentBehavior} />
          )}
        </>
      )}
    </div>
  );
};

const PATTERN_STYLES = {
  excellent: 'bg-green-100 text-green-700',
  regular: 'bg-blue-100 text-blue-700',
  irregular: 'bg-yellow-100 text-yellow-700',
  risky: 'bg-red-100 text-red-700',
  no_transactions: 'bg-slate-100 text-slate-500',
};

const fmtRs = (v) => `Rs.${(v || 0).toLocaleString('en-IN', { maximumFractionDigits: 0 })}`;

const PaymentBehaviorTab = ({ paymentBehavior }) => {
  const [expanded, setExpanded] = useState(null);
  const [filterPattern, setFilterPattern] = useState('all');
  const [searchTerm, setSearchTerm] = useState('');
  const [sortBy, setSortBy] = useState('credit_score');
  const [sortDir, setSortDir] = useState('desc');

  const toggleSort = (field) => {
    if (sortBy === field) setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    else { setSortBy(field); setSortDir('desc'); }
  };

  const filtered = paymentBehavior
    .filter(c => filterPattern === 'all' || c.payment_pattern === filterPattern)
    .filter(c => !searchTerm || (c.customer_name || '').toLowerCase().includes(searchTerm.toLowerCase()))
    .sort((a, b) => {
      const av = a[sortBy] ?? 0, bv = b[sortBy] ?? 0;
      return sortDir === 'asc' ? (av > bv ? 1 : -1) : (av < bv ? 1 : -1);
    });

  const summary = {
    total: paymentBehavior.length,
    excellent: paymentBehavior.filter(c => c.payment_pattern === 'excellent').length,
    regular: paymentBehavior.filter(c => c.payment_pattern === 'regular').length,
    irregular: paymentBehavior.filter(c => c.payment_pattern === 'irregular').length,
    risky: paymentBehavior.filter(c => c.payment_pattern === 'risky').length,
    avgScore: paymentBehavior.length > 0 ? (paymentBehavior.reduce((s, c) => s + (c.credit_score || 0), 0) / paymentBehavior.length).toFixed(0) : 0,
  };

  return (
    <div data-testid="payment-behavior-section">
      {/* Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-6 gap-3 mb-5">
        {[
          { label: 'Total', count: summary.total, cls: 'bg-white border-slate-200', textCls: 'text-slate-900' },
          { label: 'Excellent', count: summary.excellent, cls: 'bg-green-50 border-green-200', textCls: 'text-green-700' },
          { label: 'Regular', count: summary.regular, cls: 'bg-blue-50 border-blue-200', textCls: 'text-blue-700' },
          { label: 'Irregular', count: summary.irregular, cls: 'bg-yellow-50 border-yellow-200', textCls: 'text-yellow-700' },
          { label: 'Risky', count: summary.risky, cls: 'bg-red-50 border-red-200', textCls: 'text-red-700' },
          { label: 'Avg Score', count: summary.avgScore, cls: 'bg-indigo-50 border-indigo-200', textCls: 'text-indigo-700' },
        ].map(({ label, count, cls, textCls }) => (
          <button key={label} onClick={() => setFilterPattern(label === 'Total' || label === 'Avg Score' ? 'all' : label.toLowerCase())}
            className={`border rounded-xl p-3 text-center transition-all ${cls} ${filterPattern === label.toLowerCase() ? 'ring-2 ring-blue-300' : ''}`}
            data-testid={`behavior-summary-${label.toLowerCase()}`}>
            <div className={`text-xs ${textCls} mb-0.5`}>{label}</div>
            <div className={`text-lg font-bold ${textCls}`}>{count}</div>
          </button>
        ))}
      </div>

      {/* Search + Filter */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center gap-3 mb-4">
        <input
          type="text" value={searchTerm} onChange={e => setSearchTerm(e.target.value)}
          placeholder="Search customer..."
          className="flex-1 px-4 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#2563EB]"
          data-testid="behavior-search"
        />
        {filterPattern !== 'all' && (
          <button onClick={() => setFilterPattern('all')} className="px-3 py-2 text-xs bg-slate-100 rounded-lg hover:bg-slate-200 flex items-center gap-1">
            <X size={12} /> Clear Filter
          </button>
        )}
        <span className="text-xs text-slate-400">{filtered.length} customers</span>
      </div>

      <p className="text-xs text-slate-400 mb-4">Payment behavior is calculated for the selected financial year. Opening balance carries forward from prior FYs. Click a row for detailed breakdown.</p>

      {/* Table */}
      <div className="bg-white border border-slate-200 rounded-xl overflow-x-auto">
          <table className="data-table min-w-[900px]" data-testid="payment-behavior-table">
            <thead>
              <tr>
                <th className="cursor-pointer" onClick={() => toggleSort('customer_name')}>Customer {sortBy === 'customer_name' ? (sortDir === 'asc' ? '↑' : '↓') : ''}</th>
                <th className="numeric cursor-pointer" onClick={() => toggleSort('total_amount')}>Sales {sortBy === 'total_amount' ? (sortDir === 'asc' ? '↑' : '↓') : ''}</th>
                <th className="numeric cursor-pointer" onClick={() => toggleSort('paid_amount')}>Receipts</th>
                <th className="numeric cursor-pointer" onClick={() => toggleSort('outstanding_amount')}>Outstanding {sortBy === 'outstanding_amount' ? (sortDir === 'asc' ? '↑' : '↓') : ''}</th>
                <th className="numeric cursor-pointer" onClick={() => toggleSort('payment_ratio')}>Pay Ratio</th>
                <th className="numeric cursor-pointer" onClick={() => toggleSort('average_payment_delay')}>Avg Delay</th>
                <th className="numeric cursor-pointer" onClick={() => toggleSort('credit_score')}>Score {sortBy === 'credit_score' ? (sortDir === 'asc' ? '↑' : '↓') : ''}</th>
                <th>Pattern</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((c, idx) => (
                <React.Fragment key={idx}>
                  <tr className="cursor-pointer hover:bg-blue-50/30" onClick={() => setExpanded(expanded === idx ? null : idx)} data-testid={`behavior-row-${idx}`}>
                    <td className="font-medium text-slate-900">
                      <div className="flex items-center gap-2">
                        <span className="text-slate-400 flex-shrink-0">{expanded === idx ? <ChevronUp size={14} /> : <ChevronDown size={14} />}</span>
                        <div>
                          <div>{c.customer_name}</div>
                          <div className="text-xs text-slate-400">{c.total_transactions} txns &middot; {c.relationship_months || 0}mo</div>
                        </div>
                      </div>
                    </td>
                    <td className="numeric">{fmtRs(c.total_amount)}</td>
                    <td className="numeric text-emerald-600">{fmtRs(c.paid_amount)}</td>
                    <td className="numeric text-red-600 font-medium">{fmtRs(c.outstanding_amount)}</td>
                    <td className="numeric">
                      <div className="flex items-center gap-1">
                        <div className="w-12 h-1.5 bg-slate-200 rounded-full overflow-hidden">
                          <div className={`h-full ${c.payment_ratio >= 80 ? 'bg-green-500' : c.payment_ratio >= 50 ? 'bg-yellow-500' : 'bg-red-500'}`}
                            style={{ width: `${Math.min(c.payment_ratio, 100)}%` }} />
                        </div>
                        <span className="text-xs">{c.payment_ratio}%</span>
                      </div>
                    </td>
                    <td className="numeric">{c.average_payment_delay || 0}d</td>
                    <td className="numeric font-semibold text-[#2563EB]">{(c.credit_score || 0).toFixed(0)}</td>
                    <td><span className={`px-2 py-1 rounded-full text-xs font-medium ${PATTERN_STYLES[c.payment_pattern] || 'bg-slate-100 text-slate-500'}`}>{c.payment_pattern}</span></td>
                  </tr>
                  {expanded === idx && (
                    <tr>
                      <td colSpan="8" className="p-0">
                        <CustomerPaymentDetail customer={c} />
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              ))}
            </tbody>
          </table>
      </div>
    </div>
  );
};

const CustomerPaymentDetail = ({ customer: c }) => {
  const timeline = c.monthly_timeline || [];
  const topOverdue = c.top_overdue_invoices || [];
  const totalCredits = (c.paid_amount || 0) + (c.credit_note_total || 0) + (c.journal_credit || 0);
  const openingBal = c.opening_balance || 0;

  return (
    <div className="bg-slate-50 border-t border-slate-200 p-5" data-testid={`behavior-detail-${c.customer_name}`}>
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        {/* Left: Financial Breakdown */}
        <div className="space-y-4">
          <h4 className="text-sm font-semibold text-slate-700">Financial Breakdown</h4>
          <div className="space-y-2">
            {[
              { label: 'Opening Balance', value: openingBal, color: openingBal > 0 ? 'text-orange-600' : 'text-slate-500' },
              { label: 'Total Sales (FY)', value: c.total_amount, color: 'text-slate-800' },
              { label: 'Total Debits', value: openingBal + (c.total_amount || 0), color: 'text-slate-900', bold: true },
              { label: 'Receipts (Cash/Bank)', value: c.paid_amount, color: 'text-emerald-600' },
              { label: 'Credit Notes', value: c.credit_note_total, color: 'text-purple-600' },
              { label: 'Journal Credits', value: c.journal_credit, color: 'text-indigo-600' },
              { label: 'Total Credits', value: totalCredits, color: 'text-green-700', bold: true },
              { label: 'Closing Balance', value: c.outstanding_amount, color: (c.outstanding_amount || 0) > 0 ? 'text-red-600' : 'text-green-600', bold: true },
            ].map(({ label, value, color, bold }) => (
              <div key={label} className="flex items-center justify-between">
                <span className={`text-xs ${bold ? 'font-semibold' : ''} text-slate-600`}>{label}</span>
                <span className={`text-sm ${bold ? 'font-bold' : 'font-medium'} ${color}`}>{fmtRs(value)}</span>
              </div>
            ))}
          </div>
          <div className="border-t border-slate-200 pt-3 space-y-1.5">
            {c.phone && <div className="flex items-center gap-2 text-xs text-slate-500"><Phone size={11} /> {c.phone}</div>}
            {c.state && <div className="flex items-center gap-2 text-xs text-slate-500"><MapPin size={11} /> {c.state}</div>}
            {c.first_transaction && <div className="flex items-center gap-2 text-xs text-slate-500"><Clock size={11} /> Since {c.first_transaction}</div>}
          </div>
          {/* Score Gauge */}
          <div className="p-3 rounded-lg bg-white border border-slate-200">
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-xs font-medium text-slate-600">Credit Score</span>
              <span className={`text-lg font-bold ${c.credit_score >= 80 ? 'text-green-600' : c.credit_score >= 50 ? 'text-yellow-600' : 'text-red-600'}`}>{(c.credit_score || 0).toFixed(0)}/100</span>
            </div>
            <div className="w-full h-2 bg-slate-200 rounded-full overflow-hidden">
              <div className={`h-full rounded-full transition-all ${c.credit_score >= 80 ? 'bg-green-500' : c.credit_score >= 50 ? 'bg-yellow-500' : 'bg-red-500'}`}
                style={{ width: `${Math.min(c.credit_score || 0, 100)}%` }} />
            </div>
          </div>
        </div>

        {/* Center: Monthly Payment Timeline Chart */}
        <div>
          <h4 className="text-sm font-semibold text-slate-700 mb-3">Monthly Payment Timeline</h4>
          {timeline.length > 0 ? (
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={timeline}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="month" tick={{ fontSize: 10 }} tickFormatter={m => m.slice(5)} />
                <YAxis tick={{ fontSize: 10 }} tickFormatter={v => v >= 1000 ? `${(v/1000).toFixed(0)}K` : v} />
                <Tooltip formatter={(v) => fmtRs(v)} labelFormatter={l => `Month: ${l}`} />
                <Bar dataKey="invoiced" fill="#64748b" name="Invoiced" radius={[2, 2, 0, 0]} />
                <Bar dataKey="received" fill="#22c55e" name="Received" radius={[2, 2, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-[200px] flex items-center justify-center text-sm text-slate-400">No monthly data available</div>
          )}
        </div>

        {/* Right: Top Overdue Invoices & Payment Gap */}
        <div className="space-y-4">
          <h4 className="text-sm font-semibold text-slate-700">Payment Gap Analysis</h4>
          <div className="grid grid-cols-2 gap-2">
            <div className="p-3 rounded-lg bg-white border border-slate-200">
              <div className="text-xs text-slate-500">Avg Delay</div>
              <div className={`text-lg font-bold ${(c.average_payment_delay || 0) > 30 ? 'text-red-600' : 'text-slate-800'}`}>{c.average_payment_delay || 0} days</div>
            </div>
            <div className="p-3 rounded-lg bg-white border border-slate-200">
              <div className="text-xs text-slate-500">Oldest Invoice</div>
              <div className={`text-lg font-bold ${(c.oldest_invoice_days || 0) > 90 ? 'text-red-600' : 'text-slate-800'}`}>{c.oldest_invoice_days || 0}d</div>
            </div>
            <div className="p-3 rounded-lg bg-white border border-slate-200">
              <div className="text-xs text-slate-500">Receipt Count</div>
              <div className="text-lg font-bold text-slate-800">{c.receipt_count || 0}</div>
            </div>
            <div className="p-3 rounded-lg bg-white border border-slate-200">
              <div className="text-xs text-slate-500">Avg Transaction</div>
              <div className="text-lg font-bold text-slate-800">{fmtRs(c.average_transaction)}</div>
            </div>
          </div>
          {topOverdue.length > 0 && (
            <>
              <h4 className="text-xs font-semibold text-slate-600 mt-2">Most Overdue Invoices</h4>
              <div className="space-y-1.5">
                {topOverdue.map((inv, i) => (
                  <div key={i} className="flex items-center justify-between p-2 rounded bg-white border border-slate-100 text-xs">
                    <span className="text-slate-500">{inv.date || 'N/A'}</span>
                    <span className="font-medium text-slate-800">{fmtRs(inv.amount)}</span>
                    <span className={`font-medium ${inv.days_old > 90 ? 'text-red-600' : inv.days_old > 30 ? 'text-yellow-600' : 'text-green-600'}`}>{inv.days_old}d old</span>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
};

export default CustomerCRM;
