import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Download, Calendar, User, X, FileText, Package } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

// Invoice Modal
const InvoiceModal = ({ voucherId, onClose }) => {
  const [voucher, setVoucher] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchDetail = async () => {
      try {
        const res = await axios.get(`${API}/sales/vouchers/${encodeURIComponent(voucherId)}`);
        if (res.data?.success) setVoucher(res.data.data);
      } catch (err) {
        console.error('Error fetching voucher detail:', err);
      } finally {
        setLoading(false);
      }
    };
    fetchDetail();
  }, [voucherId]);

  if (loading) {
    return (
      <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" data-testid="invoice-modal-loading">
        <div className="bg-white rounded-xl p-8"><div className="loading-spinner" /></div>
      </div>
    );
  }

  if (!voucher) {
    return (
      <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
        <div className="bg-white rounded-xl p-8">
          <p className="text-stone-600">Voucher not found</p>
          <button onClick={onClose} className="mt-4 btn-primary px-4 py-2 text-sm">Close</button>
        </div>
      </div>
    );
  }

  const items = voucher.items || [];
  const subtotal = items.reduce((sum, it) => sum + (it.amount || it.quantity * it.rate || 0), 0);

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4" data-testid="invoice-modal">
      <div className="bg-white rounded-xl w-full max-w-2xl max-h-[85vh] overflow-y-auto shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-stone-200 bg-stone-50 rounded-t-xl">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-[#064E3B] rounded-lg flex items-center justify-center">
              <FileText className="text-white" size={20} />
            </div>
            <div>
              <h3 className="text-lg font-semibold text-stone-900" data-testid="invoice-title">
                Invoice #{voucher.voucher_id}
              </h3>
              <p className="text-xs text-stone-500">Sales Voucher</p>
            </div>
          </div>
          <button onClick={onClose} className="text-stone-400 hover:text-stone-700 p-1" data-testid="close-invoice-modal">
            <X size={20} />
          </button>
        </div>

        {/* Invoice Details */}
        <div className="px-6 py-4">
          <div className="grid grid-cols-2 gap-4 mb-6">
            <div>
              <p className="text-xs text-stone-500 uppercase tracking-wide">Customer</p>
              <p className="text-sm font-semibold text-stone-900 mt-1" data-testid="invoice-party">{voucher.party_name}</p>
            </div>
            <div className="text-right">
              <p className="text-xs text-stone-500 uppercase tracking-wide">Date</p>
              <p className="text-sm font-medium text-stone-900 mt-1" data-testid="invoice-date">{voucher.voucher_date}</p>
            </div>
            {voucher.reference_number && (
              <div>
                <p className="text-xs text-stone-500 uppercase tracking-wide">Reference</p>
                <p className="text-sm text-stone-700 mt-1">{voucher.reference_number}</p>
              </div>
            )}
            {voucher.salesman && (
              <div className="text-right">
                <p className="text-xs text-stone-500 uppercase tracking-wide">Salesman</p>
                <p className="text-sm text-stone-700 mt-1">{voucher.salesman}</p>
              </div>
            )}
          </div>

          {/* Line Items */}
          {items.length > 0 ? (
            <div className="border border-stone-200 rounded-lg overflow-hidden mb-4">
              <table className="w-full text-sm" data-testid="invoice-items-table">
                <thead>
                  <tr className="bg-stone-50 border-b border-stone-200">
                    <th className="text-left px-4 py-3 text-xs font-semibold text-stone-600 uppercase">#</th>
                    <th className="text-left px-4 py-3 text-xs font-semibold text-stone-600 uppercase">Item</th>
                    <th className="text-right px-4 py-3 text-xs font-semibold text-stone-600 uppercase">Qty</th>
                    <th className="text-right px-4 py-3 text-xs font-semibold text-stone-600 uppercase">Rate</th>
                    <th className="text-right px-4 py-3 text-xs font-semibold text-stone-600 uppercase">Amount</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((item, idx) => (
                    <tr key={idx} className="border-b border-stone-100 last:border-b-0" data-testid={`invoice-item-${idx}`}>
                      <td className="px-4 py-3 text-stone-500">{idx + 1}</td>
                      <td className="px-4 py-3 font-medium text-stone-900">
                        <div className="flex items-center gap-2">
                          <Package size={14} className="text-stone-400" />
                          {item.item}
                        </div>
                      </td>
                      <td className="px-4 py-3 text-right text-stone-700">{item.quantity || '-'}</td>
                      <td className="px-4 py-3 text-right text-stone-700">
                        {item.rate ? `Rs.${item.rate.toLocaleString('en-IN')}` : '-'}
                      </td>
                      <td className="px-4 py-3 text-right font-medium text-stone-900">
                        Rs.{(item.amount || item.quantity * item.rate || 0).toLocaleString('en-IN')}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="text-center py-6 text-stone-500 text-sm border border-stone-200 rounded-lg mb-4">
              No line items available for this voucher
            </div>
          )}

          {/* Totals */}
          <div className="flex justify-end">
            <div className="w-64 space-y-2">
              {items.length > 0 && subtotal !== voucher.total_amount && (
                <div className="flex justify-between text-sm text-stone-600">
                  <span>Subtotal</span>
                  <span>Rs.{subtotal.toLocaleString('en-IN')}</span>
                </div>
              )}
              <div className="flex justify-between text-base font-bold text-stone-900 border-t border-stone-300 pt-2" data-testid="invoice-total">
                <span>Total Amount</span>
                <span className="text-[#064E3B]">Rs.{(voucher.total_amount || 0).toLocaleString('en-IN')}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

const Sales = ({ selectedFY }) => {
  const [vouchers, setVouchers] = useState([]);
  const [analytics, setAnalytics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [filterParty, setFilterParty] = useState('');
  const [selectedVoucher, setSelectedVoucher] = useState(null);

  useEffect(() => {
    fetchSalesData();
  }, []);

  const fetchSalesData = async () => {
    setLoading(true);
    try {
      const [vouchersRes, analyticsRes] = await Promise.all([
        axios.get(`${API}/sales/vouchers`),
        axios.get(`${API}/sales/analytics`)
      ]);

      setVouchers(vouchersRes.data?.data?.vouchers || []);
      setAnalytics(analyticsRes.data?.data);
    } catch (error) {
      console.error('Error fetching sales data:', error);
    } finally {
      setLoading(false);
    }
  };

  const exportData = async (format) => {
    try {
      const response = await axios.post(
        `${API}/reports/export`,
        { report_type: 'sales', format },
        { responseType: 'blob' }
      );

      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `sales_report.${format}`);
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch (error) {
      console.error('Error exporting data:', error);
    }
  };

  const filteredVouchers = vouchers.filter(v =>
    v.party_name.toLowerCase().includes(filterParty.toLowerCase())
  );

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64" data-testid="sales-loading">
        <div className="loading-spinner" />
        <span className="ml-3 text-stone-600">Loading sales data...</span>
      </div>
    );
  }

  return (
    <div data-testid="sales-page">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-4xl font-light tracking-tight text-stone-900" style={{ fontFamily: 'Outfit, sans-serif' }}>
            Sales
          </h1>
          <p className="mt-2 text-base text-stone-600">Track your sales performance</p>
        </div>
        <div className="flex gap-2">
          <button data-testid="export-sales-pdf-button" onClick={() => exportData('pdf')} className="btn-secondary flex items-center gap-2">
            <Download size={16} /> PDF
          </button>
          <button data-testid="export-sales-excel-button" onClick={() => exportData('excel')} className="btn-secondary flex items-center gap-2">
            <Download size={16} /> Excel
          </button>
          <button data-testid="export-sales-csv-button" onClick={() => exportData('csv')} className="btn-primary flex items-center gap-2">
            <Download size={16} /> CSV
          </button>
        </div>
      </div>

      {analytics?.daily_sales && analytics.daily_sales.length > 0 && (
        <div className="chart-container mb-6" data-testid="sales-chart">
          <h3 className="text-xl font-medium text-stone-900 mb-4" style={{ fontFamily: 'Outfit, sans-serif' }}>
            Sales Trend
          </h3>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={analytics.daily_sales}>
              <CartesianGrid strokeDasharray="3 3" stroke="#E7E5E4" />
              <XAxis dataKey="date" stroke="#78716C" style={{ fontSize: '12px' }} />
              <YAxis stroke="#78716C" style={{ fontSize: '12px' }} />
              <Tooltip contentStyle={{ background: 'white', border: '1px solid #E7E5E4', borderRadius: '8px', padding: '12px' }} />
              <Bar dataKey="amount" fill="#064E3B" radius={[8, 8, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      <div className="bg-white border border-stone-200 rounded-xl p-6 mb-6">
        <div className="relative">
          <User className="absolute left-3 top-1/2 transform -translate-y-1/2 text-stone-400" size={18} />
          <input
            type="text"
            data-testid="filter-party-input"
            placeholder="Filter by customer name..."
            value={filterParty}
            onChange={(e) => setFilterParty(e.target.value)}
            className="w-full pl-10 pr-4 py-2 border border-stone-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#064E3B] focus:border-transparent"
          />
        </div>
      </div>

      <div className="bg-white border border-stone-200 rounded-xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="data-table" data-testid="sales-table">
            <thead>
              <tr>
                <th>Voucher No.</th>
                <th>Date</th>
                <th>Customer</th>
                <th>Items</th>
                <th>Reference</th>
                <th className="numeric">Amount</th>
              </tr>
            </thead>
            <tbody>
              {filteredVouchers.length > 0 ? (
                filteredVouchers.map((voucher) => (
                  <tr key={voucher.voucher_id} data-testid={`sales-row-${voucher.voucher_id}`}>
                    <td>
                      <button
                        onClick={() => setSelectedVoucher(voucher.voucher_id)}
                        className="font-medium text-[#064E3B] hover:text-[#065F46] hover:underline cursor-pointer transition-colors"
                        data-testid={`voucher-link-${voucher.voucher_id}`}
                        title="Click to view invoice"
                      >
                        {voucher.voucher_id}
                      </button>
                    </td>
                    <td>
                      <div className="flex items-center gap-2">
                        <Calendar size={14} className="text-stone-400" />
                        {voucher.voucher_date}
                      </div>
                    </td>
                    <td>{voucher.party_name}</td>
                    <td className="text-stone-500 text-sm">
                      {voucher.items?.length > 0
                        ? `${voucher.items.length} item${voucher.items.length > 1 ? 's' : ''}`
                        : '-'}
                    </td>
                    <td className="text-stone-500">{voucher.reference_number || '-'}</td>
                    <td className="numeric font-semibold text-[#064E3B]">
                      Rs.{(voucher.total_amount || 0).toLocaleString('en-IN')}
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan="6" className="text-center py-8 text-stone-500">
                    No sales vouchers found
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      <div className="mt-4 text-sm text-stone-500">
        Showing {filteredVouchers.length} of {vouchers.length} vouchers
      </div>

      {/* Invoice Detail Modal */}
      {selectedVoucher && (
        <InvoiceModal voucherId={selectedVoucher} onClose={() => setSelectedVoucher(null)} />
      )}
    </div>
  );
};

export default Sales;
