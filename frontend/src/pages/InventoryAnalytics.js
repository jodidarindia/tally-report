import React, { useState, useEffect, useMemo, useRef } from 'react';
import axios from 'axios';
import { TrendingUp, TrendingDown, AlertTriangle, BarChart3, Download, Filter as FilterIcon, Users, Search } from 'lucide-react';
import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const InventoryAnalytics = ({ selectedFY, excludeBranches }) => {
  const [activeTab, setActiveTab] = useState('movement');
  const [movementData, setMovementData] = useState([]);
  const [belowCostData, setBelowCostData] = useState({ items: [], summary: {} });
  const [salesFrequency, setSalesFrequency] = useState([]);
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);

  // Customer Items tab state
  const [customerNames, setCustomerNames] = useState([]);
  const [selectedCustomer, setSelectedCustomer] = useState('');
  const [customerSearch, setCustomerSearch] = useState('');
  const [showCustomerDropdown, setShowCustomerDropdown] = useState(false);
  const [customerItemsData, setCustomerItemsData] = useState(null);
  const [customerItemsLoading, setCustomerItemsLoading] = useState(false);
  const dropdownRef = useRef(null);

  // Close dropdown on outside click
  useEffect(() => {
    const handler = (e) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target)) {
        setShowCustomerDropdown(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);
  const [sortField, setSortField] = useState('movement_rate');
  const [sortDir, setSortDir] = useState('desc');
  const [classFilter, setClassFilter] = useState('all');
  const [dateFilter, setDateFilter] = useState({
    start_date: '',
    end_date: ''
  });

  useEffect(() => {
    // Don't fetch sales-frequency mid-typing — only when both dates are set, or both empty
    if (activeTab === 'sales-frequency') {
      const s = dateFilter.start_date, e = dateFilter.end_date;
      const bothEmpty = !s && !e;
      const bothSet = !!s && !!e;
      if (!bothEmpty && !bothSet) return;       // partial state — wait
      if (bothSet && s > e) return;              // invalid range — wait
    }
    fetchData();
  }, [activeTab, dateFilter, selectedFY, excludeBranches]);

  // Fetch customer names when switching to customer-items tab
  useEffect(() => {
    if (activeTab === 'customer-items') {
      fetchCustomerNames();
    }
  }, [activeTab, selectedFY, excludeBranches]);

  // Fetch customer item data when customer is selected
  useEffect(() => {
    if (selectedCustomer && activeTab === 'customer-items') {
      fetchCustomerItemSales(selectedCustomer);
    }
  }, [selectedCustomer, selectedFY, excludeBranches]);

  const fetchCustomerNames = async () => {
    try {
      const fyParam = selectedFY ? `fy=${selectedFY}` : '';
      const res = await axios.get(`${API}/sales/customer-names?${fyParam}`);
      setCustomerNames(res.data?.data?.customers || []);
    } catch { /* ignore */ }
  };

  const fetchCustomerItemSales = async (customer) => {
    setCustomerItemsLoading(true);
    try {
      const fyParam = selectedFY ? `&fy=${selectedFY}` : '';
      const res = await axios.get(`${API}/sales/customer-item-sales?customer=${encodeURIComponent(customer)}${fyParam}`);
      if (res.data?.success) {
        setCustomerItemsData(res.data.data);
      } else {
        toast.error(res.data?.error || 'Failed to load data');
      }
    } catch { toast.error('Failed to load customer item sales'); }
    finally { setCustomerItemsLoading(false); }
  };

  const handleCustomerSelect = (name) => {
    setSelectedCustomer(name);
    setCustomerSearch(name);
    setShowCustomerDropdown(false);
  };

  const filteredCustomerNames = useMemo(() => {
    if (!customerSearch.trim()) return customerNames;
    const q = customerSearch.toLowerCase();
    return customerNames.filter(n => n.toLowerCase().includes(q));
  }, [customerNames, customerSearch]);

  const handleExportCustomerItems = async () => {
    if (!selectedCustomer) return;
    setExporting(true);
    try {
      const fyParam = selectedFY ? `&fy=${selectedFY}` : '';
      const res = await axios.get(
        `${API}/sales/customer-item-sales-export?customer=${encodeURIComponent(selectedCustomer)}${fyParam}`,
        { responseType: 'blob' }
      );
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const link = document.createElement('a');
      link.href = url;
      const safeName = selectedCustomer.replace(/[^a-zA-Z0-9]/g, '_').substring(0, 30);
      link.setAttribute('download', `customer_items_${safeName}_${selectedFY || 'all'}.xlsx`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      toast.success('Customer item sales exported');
    } catch { toast.error('Export failed'); }
    finally { setExporting(false); }
  };

  const fetchData = async () => {
    setLoading(true);
    try {
      const fyParam = selectedFY ? `fy=${selectedFY}` : '';
      if (activeTab === 'movement') {
        const res = await axios.get(`${API}/inventory/movement-analysis?${fyParam}`);
        setMovementData(res.data?.data?.movements || []);
      } else if (activeTab === 'below-cost') {
        const res = await axios.get(`${API}/inventory/below-cost-sales?${fyParam}`);
        setBelowCostData(res.data?.data || { items: [], summary: {} });
      } else if (activeTab === 'sales-frequency') {
        const params = new URLSearchParams();
        if (dateFilter.start_date) params.append('start_date', dateFilter.start_date);
        if (dateFilter.end_date) params.append('end_date', dateFilter.end_date);
        if (selectedFY) params.append('fy', selectedFY);
        
        const url = params.toString() ? `${API}/inventory/sales-frequency?${params.toString()}` : `${API}/inventory/sales-frequency`;
        const res = await axios.get(url);
        setSalesFrequency(res.data?.data?.frequency || []);
      }
    } catch (error) {
      console.error('Error fetching data:', error);
      toast.error('Failed to load analytics');
    } finally {
      setLoading(false);
    }
  };

  const handleSort = (field) => {
    if (sortField === field) setSortDir(sortDir === 'asc' ? 'desc' : 'asc');
    else { setSortField(field); setSortDir('desc'); }
  };

  const SortTh = ({ field, label, className = '' }) => (
    <th className={`cursor-pointer select-none hover:bg-slate-50 ${className}`} onClick={() => handleSort(field)} data-testid={`sort-analytics-${field}`}>
      <span className="flex items-center gap-1">{label} {sortField === field ? (sortDir === 'asc' ? '\u2191' : '\u2193') : ''}</span>
    </th>
  );

  const handleExportMovement = async () => {
    setExporting(true);
    try {
      const fyParam = selectedFY ? `fy=${selectedFY}` : '';
      const res = await axios.get(`${API}/inventory/movement-export?${fyParam}`, { responseType: 'blob' });
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `movement_analysis_${selectedFY || 'all'}.xlsx`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      toast.success('Movement analysis exported');
    } catch { toast.error('Export failed'); }
    finally { setExporting(false); }
  };

  const handleExportBelowCost = async () => {
    setExporting(true);
    try {
      const fyParam = selectedFY ? `fy=${selectedFY}` : '';
      const res = await axios.get(`${API}/inventory/below-cost-export?${fyParam}`, { responseType: 'blob' });
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `below_cost_sales_${selectedFY || 'all'}.xlsx`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      toast.success('Below cost sales exported');
    } catch { toast.error('Export failed'); }
    finally { setExporting(false); }
  };

  const exportSalesFrequency = async (format) => {
    setExporting(true);
    try {
      const params = new URLSearchParams();
      if (dateFilter.start_date) params.append('start_date', dateFilter.start_date);
      if (dateFilter.end_date) params.append('end_date', dateFilter.end_date);
      if (selectedFY) params.append('fy', selectedFY);
      params.append('format', format);
      const res = await axios.get(`${API}/inventory/sales-frequency-export?${params.toString()}`, { responseType: 'blob' });
      const ext = format === 'pdf' ? 'pdf' : 'xlsx';
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `sales_frequency_${selectedFY || 'all'}.${ext}`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      toast.success(`Sales frequency exported as ${format.toUpperCase()}`);
    } catch { toast.error('Export failed'); }
    finally { setExporting(false); }
  };

  const filteredMovement = classFilter === 'all' ? movementData : movementData.filter(m => m.classification === classFilter);

  const fmt = (n) => {
    if (n === undefined || n === null || n === 0) return '0';
    if (n >= 10000000) return `${(n / 10000000).toFixed(2)} Cr`;
    if (n >= 100000) return `${(n / 100000).toFixed(2)} L`;
    if (n >= 1000) return `${(n / 1000).toFixed(1)} K`;
    return Number(n).toLocaleString('en-IN', { maximumFractionDigits: 0 });
  };

  const tabs = [
    { id: 'movement', label: 'Movement Analysis', icon: TrendingUp },
    { id: 'category-sales', label: 'Category Sales', icon: BarChart3 },
    { id: 'below-cost', label: 'Below Cost Sales', icon: AlertTriangle },
    { id: 'sales-frequency', label: 'Sales Frequency', icon: BarChart3 },
    { id: 'customer-items', label: 'Customer Items', icon: Users }
  ];

  return (
    <div data-testid="analytics-page">
      <div className="mb-6">
        <h1 className="text-2xl sm:text-4xl font-light tracking-tight text-slate-900" style={{ fontFamily: 'Outfit, sans-serif' }}>
          Inventory Analytics
        </h1>
        <p className="mt-1 text-sm text-slate-600">Advanced inventory analysis and insights</p>
      </div>

      {/* Tabs */}
      <div className="bg-white border border-slate-200 rounded-xl p-1.5 sm:p-2 mb-6 flex gap-1.5 sm:gap-2 overflow-x-auto">
        {tabs.map(tab => {
          const Icon = tab.icon;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              data-testid={`tab-${tab.id}`}
              className={`flex-1 min-w-[80px] flex items-center justify-center gap-1.5 px-2 sm:px-4 py-2.5 sm:py-3 rounded-lg transition-all ${
                activeTab === tab.id
                  ? 'bg-[#2563EB] text-white'
                  : 'text-slate-600 hover:bg-slate-50'
              }`}
            >
              <Icon size={16} />
              <span className="text-xs sm:text-sm font-medium text-center leading-tight sm:whitespace-nowrap">{tab.label}</span>
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
          {/* Movement Analysis */}
          {activeTab === 'movement' && (
            <div>
              {/* Classification Filter Cards */}
              <div className="grid grid-cols-2 md:grid-cols-5 gap-2 sm:gap-3 mb-5">
                <button onClick={() => setClassFilter('all')} className={`bg-white border rounded-xl p-4 text-left transition-all ${classFilter === 'all' ? 'border-blue-500 ring-2 ring-blue-100' : 'border-slate-200 hover:border-slate-300'}`} data-testid="filter-all">
                  <div className="flex items-center gap-2 mb-1"><BarChart3 className="text-slate-600" size={16} /><span className="text-[10px] font-medium text-slate-500">All Items</span></div>
                  <div className="text-xl font-bold text-slate-900">{movementData.length}</div>
                </button>
                <button onClick={() => setClassFilter('fast-moving')} className={`bg-white border rounded-xl p-4 text-left transition-all ${classFilter === 'fast-moving' ? 'border-green-500 ring-2 ring-green-100' : 'border-slate-200 hover:border-slate-300'}`} data-testid="filter-fast-moving">
                  <div className="flex items-center gap-2 mb-1"><TrendingUp className="text-green-600" size={16} /><span className="text-[10px] font-medium text-slate-500">Fast Moving</span></div>
                  <div className="text-xl font-bold text-green-700" data-testid="fast-moving-count">{movementData.filter(m => m.classification === 'fast-moving').length}</div>
                </button>
                <button onClick={() => setClassFilter('moderate')} className={`bg-white border rounded-xl p-4 text-left transition-all ${classFilter === 'moderate' ? 'border-blue-500 ring-2 ring-blue-100' : 'border-slate-200 hover:border-slate-300'}`} data-testid="filter-moderate">
                  <div className="flex items-center gap-2 mb-1"><BarChart3 className="text-blue-600" size={16} /><span className="text-[10px] font-medium text-slate-500">Moderate</span></div>
                  <div className="text-xl font-bold text-blue-700" data-testid="moderate-count">{movementData.filter(m => m.classification === 'moderate').length}</div>
                </button>
                <button onClick={() => setClassFilter('slow-moving')} className={`bg-white border rounded-xl p-4 text-left transition-all ${classFilter === 'slow-moving' ? 'border-yellow-500 ring-2 ring-yellow-100' : 'border-slate-200 hover:border-slate-300'}`} data-testid="filter-slow-moving">
                  <div className="flex items-center gap-2 mb-1"><TrendingDown className="text-yellow-600" size={16} /><span className="text-[10px] font-medium text-slate-500">Slow Moving</span></div>
                  <div className="text-xl font-bold text-yellow-700" data-testid="slow-moving-count">{movementData.filter(m => m.classification === 'slow-moving').length}</div>
                </button>
                <button onClick={() => setClassFilter('non-moving')} className={`bg-white border rounded-xl p-4 text-left transition-all ${classFilter === 'non-moving' ? 'border-red-500 ring-2 ring-red-100' : 'border-slate-200 hover:border-slate-300'}`} data-testid="filter-non-moving">
                  <div className="flex items-center gap-2 mb-1"><AlertTriangle className="text-red-600" size={16} /><span className="text-[10px] font-medium text-slate-500">Non-Moving</span></div>
                  <div className="text-xl font-bold text-red-700" data-testid="non-moving-count">{movementData.filter(m => m.classification === 'non-moving').length}</div>
                </button>
              </div>

              {/* Export + Active filter indicator */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between mb-3 gap-2">
                {classFilter !== 'all' && (
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-slate-500">Showing: <strong className="text-slate-700 capitalize">{classFilter.replace('-', ' ')}</strong> ({filteredMovement.length} items)</span>
                    <button onClick={() => setClassFilter('all')} className="text-xs text-blue-600 hover:text-blue-700 font-medium" data-testid="reset-filter">Reset</button>
                  </div>
                )}
                {classFilter === 'all' && <div />}
                <button onClick={handleExportMovement} disabled={exporting} className="flex items-center gap-1 px-3 py-1.5 text-xs font-medium bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 transition-colors" data-testid="export-movement">
                  <Download size={12} />{exporting ? 'Exporting...' : 'Export Excel'}
                </button>
              </div>

              <div className="bg-white border border-slate-200 rounded-xl overflow-auto max-h-[calc(100vh-340px)]">
                  <table className="data-table min-w-[900px]" data-testid="movement-table">
                    <thead>
                      <tr>
                        <SortTh field="item_name" label="Item Name" />
                        <th>Part No.</th>
                        <th>Category</th>
                        <SortTh field="opening_stock" label="Opening" className="numeric" />
                        <SortTh field="inward" label="Inward" className="numeric" />
                        <SortTh field="sales" label="Outward (Sales)" className="numeric" />
                        <SortTh field="closing_stock" label="Closing" className="numeric" />
                        <SortTh field="movement_rate" label="Movement %" className="numeric" />
                        <SortTh field="days_to_sell" label="Days to Sell" className="numeric" />
                        <SortTh field="transactions" label="Txns" className="numeric" />
                        <th>Classification</th>
                      </tr>
                    </thead>
                    <tbody>
                      {[...filteredMovement].sort((a, b) => {
                        const dir = sortDir === 'asc' ? 1 : -1;
                        if (sortField === 'item_name') return dir * (a.item_name || '').localeCompare(b.item_name || '');
                        return dir * ((a[sortField] || 0) - (b[sortField] || 0));
                      }).map((item, idx) => (
                        <tr key={idx} data-testid={`movement-row-${idx}`}>
                          <td className="font-medium">{item.item_name}</td>
                          <td className="text-slate-400 text-xs">{item.part_number || '-'}</td>
                          <td className="text-slate-500 text-xs">{item.category}</td>
                          <td className="numeric">{item.opening_stock > 0 ? item.opening_stock : '-'}</td>
                          <td className="numeric">{item.inward > 0 ? item.inward : '-'}</td>
                          <td className="numeric font-medium">{item.sales > 0 ? item.sales : '-'}</td>
                          <td className="numeric font-semibold">{item.closing_stock > 0 ? item.closing_stock : '0'}</td>
                          <td className="numeric font-semibold">{item.movement_rate}%</td>
                          <td className="numeric">{item.days_to_sell >= 999 ? 'N/A' : item.days_to_sell}</td>
                          <td className="numeric">{item.transactions || 0}</td>
                          <td>
                            <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold ${
                              item.classification === 'fast-moving' ? 'bg-green-100 text-green-700' :
                              item.classification === 'moderate' ? 'bg-blue-100 text-blue-700' :
                              item.classification === 'slow-moving' ? 'bg-yellow-100 text-yellow-700' :
                              'bg-red-100 text-red-700'
                            }`}>
                              {item.classification}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
              </div>
            </div>
          )}

          {/* Category Sales (A/B/C/D drill-down) */}
          {activeTab === 'category-sales' && <CategorySalesTab fy={selectedFY} formatNum={fmt} />}

          {/* Below Cost Sales */}
          {activeTab === 'below-cost' && (
            <div>
              {/* Summary */}
              {belowCostData.items.length > 0 && (
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-5">
                  <div className="bg-red-50 border border-red-200 rounded-xl p-4">
                    <div className="text-xs text-red-600 font-medium mb-1">Items Below Cost</div>
                    <div className="text-2xl font-bold text-red-700">{belowCostData.summary.total_items || 0}</div>
                  </div>
                  <div className="bg-red-50 border border-red-200 rounded-xl p-4">
                    <div className="text-xs text-red-600 font-medium mb-1">Total Loss</div>
                    <div className="text-2xl font-bold text-red-700">Rs.{fmt(belowCostData.summary.total_loss || 0)}</div>
                  </div>
                  <div className="bg-red-50 border border-red-200 rounded-xl p-4">
                    <div className="text-xs text-red-600 font-medium mb-1">Affected Revenue</div>
                    <div className="text-2xl font-bold text-red-700">Rs.{fmt(belowCostData.summary.total_affected_revenue || 0)}</div>
                  </div>
                </div>
              )}

              {belowCostData.items.length > 0 && (
                <div className="flex justify-end mb-3">
                  <button onClick={handleExportBelowCost} disabled={exporting} className="flex items-center gap-1 px-3 py-1.5 text-xs font-medium bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 transition-colors" data-testid="export-below-cost">
                    <Download size={12} />{exporting ? 'Exporting...' : 'Export Excel'}
                  </button>
                </div>
              )}

              <div className="bg-white border border-slate-200 rounded-xl overflow-x-auto">
                  <table className="data-table min-w-[800px]" data-testid="below-cost-table">
                    <thead>
                      <tr>
                        <SortTh field="item_name" label="Item Name" />
                        <SortTh field="cost_price" label="Cost Price" className="numeric" />
                        <SortTh field="avg_selling_price" label="Avg Sale Price" className="numeric" />
                        <SortTh field="margin" label="Margin" className="numeric" />
                        <SortTh field="margin_pct" label="Margin %" className="numeric" />
                        <SortTh field="qty_sold" label="Qty Sold" className="numeric" />
                        <SortTh field="total_revenue" label="Revenue" className="numeric" />
                        <SortTh field="total_loss" label="Total Loss" className="numeric" />
                      </tr>
                    </thead>
                    <tbody>
                      {belowCostData.items.length > 0 ? (
                        [...belowCostData.items].sort((a, b) => {
                          const dir = sortDir === 'asc' ? 1 : -1;
                          if (sortField === 'item_name') return dir * (a.item_name || '').localeCompare(b.item_name || '');
                          return dir * ((a[sortField] || 0) - (b[sortField] || 0));
                        }).map((item, idx) => (
                          <tr key={idx} className="bg-red-50/50" data-testid={`below-cost-row-${idx}`}>
                            <td className="font-medium text-red-900">{item.item_name}</td>
                            <td className="numeric">Rs.{item.cost_price.toLocaleString('en-IN')}</td>
                            <td className="numeric">Rs.{item.avg_selling_price.toLocaleString('en-IN')}</td>
                            <td className="numeric text-red-600 font-semibold">Rs.{item.margin.toLocaleString('en-IN')}</td>
                            <td className="numeric text-red-600 font-semibold">{item.margin_pct}%</td>
                            <td className="numeric">{item.qty_sold}</td>
                            <td className="numeric">Rs.{fmt(item.total_revenue)}</td>
                            <td className="numeric text-red-700 font-bold">Rs.{fmt(item.total_loss)}</td>
                          </tr>
                        ))
                      ) : (
                        <tr>
                          <td colSpan="8" className="text-center py-8">
                            <div className="text-green-600 font-medium">No items sold below cost{belowCostData.summary?.total_items === undefined ? ' (sync purchase vouchers from Tally* for cost data)' : ' - Great!'}</div>
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
              </div>
            </div>
          )}


          {/* Sales Frequency Report */}
          {activeTab === 'sales-frequency' && (
            <div>
              <div className="bg-white border border-slate-200 rounded-xl p-4 sm:p-6 mb-6">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <h3 className="text-lg font-medium text-slate-900">Date Filter</h3>
                  <div className="flex flex-wrap gap-2">
                    <button
                      onClick={() => exportSalesFrequency('excel')}
                      disabled={exporting || salesFrequency.length === 0}
                      className="btn-primary flex items-center gap-2 text-xs sm:text-sm disabled:opacity-50"
                      data-testid="export-freq-excel"
                    >
                      <Download size={14} />
                      {exporting ? 'Exporting...' : 'Excel'}
                    </button>
                    <button
                      onClick={() => exportSalesFrequency('pdf')}
                      disabled={exporting || salesFrequency.length === 0}
                      className="btn-secondary flex items-center gap-2 text-xs sm:text-sm disabled:opacity-50"
                      data-testid="export-freq-pdf"
                    >
                      <Download size={14} />
                      PDF
                    </button>
                    <button
                      onClick={() => setDateFilter({ start_date: '', end_date: '' })}
                      className="btn-secondary text-xs sm:text-sm"
                    >
                      Clear
                    </button>
                  </div>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mt-4">
                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-2">Start Date</label>
                    <input
                      type="date"
                      value={dateFilter.start_date}
                      onChange={(e) => setDateFilter({ ...dateFilter, start_date: e.target.value })}
                      className="w-full px-4 py-2 border border-slate-200 rounded-lg"
                      data-testid="sales-freq-start-date"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-2">End Date</label>
                    <input
                      type="date"
                      value={dateFilter.end_date}
                      onChange={(e) => setDateFilter({ ...dateFilter, end_date: e.target.value })}
                      className="w-full px-4 py-2 border border-slate-200 rounded-lg"
                      data-testid="sales-freq-end-date"
                    />
                  </div>
                </div>
                {(dateFilter.start_date || dateFilter.end_date) && (
                  <div className="mt-3 text-sm text-slate-600">
                    Filtering: {dateFilter.start_date || 'All'} to {dateFilter.end_date || 'All'}
                  </div>
                )}
              </div>

              <div className="bg-white border border-slate-200 rounded-xl overflow-auto max-h-[calc(100vh-460px)]">
                  <table className="data-table min-w-[700px]" data-testid="sales-frequency-table">
                    <thead>
                      <tr>
                        <SortTh field="item_name" label="Item Name" />
                        <SortTh field="transaction_count" label="Transaction Count" className="numeric" />
                        <SortTh field="total_quantity_sold" label="Total Qty Sold" className="numeric" />
                        <SortTh field="unique_customers" label="Unique Customers" className="numeric" />
                        <SortTh field="total_revenue" label="Total Revenue" className="numeric" />
                        <SortTh field="avg_quantity_per_transaction" label="Avg Qty/Transaction" className="numeric" />
                        <th>Top Customers</th>
                      </tr>
                    </thead>
                    <tbody>
                      {salesFrequency.length > 0 ? (
                        [...salesFrequency].sort((a, b) => {
                          const dir = sortDir === 'asc' ? 1 : -1;
                          if (sortField === 'item_name') return dir * (a.item_name || '').localeCompare(b.item_name || '');
                          return dir * ((a[sortField] || 0) - (b[sortField] || 0));
                        }).map((item, idx) => (
                          <tr key={idx}>
                            <td className="font-medium text-slate-900">{item.item_name}</td>
                            <td className="numeric">
                              <span className="px-3 py-1 bg-[#E7F5F0] text-[#2563EB] rounded-full font-semibold">
                                {item.transaction_count}
                              </span>
                            </td>
                            <td className="numeric font-semibold">{item.total_quantity_sold}</td>
                            <td className="numeric">
                              <span className="px-3 py-1 bg-blue-50 text-blue-700 rounded-full font-semibold">
                                {item.unique_customers}
                              </span>
                            </td>
                            <td className="numeric text-[#2563EB] font-semibold">
                              ₹{item.total_revenue.toLocaleString('en-IN')}
                            </td>
                            <td className="numeric">{item.avg_quantity_per_transaction.toFixed(1)}</td>
                            <td>
                              <div className="text-xs text-slate-600">
                                {(item.customer_list || []).slice(0, 2).join(', ')}
                                {(item.customer_list || []).length > 2 && ` +${(item.customer_list || []).length - 2} more`}
                              </div>
                            </td>
                          </tr>
                        ))
                      ) : (
                        <tr>
                          <td colSpan="7" className="text-center py-8 text-slate-500">
                            No sales data available for the selected date range
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
              </div>

              {salesFrequency.length > 0 && (
                <div className="mt-4 grid grid-cols-1 sm:grid-cols-3 gap-4">
                  <div className="bg-white border border-slate-200 rounded-xl p-4">
                    <div className="text-sm text-slate-600">Total Items</div>
                    <div className="text-2xl font-semibold text-slate-900">{salesFrequency.length}</div>
                  </div>
                  <div className="bg-white border border-slate-200 rounded-xl p-4">
                    <div className="text-sm text-slate-600">Total Transactions</div>
                    <div className="text-2xl font-semibold text-slate-900">
                      {salesFrequency.reduce((sum, item) => sum + item.transaction_count, 0)}
                    </div>
                  </div>
                  <div className="bg-white border border-slate-200 rounded-xl p-4">
                    <div className="text-sm text-slate-600">Total Revenue</div>
                    <div className="text-2xl font-semibold text-[#2563EB]">
                      ₹{salesFrequency.reduce((sum, item) => sum + item.total_revenue, 0).toLocaleString('en-IN')}
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Customer Items Tab */}
          {activeTab === 'customer-items' && (
            <div data-testid="customer-items-tab">
              {/* Customer Search Combobox */}
              <div className="bg-white border border-slate-200 rounded-xl p-6 mb-6" data-testid="customer-search-section">
                <div className="flex flex-col sm:flex-row items-start sm:items-center gap-4">
                  <div className="relative flex-1 w-full" ref={dropdownRef}>
                    <label className="text-sm font-medium text-slate-700 mb-1 block">Select Customer</label>
                    <div className="relative">
                      <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                      <input
                        type="text"
                        value={customerSearch}
                        onChange={(e) => {
                          setCustomerSearch(e.target.value);
                          setShowCustomerDropdown(true);
                          if (!e.target.value) { setSelectedCustomer(''); setCustomerItemsData(null); }
                        }}
                        onFocus={() => setShowCustomerDropdown(true)}
                        placeholder="Type customer name to search..."
                        className="w-full pl-10 pr-4 py-2.5 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-100 focus:border-[#2563EB]"
                        data-testid="customer-search-input"
                      />
                      {showCustomerDropdown && filteredCustomerNames.length > 0 && (
                        <div className="absolute z-20 top-full left-0 right-0 mt-1 bg-white border border-slate-200 rounded-lg shadow-lg max-h-60 overflow-y-auto" data-testid="customer-dropdown">
                          {filteredCustomerNames.map((name, idx) => (
                            <button
                              key={idx}
                              onClick={() => handleCustomerSelect(name)}
                              className={`w-full text-left px-4 py-2.5 text-sm hover:bg-blue-50 transition-colors ${
                                selectedCustomer === name ? 'bg-blue-50 text-[#2563EB] font-medium' : 'text-slate-700'
                              }`}
                              data-testid={`customer-option-${idx}`}
                            >
                              {name}
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                  {selectedCustomer && customerItemsData && (
                    <button
                      onClick={handleExportCustomerItems}
                      disabled={exporting}
                      className="mt-5 sm:mt-0 self-end flex items-center gap-2 px-4 py-2.5 bg-emerald-600 text-white rounded-lg text-sm font-medium hover:bg-emerald-700 disabled:opacity-50"
                      data-testid="export-customer-items-btn"
                    >
                      <Download size={16} />
                      {exporting ? 'Exporting...' : 'Export Excel'}
                    </button>
                  )}
                </div>
              </div>

              {/* Summary Cards */}
              {selectedCustomer && customerItemsData && (
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-6">
                  <div className="bg-white border border-slate-200 rounded-xl p-4" data-testid="ci-total-items">
                    <div className="text-xs text-slate-500 mb-1">Unique Items</div>
                    <div className="text-2xl font-bold text-slate-900">{customerItemsData.total_items}</div>
                  </div>
                  <div className="bg-white border border-slate-200 rounded-xl p-4" data-testid="ci-total-qty">
                    <div className="text-xs text-slate-500 mb-1">Total Quantity</div>
                    <div className="text-2xl font-bold text-slate-900">{customerItemsData.total_quantity?.toLocaleString('en-IN')}</div>
                  </div>
                  <div className="bg-white border border-slate-200 rounded-xl p-4" data-testid="ci-total-amount">
                    <div className="text-xs text-slate-500 mb-1">Total Amount</div>
                    <div className="text-2xl font-bold text-[#2563EB]">Rs.{customerItemsData.total_amount?.toLocaleString('en-IN')}</div>
                  </div>
                  <div className="bg-white border border-slate-200 rounded-xl p-4" data-testid="ci-total-vouchers">
                    <div className="text-xs text-slate-500 mb-1">Total Invoices</div>
                    <div className="text-2xl font-bold text-slate-900">{customerItemsData.total_vouchers}</div>
                  </div>
                </div>
              )}

              {/* Loading state */}
              {customerItemsLoading && (
                <div className="flex items-center justify-center h-40">
                  <div className="loading-spinner" />
                </div>
              )}

              {/* Items Table */}
              {selectedCustomer && customerItemsData && !customerItemsLoading && (
                <div className="bg-white border border-slate-200 rounded-xl overflow-hidden" data-testid="customer-items-table">
                  <div className="p-4 border-b border-slate-100">
                    <h3 className="font-semibold text-slate-900">
                      Items purchased by {selectedCustomer.split(',')[0]}
                    </h3>
                    <p className="text-xs text-slate-500 mt-0.5">
                      FY {selectedFY || 'All'} — {customerItemsData.total_items} items across {customerItemsData.total_vouchers} invoices
                    </p>
                  </div>
                  <div className="overflow-auto max-h-[calc(100vh-380px)]">
                    <table className="data-table min-w-[600px]" data-testid="customer-items-data-table">
                      <thead>
                        <tr>
                          <SortTh field="item_name" label="Item Name" />
                          <SortTh field="quantity" label="Quantity" className="numeric" />
                          <SortTh field="avg_rate" label="Avg Rate (Pre-GST)" className="numeric" />
                          <SortTh field="amount" label="Amount (Pre-GST)" className="numeric" />
                          <SortTh field="voucher_count" label="Invoices" className="numeric" />
                        </tr>
                      </thead>
                      <tbody>
                        {[...(customerItemsData.items || [])].sort((a, b) => {
                          const dir = sortDir === 'asc' ? 1 : -1;
                          if (sortField === 'item_name') return dir * (a.item_name || '').localeCompare(b.item_name || '');
                          return dir * ((a[sortField] || 0) - (b[sortField] || 0));
                        }).map((item, idx) => (
                          <tr key={idx} className="border-t border-slate-100 hover:bg-slate-50" data-testid={`customer-item-row-${idx}`}>
                            <td className="font-medium text-slate-800">
                              <span className="text-slate-400 mr-2 text-xs">{idx + 1}.</span>{item.item_name}
                            </td>
                            <td className="numeric text-slate-700">{item.quantity?.toLocaleString('en-IN')}</td>
                            <td className="numeric text-slate-600">Rs.{item.avg_rate?.toLocaleString('en-IN', { maximumFractionDigits: 2 })}</td>
                            <td className="numeric font-medium text-[#2563EB]">Rs.{item.amount?.toLocaleString('en-IN', { maximumFractionDigits: 2 })}</td>
                            <td className="numeric text-slate-500">{item.voucher_count}</td>
                          </tr>
                        ))}
                        {/* Totals row */}
                        <tr className="border-t-2 border-slate-200 bg-slate-50 font-bold">
                          <td>TOTAL</td>
                          <td className="numeric">{customerItemsData.total_quantity?.toLocaleString('en-IN')}</td>
                          <td className="numeric"></td>
                          <td className="numeric text-[#2563EB]">Rs.{customerItemsData.total_amount?.toLocaleString('en-IN', { maximumFractionDigits: 2 })} <span className="text-xs font-normal text-slate-500">(Pre-GST)</span></td>
                          <td className="numeric">{customerItemsData.total_vouchers}</td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* Empty State */}
              {!selectedCustomer && !customerItemsLoading && (
                <div className="bg-white border border-slate-200 rounded-xl p-12 text-center" data-testid="customer-items-empty">
                  <Users size={48} className="mx-auto text-slate-300 mb-4" />
                  <h3 className="text-lg font-medium text-slate-600 mb-1">Select a Customer</h3>
                  <p className="text-sm text-slate-400">Search and select a customer above to see their item-wise purchase details</p>
                </div>
              )}

              {/* No data for customer */}
              {selectedCustomer && customerItemsData && customerItemsData.total_items === 0 && (
                <div className="bg-white border border-slate-200 rounded-xl p-12 text-center" data-testid="customer-items-no-data">
                  <AlertTriangle size={48} className="mx-auto text-amber-300 mb-4" />
                  <h3 className="text-lg font-medium text-slate-600 mb-1">No Sales Found</h3>
                  <p className="text-sm text-slate-400">No item sales found for {selectedCustomer} in FY {selectedFY || 'selected period'}</p>
                </div>
              )}
            </div>
          )}

        </>
      )}
    </div>
  );
};

export default InventoryAnalytics;

// ─── Category Sales Tab (A/B/C/D drill-down) ──────────────────────────────
function CategorySalesTab({ fy, formatNum }) {
  const [activeABC, setActiveABC] = useState('A');
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    axios.get(`${API}/inventory/category-sales?abc=${activeABC}&fy=${fy || ''}`)
      .then(r => { if (!cancelled && r.data?.success) setData(r.data.data); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [activeABC, fy]);

  const downloadExcel = () => {
    if (!data || !data.items.length) return;
    const rows = [['ABC', 'Item', 'Part No', 'Stock Group', 'Current Stock', 'Sale Price', 'FY Qty', 'FY Revenue', 'Order Frequency', 'Top Customer', 'Top Customer Revenue']];
    data.items.forEach(it => {
      const top = (it.top_customers || [])[0];
      rows.push([data.abc, it.item_name, it.part_number || '', it.stock_group || '',
        it.current_stock, it.standard_price, it.total_qty, it.total_revenue,
        it.order_count, top?.customer_name || '', top?.revenue || 0]);
    });
    const csv = rows.map(r => r.map(v => `"${String(v ?? '').replace(/"/g, '""')}"`).join(',')).join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = `category_sales_${data.abc}_${fy || 'all'}.csv`;
    a.click(); URL.revokeObjectURL(url);
  };

  const ABC_COLORS = { A: '#10b981', B: '#3b82f6', C: '#f59e0b', D: '#94a3b8' };
  const ABC_DESC = {
    A: 'Top 80% of revenue (highest value items)',
    B: 'Next 15% of revenue',
    C: 'Next 4% of revenue',
    D: 'Remaining 1% (slow / dead stock)',
  };

  const filtered = !data ? [] : (search
    ? data.items.filter(it => (it.item_name || '').toLowerCase().includes(search.toLowerCase())
        || (it.part_number || '').toLowerCase().includes(search.toLowerCase()))
    : data.items);

  return (
    <div data-testid="category-sales-tab">
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 sm:gap-3 mb-4">
        {['A', 'B', 'C', 'D'].map(letter => (
          <button key={letter} onClick={() => setActiveABC(letter)} data-testid={`abc-pill-${letter}`}
            className={`text-left rounded-xl p-3 sm:p-4 border-2 transition-all ${activeABC === letter ? 'shadow-md' : 'border-slate-200 hover:border-slate-300'}`}
            style={activeABC === letter ? { borderColor: ABC_COLORS[letter], background: ABC_COLORS[letter] + '10' } : {}}>
            <div className="flex items-center gap-2 mb-1">
              <div className="w-7 h-7 rounded-lg flex items-center justify-center font-bold text-white text-sm" style={{ background: ABC_COLORS[letter] }}>{letter}</div>
              <div className="text-[10px] sm:text-xs text-slate-500 font-medium leading-tight">{ABC_DESC[letter]}</div>
            </div>
          </button>
        ))}
      </div>

      <div className="bg-white border border-slate-200 rounded-xl overflow-hidden">
        <div className="px-3 py-2.5 border-b border-slate-100 flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <div>
            <h3 className="text-sm font-semibold text-slate-900 flex items-center gap-2">
              <span className="w-6 h-6 rounded-md flex items-center justify-center font-bold text-white text-xs" style={{ background: ABC_COLORS[activeABC] }}>{activeABC}</span>
              Category {activeABC} — {data?.summary?.items || 0} items
            </h3>
            {data && <p className="text-[11px] text-slate-500 mt-0.5">FY {data.fy || '—'} · Total qty {formatNum(data.summary.qty)} · Revenue ₹{formatNum(data.summary.revenue)}</p>}
          </div>
          <div className="flex gap-2 items-center">
            <div className="relative">
              <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400" />
              <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search item / part #" className="pl-8 pr-3 py-1.5 text-xs border border-slate-200 rounded-lg" data-testid="abc-item-search" />
            </div>
            <button onClick={downloadExcel} className="text-xs flex items-center gap-1.5 bg-emerald-600 text-white px-3 py-1.5 rounded-lg hover:bg-emerald-700" data-testid="abc-export-csv">
              <Download size={13} /> Export CSV
            </button>
          </div>
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-12"><div className="loading-spinner" /></div>
        ) : (
          <div className="max-h-[60vh] overflow-y-auto">
            {filtered.length === 0 && <p className="text-center text-sm text-slate-400 py-10">No items in category {activeABC} {search ? `matching "${search}"` : ''}.</p>}
            {filtered.map((it, i) => (
              <details key={i} className="border-b border-slate-100 last:border-0 group" data-testid={`abc-item-${i}`}>
                <summary className="px-3 py-2.5 cursor-pointer hover:bg-slate-50">
                  <div className="flex items-center justify-between gap-2">
                    <div className="min-w-0 flex-1">
                      <div className="text-xs sm:text-sm font-medium text-slate-900 truncate">{it.item_name}</div>
                      <div className="text-[10px] text-slate-500 flex flex-wrap gap-x-3 gap-y-0.5 mt-0.5">
                        {it.part_number && <span className="font-mono">P/N: {it.part_number}</span>}
                        {it.stock_group && <span>{it.stock_group}</span>}
                        <span>Stock: {formatNum(it.current_stock)}</span>
                        <span>Sale: ₹{formatNum(it.standard_price)}</span>
                      </div>
                    </div>
                    <div className="text-right flex-shrink-0">
                      <div className="text-xs sm:text-sm font-bold text-slate-900">₹{formatNum(it.total_revenue)}</div>
                      <div className="text-[10px] text-slate-500">Qty {formatNum(it.total_qty)} · {it.order_count} orders</div>
                    </div>
                  </div>
                </summary>
                <div className="bg-slate-50 px-3 py-2 border-t border-slate-100">
                  <div className="text-[10px] uppercase tracking-wide text-slate-500 font-semibold mb-1.5">Top Customers</div>
                  {(!it.top_customers || it.top_customers.length === 0) && <p className="text-[11px] text-slate-400 italic">No customer transactions in this FY.</p>}
                  {(it.top_customers || []).map((c, j) => (
                    <div key={j} className="flex items-center justify-between text-[11px] py-0.5">
                      <span className="truncate flex-1 min-w-0 text-slate-700">{j + 1}. {c.customer_name}</span>
                      <span className="text-slate-500 flex-shrink-0 ml-3">Qty {formatNum(c.qty)} · ₹{formatNum(c.revenue)} · {c.count}x</span>
                    </div>
                  ))}
                </div>
              </details>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
