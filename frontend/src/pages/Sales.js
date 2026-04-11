import React, { useState, useEffect, useMemo } from 'react';
import axios from 'axios';
import { TrendingUp, Calendar, User, FileText, Download, X, Package, Truck, Receipt, Filter, ChevronDown } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';
import SearchableSelect from '../components/SearchableSelect';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const InvoiceModal = ({ voucherId, onClose }) => {
  const [voucher, setVoucher] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchVoucher = async () => {
      try {
        const res = await axios.get(`${API}/sales/vouchers/${encodeURIComponent(voucherId)}`);
        if (res.data?.success) setVoucher(res.data.data);
      } catch (err) {
        console.error('Error fetching voucher:', err);
      } finally {
        setLoading(false);
      }
    };
    fetchVoucher();
  }, [voucherId]);

  if (loading) return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={onClose}>
      <div className="bg-white rounded-xl p-8 text-center" onClick={e => e.stopPropagation()}>Loading...</div>
    </div>
  );

  if (!voucher) return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={onClose}>
      <div className="bg-white rounded-xl p-8 text-center" onClick={e => e.stopPropagation()}>
        <p className="text-red-600 mb-4">Voucher not found</p>
        <button onClick={onClose} className="btn-primary px-4 py-2 bg-[#2563EB] text-white rounded-lg">Close</button>
      </div>
    </div>
  );

  const items = voucher.items || [];
  const gstDetails = voucher.gst_details || [];
  const dispatch = voucher.dispatch_details || {};
  const hasDispatch = dispatch.dispatch_through || dispatch.destination || dispatch.carrier_name;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4" onClick={onClose} data-testid="invoice-modal">
      <div className="bg-white rounded-xl max-w-3xl w-full max-h-[85vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
        <div className="bg-gradient-to-r from-[#2563EB] to-[#7C3AED] p-6 rounded-t-xl flex justify-between items-start">
          <div>
            <h2 className="text-white text-xl font-bold">Invoice {voucher.voucher_id}</h2>
            <p className="text-blue-100 text-sm mt-1">{voucher.voucher_date}</p>
          </div>
          <button onClick={onClose} className="text-white/80 hover:text-white" data-testid="modal-close"><X size={20} /></button>
        </div>

        <div className="p-6 space-y-6">
          {/* Customer Info */}
          <div className="flex items-start gap-3">
            <User size={18} className="text-slate-400 mt-0.5" />
            <div>
              <p className="font-semibold text-slate-900">{voucher.party_name}</p>
              {voucher.reference_number && <p className="text-sm text-slate-500">Ref: {voucher.reference_number}</p>}
            </div>
          </div>

          {/* Line Items */}
          {items.length > 0 && (
            <div>
              <h3 className="text-sm font-semibold text-slate-700 mb-2 flex items-center gap-2"><Package size={14} /> Items</h3>
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-200 text-slate-500">
                    <th className="text-left py-2">Item</th>
                    <th className="text-right py-2">Qty</th>
                    <th className="text-right py-2">Rate</th>
                    <th className="text-right py-2">Amount</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((item, idx) => (
                    <tr key={idx} className="border-b border-slate-100">
                      <td className="py-2 text-slate-800">{item.item}</td>
                      <td className="py-2 text-right text-slate-600">{item.quantity}</td>
                      <td className="py-2 text-right text-slate-600">Rs.{(item.rate || 0).toLocaleString('en-IN')}</td>
                      <td className="py-2 text-right font-medium">Rs.{(item.amount || 0).toLocaleString('en-IN')}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Subtotal / Discount / GST / Total */}
          <div className="border-t border-slate-200 pt-4 space-y-2">
            <div className="flex justify-between text-sm text-slate-600">
              <span>Subtotal</span>
              <span>Rs.{(voucher.subtotal || 0).toLocaleString('en-IN')}</span>
            </div>
            {voucher.discount_amount > 0 && (
              <div className="flex justify-between text-sm text-green-600">
                <span>Discount</span>
                <span>- Rs.{voucher.discount_amount.toLocaleString('en-IN')}</span>
              </div>
            )}
            {gstDetails.length > 0 && gstDetails.map((g, i) => (
              <div key={i} className="flex justify-between text-sm text-slate-600">
                <span>{g.tax_name}</span>
                <span>Rs.{(g.amount || 0).toLocaleString('en-IN')}</span>
              </div>
            ))}
            {(voucher.gst_total || 0) > 0 && (
              <div className="flex justify-between text-sm font-medium text-slate-700">
                <span>Total Tax</span>
                <span>Rs.{voucher.gst_total.toLocaleString('en-IN')}</span>
              </div>
            )}
            <div className="flex justify-between text-lg font-bold text-[#2563EB] border-t border-slate-200 pt-2">
              <span>Total</span>
              <span>Rs.{(voucher.computed_total || voucher.total_amount || 0).toLocaleString('en-IN')}</span>
            </div>
          </div>

          {/* Dispatch Details */}
          {hasDispatch && (
            <div className="bg-slate-50 border border-slate-200 rounded-lg p-4">
              <h3 className="text-sm font-semibold text-slate-700 mb-2 flex items-center gap-2"><Truck size={14} /> Dispatch Details</h3>
              <div className="grid grid-cols-2 gap-3 text-sm">
                {dispatch.dispatch_through && (
                  <div><span className="text-slate-500">Dispatch Through: </span><span className="text-slate-800">{dispatch.dispatch_through}</span></div>
                )}
                {dispatch.destination && (
                  <div><span className="text-slate-500">Destination: </span><span className="text-slate-800">{dispatch.destination}</span></div>
                )}
                {dispatch.carrier_name && (
                  <div><span className="text-slate-500">Carrier: </span><span className="text-slate-800">{dispatch.carrier_name}</span></div>
                )}
                {dispatch.delivery_note && (
                  <div><span className="text-slate-500">Delivery Note: </span><span className="text-slate-800">{dispatch.delivery_note}</span></div>
                )}
                {dispatch.bill_of_lading && (
                  <div><span className="text-slate-500">Bill of Lading: </span><span className="text-slate-800">{dispatch.bill_of_lading}</span></div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

const Sales = ({ selectedFY, excludeBranches }) => {
  const [vouchers, setVouchers] = useState([]);
  const [analytics, setAnalytics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [selectedVoucher, setSelectedVoucher] = useState(null);
  const [uniqueParties, setUniqueParties] = useState([]);
  const [uniqueMonths, setUniqueMonths] = useState([]);

  // Filters
  const [filterParty, setFilterParty] = useState('');
  const [filterMonth, setFilterMonth] = useState('');
  const [sortField, setSortField] = useState('voucher_date');
  const [sortDir, setSortDir] = useState('desc');

  useEffect(() => {
    fetchSalesData();
  }, [selectedFY, filterParty, filterMonth, excludeBranches]);

  const fetchSalesData = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (selectedFY) params.append('fy', selectedFY);
      if (filterParty) params.append('party_name', filterParty);
      if (filterMonth) params.append('month', filterMonth);
      const qs = params.toString();

      const [vouchersRes, analyticsRes] = await Promise.all([
        axios.get(`${API}/sales/vouchers${qs ? '?' + qs : ''}`),
        axios.get(`${API}/sales/analytics${qs ? '?' + qs : ''}`)
      ]);

      const vData = vouchersRes.data?.data || {};
      setVouchers(vData.vouchers || []);
      setUniqueParties(vData.unique_parties || []);
      setUniqueMonths(vData.unique_months || []);
      setAnalytics(analyticsRes.data?.data || null);
    } catch (error) {
      console.error('Error fetching sales data:', error);
    } finally {
      setLoading(false);
    }
  };

  const monthLabel = (m) => {
    if (!m || m.length < 7) return m;
    const [y, mo] = m.split('-');
    const names = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
    return `${names[parseInt(mo) - 1] || mo} ${y}`;
  };

  const totalAmount = vouchers.reduce((s, v) => s + (v.total_amount || 0), 0);

  const handleSort = (field) => {
    if (sortField === field) setSortDir(sortDir === 'asc' ? 'desc' : 'asc');
    else { setSortField(field); setSortDir('desc'); }
  };

  const SortTh = ({ field, label, className = '' }) => (
    <th className={`cursor-pointer select-none hover:bg-slate-50 ${className}`} onClick={() => handleSort(field)} data-testid={`sort-sales-${field}`}>
      <span className="flex items-center gap-1">{label} {sortField === field ? (sortDir === 'asc' ? '↑' : '↓') : ''}</span>
    </th>
  );

  const sortedVouchers = [...vouchers].sort((a, b) => {
    const dir = sortDir === 'asc' ? 1 : -1;
    if (sortField === 'party_name') return dir * (a.party_name || '').localeCompare(b.party_name || '');
    if (sortField === 'voucher_date') return dir * (a.voucher_date || '').localeCompare(b.voucher_date || '');
    if (sortField === 'voucher_id') return dir * (a.voucher_id || '').localeCompare(b.voucher_id || '');
    if (sortField === 'total_amount') return dir * ((a.total_amount || 0) - (b.total_amount || 0));
    return 0;
  });

  const handleExport = async (format) => {
    try {
      const params = new URLSearchParams();
      if (selectedFY) params.append('fy', selectedFY);
      params.append('format', format);
      const url = `${API}/export/sales?${params.toString()}`;
      window.open(url, '_blank');
    } catch (err) {
      console.error('Export error:', err);
    }
  };

  if (loading) return (
    <div className="flex items-center justify-center h-64">
      <div className="animate-spin w-8 h-8 border-2 border-[#2563EB] border-t-transparent rounded-full"></div>
    </div>
  );

  return (
    <div className="space-y-6" data-testid="sales-page">
      {/* Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Sales</h1>
          <p className="text-slate-600 text-sm">{vouchers.length} vouchers | Rs.{totalAmount.toLocaleString('en-IN')}</p>
        </div>
        <div className="flex gap-2">
          <button onClick={() => handleExport('pdf')} className="flex items-center gap-2 px-3 py-2 bg-red-50 text-red-700 rounded-lg hover:bg-red-100 text-sm" data-testid="export-pdf-btn">
            <Download size={14} /> PDF
          </button>
          <button onClick={() => handleExport('excel')} className="flex items-center gap-2 px-3 py-2 bg-green-50 text-green-700 rounded-lg hover:bg-green-100 text-sm" data-testid="export-excel-btn">
            <Download size={14} /> Excel
          </button>
        </div>
      </div>

      {/* Filters Row */}
      <div className="bg-white border border-slate-200 rounded-xl p-4" data-testid="sales-filters">
        <div className="flex items-center gap-2 mb-3">
          <Filter size={16} className="text-slate-500" />
          <span className="text-sm font-medium text-slate-700">Filters</span>
          {(filterParty || filterMonth) && (
            <button onClick={() => { setFilterParty(''); setFilterMonth(''); }} className="text-xs text-red-500 hover:text-red-700 ml-auto">
              Clear All
            </button>
          )}
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {/* Party Filter */}
          <div>
            <SearchableSelect
              options={uniqueParties}
              value={filterParty}
              onChange={(val) => setFilterParty(val === filterParty ? '' : val)}
              placeholder="All Customers"
              testId="filter-party-select"
            />
          </div>

          {/* Month Filter */}
          <div className="relative">
            <select
              data-testid="filter-month-select"
              value={filterMonth}
              onChange={(e) => setFilterMonth(e.target.value)}
              className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-[#2563EB] appearance-none bg-white"
            >
              <option value="">All Months</option>
              {uniqueMonths.map(m => <option key={m} value={m}>{monthLabel(m)}</option>)}
            </select>
            <ChevronDown size={14} className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
          </div>
        </div>
      </div>

      {/* Chart — updates with filters */}
      {analytics?.daily_sales?.length > 0 && (
        <div className="bg-white border border-slate-200 rounded-xl p-6" data-testid="sales-chart">
          <h3 className="text-sm font-semibold text-slate-700 mb-4 flex items-center gap-2">
            <TrendingUp size={16} /> Sales Trend
            {filterParty && <span className="text-xs bg-blue-50 text-blue-700 px-2 py-0.5 rounded-full ml-2">{filterParty}</span>}
            {filterMonth && <span className="text-xs bg-purple-50 text-purple-700 px-2 py-0.5 rounded-full ml-1">{monthLabel(filterMonth)}</span>}
          </h3>
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={analytics.daily_sales}>
              <XAxis dataKey="date" stroke="#64748B" style={{ fontSize: '11px' }} />
              <YAxis stroke="#64748B" style={{ fontSize: '11px' }} />
              <Tooltip contentStyle={{ background: 'white', border: '1px solid #E0E7FF', borderRadius: '8px', padding: '12px' }} />
              <Bar dataKey="amount" fill="#2563EB" radius={[6, 6, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Table */}
      <div className="bg-white border border-slate-200 rounded-xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="data-table" data-testid="sales-table">
            <thead>
              <tr>
                <SortTh field="voucher_id" label="Voucher No." />
                <SortTh field="voucher_date" label="Date" />
                <SortTh field="party_name" label="Customer" />
                <th>Items</th>
                <th>Reference</th>
                <SortTh field="total_amount" label="Amount" className="numeric" />
              </tr>
            </thead>
            <tbody>
              {sortedVouchers.length > 0 ? (
                sortedVouchers.map((voucher) => (
                  <tr key={voucher.voucher_id} data-testid={`sales-row-${voucher.voucher_id}`}>
                    <td>
                      <button
                        onClick={() => setSelectedVoucher(voucher.voucher_id)}
                        className="font-medium text-[#2563EB] hover:text-[#1D4ED8] hover:underline cursor-pointer transition-colors"
                        data-testid={`voucher-link-${voucher.voucher_id}`}
                      >
                        {voucher.voucher_id}
                      </button>
                    </td>
                    <td>
                      <div className="flex items-center gap-2">
                        <Calendar size={14} className="text-slate-400" />
                        {voucher.voucher_date}
                      </div>
                    </td>
                    <td>{voucher.party_name}</td>
                    <td className="text-slate-500 text-sm">
                      {voucher.items?.length > 0 ? `${voucher.items.length} item${voucher.items.length > 1 ? 's' : ''}` : '-'}
                    </td>
                    <td className="text-slate-500">{voucher.reference_number || '-'}</td>
                    <td className="numeric font-semibold text-[#2563EB]">
                      Rs.{(voucher.total_amount || 0).toLocaleString('en-IN')}
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan="6" className="text-center py-8 text-slate-500">No sales vouchers found</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      <div className="text-sm text-slate-500">
        Showing {vouchers.length} vouchers
      </div>

      {selectedVoucher && (
        <InvoiceModal voucherId={selectedVoucher} onClose={() => setSelectedVoucher(null)} />
      )}
    </div>
  );
};

export default Sales;
