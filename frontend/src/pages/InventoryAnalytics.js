import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { TrendingUp, TrendingDown, AlertTriangle, BarChart3, Download, Filter as FilterIcon } from 'lucide-react';
import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const InventoryAnalytics = ({ selectedFY }) => {
  const [activeTab, setActiveTab] = useState('movement');
  const [movementData, setMovementData] = useState([]);
  const [belowCostSales, setBelowCostSales] = useState([]);
  const [salesFrequency, setSalesFrequency] = useState([]);
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);
  const [sortField, setSortField] = useState('movement_rate');
  const [sortDir, setSortDir] = useState('desc');
  const [dateFilter, setDateFilter] = useState({
    start_date: '',
    end_date: ''
  });

  useEffect(() => {
    fetchData();
  }, [activeTab, dateFilter, selectedFY]);

  const fetchData = async () => {
    setLoading(true);
    try {
      const fyParam = selectedFY ? `fy=${selectedFY}` : '';
      if (activeTab === 'movement') {
        const res = await axios.get(`${API}/inventory/movement-analysis?${fyParam}`);
        setMovementData(res.data?.data?.movements || []);
      } else if (activeTab === 'below-cost') {
        const res = await axios.get(`${API}/inventory/below-cost-sales?${fyParam}`);
        setBelowCostSales(res.data?.data?.below_cost_sales || []);
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
      <span className="flex items-center gap-1">{label} {sortField === field ? (sortDir === 'asc' ? '↑' : '↓') : ''}</span>
    </th>
  );

  const exportSalesFrequency = async (format) => {
    setExporting(true);
    try {
      const response = await axios.post(
        `${API}/analytics/sales-frequency/export`,
        {
          format,
          start_date: dateFilter.start_date || null,
          end_date: dateFilter.end_date || null
        },
        { responseType: 'blob' }
      );

      const ext = format === 'excel' ? 'xlsx' : 'pdf';
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `sales_frequency_report.${ext}`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      toast.success(`Sales frequency exported as ${format.toUpperCase()}`);
    } catch (error) {
      console.error('Export error:', error);
      toast.error('Failed to export sales frequency');
    } finally {
      setExporting(false);
    }
  };

  const tabs = [
    { id: 'movement', label: 'Movement Analysis', icon: TrendingUp },
    { id: 'below-cost', label: 'Below Cost Sales', icon: AlertTriangle },
    { id: 'sales-frequency', label: 'Sales Frequency', icon: BarChart3 }
  ];

  return (
    <div data-testid="analytics-page">
      <div className="mb-8">
        <h1 className="text-4xl font-light tracking-tight text-slate-900" style={{ fontFamily: 'Outfit, sans-serif' }}>
          Inventory Analytics
        </h1>
        <p className="mt-2 text-base text-slate-600">Advanced inventory analysis and insights</p>
      </div>

      {/* Tabs */}
      <div className="bg-white border border-slate-200 rounded-xl p-2 mb-6 flex gap-2">
        {tabs.map(tab => {
          const Icon = tab.icon;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              data-testid={`tab-${tab.id}`}
              className={`flex-1 flex items-center justify-center gap-2 px-4 py-3 rounded-lg transition-all ${
                activeTab === tab.id
                  ? 'bg-[#2563EB] text-white'
                  : 'text-slate-600 hover:bg-slate-50'
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
          {/* Movement Analysis */}
          {activeTab === 'movement' && (
            <div>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-6">
                <div className="bg-white border border-slate-200 rounded-xl p-6">
                  <div className="flex items-center gap-3 mb-2">
                    <TrendingUp className="text-green-600" size={24} />
                    <span className="text-sm font-medium text-slate-600">Fast Moving</span>
                  </div>
                  <div className="text-3xl font-semibold text-slate-900">
                    {movementData.filter(m => m.classification === 'fast-moving').length}
                  </div>
                </div>
                <div className="bg-white border border-slate-200 rounded-xl p-6">
                  <div className="flex items-center gap-3 mb-2">
                    <TrendingDown className="text-yellow-600" size={24} />
                    <span className="text-sm font-medium text-slate-600">Slow Moving</span>
                  </div>
                  <div className="text-3xl font-semibold text-slate-900">
                    {movementData.filter(m => m.classification === 'slow-moving').length}
                  </div>
                </div>
                <div className="bg-white border border-slate-200 rounded-xl p-6">
                  <div className="flex items-center gap-3 mb-2">
                    <AlertTriangle className="text-red-600" size={24} />
                    <span className="text-sm font-medium text-slate-600">Dead Stock</span>
                  </div>
                  <div className="text-3xl font-semibold text-slate-900">
                    {movementData.filter(m => m.classification === 'dead-stock').length}
                  </div>
                </div>
              </div>

              <div className="bg-white border border-slate-200 rounded-xl overflow-hidden">
                <div className="overflow-x-auto">
                  <table className="data-table" data-testid="movement-table">
                    <thead>
                      <tr>
                        <SortTh field="item_name" label="Item Name" />
                        <th>Category</th>
                        <SortTh field="opening_stock" label="Opening Stock" className="numeric" />
                        <SortTh field="sales" label="Sales" className="numeric" />
                        <SortTh field="closing_stock" label="Closing Stock" className="numeric" />
                        <SortTh field="movement_rate" label="Movement Rate %" className="numeric" />
                        <SortTh field="days_to_sell" label="Days to Sell" className="numeric" />
                        <th>Classification</th>
                      </tr>
                    </thead>
                    <tbody>
                      {[...movementData].sort((a, b) => {
                        const dir = sortDir === 'asc' ? 1 : -1;
                        if (sortField === 'item_name') return dir * (a.item_name || '').localeCompare(b.item_name || '');
                        return dir * ((a[sortField] || 0) - (b[sortField] || 0));
                      }).map((item, idx) => (
                        <tr key={idx}>
                          <td className="font-medium">{item.item_name}</td>
                          <td>{item.category}</td>
                          <td className="numeric">{item.opening_stock}</td>
                          <td className="numeric">{item.sales}</td>
                          <td className="numeric">{item.closing_stock}</td>
                          <td className="numeric font-semibold">{item.movement_rate}%</td>
                          <td className="numeric">{item.days_to_sell}</td>
                          <td>
                            <span className={`px-3 py-1 rounded-full text-xs font-medium ${
                              item.classification === 'fast-moving' ? 'bg-green-100 text-green-700' :
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
            </div>
          )}

          {/* Below Cost Sales */}
          {activeTab === 'below-cost' && (
            <div>
              <div className="bg-red-50 border border-red-200 rounded-xl p-6 mb-6">
                <div className="flex items-center gap-3 mb-2">
                  <AlertTriangle className="text-red-600" size={24} />
                  <h3 className="text-lg font-semibold text-red-900">Critical: Items Sold Below Cost</h3>
                </div>
                <div className="grid grid-cols-2 gap-4 mt-4">
                  <div>
                    <div className="text-sm text-red-600">Total Transactions</div>
                    <div className="text-2xl font-bold text-red-900">{belowCostSales.length}</div>
                  </div>
                  <div>
                    <div className="text-sm text-red-600">Total Loss</div>
                    <div className="text-2xl font-bold text-red-900">
                      ₹{belowCostSales.reduce((sum, item) => sum + item.total_loss, 0).toLocaleString('en-IN')}
                    </div>
                  </div>
                </div>
              </div>

              <div className="bg-white border border-slate-200 rounded-xl overflow-hidden">
                <div className="overflow-x-auto">
                  <table className="data-table" data-testid="below-cost-table">
                    <thead>
                      <tr>
                        <th>Item Name</th>
                        <th>Voucher ID</th>
                        <th>Date</th>
                        <th>Customer</th>
                        <th className="numeric">Purchase Price</th>
                        <th className="numeric">Sale Price</th>
                        <th className="numeric">Loss/Unit</th>
                        <th className="numeric">Quantity</th>
                        <th className="numeric">Total Loss</th>
                      </tr>
                    </thead>
                    <tbody>
                      {belowCostSales.length > 0 ? (
                        belowCostSales.map((item, idx) => (
                          <tr key={idx} className="bg-red-50">
                            <td className="font-medium text-red-900">{item.item_name}</td>
                            <td>{item.voucher_id}</td>
                            <td>{item.sale_date}</td>
                            <td>{item.customer}</td>
                            <td className="numeric">₹{item.purchase_price.toLocaleString('en-IN')}</td>
                            <td className="numeric">₹{item.sale_price.toLocaleString('en-IN')}</td>
                            <td className="numeric text-red-600 font-semibold">
                              ₹{item.loss_per_unit.toLocaleString('en-IN')}
                            </td>
                            <td className="numeric">{item.quantity_sold}</td>
                            <td className="numeric text-red-600 font-bold">
                              ₹{item.total_loss.toLocaleString('en-IN')}
                            </td>
                          </tr>
                        ))
                      ) : (
                        <tr>
                          <td colSpan="9" className="text-center py-8">
                            <div className="text-green-600 font-medium">✓ No items sold below cost - Great!</div>
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}


          {/* Sales Frequency Report */}
          {activeTab === 'sales-frequency' && (
            <div>
              <div className="bg-white border border-slate-200 rounded-xl p-6 mb-6">
                <div className="flex items-center justify-between">
                  <h3 className="text-lg font-medium text-slate-900">Date Filter</h3>
                  <div className="flex gap-2">
                    <button
                      onClick={() => exportSalesFrequency('excel')}
                      disabled={exporting || salesFrequency.length === 0}
                      className="btn-primary flex items-center gap-2 text-sm disabled:opacity-50"
                      data-testid="export-freq-excel"
                    >
                      <Download size={14} />
                      {exporting ? 'Exporting...' : 'Excel'}
                    </button>
                    <button
                      onClick={() => exportSalesFrequency('pdf')}
                      disabled={exporting || salesFrequency.length === 0}
                      className="btn-secondary flex items-center gap-2 text-sm disabled:opacity-50"
                      data-testid="export-freq-pdf"
                    >
                      <Download size={14} />
                      PDF
                    </button>
                    <button
                      onClick={() => setDateFilter({ start_date: '', end_date: '' })}
                      className="btn-secondary text-sm"
                    >
                      Clear Filters
                    </button>
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-4 mt-4">
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

              <div className="bg-white border border-slate-200 rounded-xl overflow-hidden">
                <div className="overflow-x-auto">
                  <table className="data-table" data-testid="sales-frequency-table">
                    <thead>
                      <tr>
                        <th>Item Name</th>
                        <th className="numeric">Transaction Count</th>
                        <th className="numeric">Total Qty Sold</th>
                        <th className="numeric">Unique Customers</th>
                        <th className="numeric">Total Revenue</th>
                        <th className="numeric">Avg Qty/Transaction</th>
                        <th>Top Customers</th>
                      </tr>
                    </thead>
                    <tbody>
                      {salesFrequency.length > 0 ? (
                        salesFrequency.map((item, idx) => (
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
              </div>

              {salesFrequency.length > 0 && (
                <div className="mt-4 grid grid-cols-3 gap-4">
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

        </>
      )}
    </div>
  );
};

export default InventoryAnalytics;
