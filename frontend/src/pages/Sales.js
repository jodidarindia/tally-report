import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Download, Calendar, User } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const Sales = () => {
  const [vouchers, setVouchers] = useState([]);
  const [analytics, setAnalytics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [filterParty, setFilterParty] = useState('');

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
          <button
            data-testid="export-sales-pdf-button"
            onClick={() => exportData('pdf')}
            className="btn-secondary flex items-center gap-2"
          >
            <Download size={16} />
            PDF
          </button>
          <button
            data-testid="export-sales-excel-button"
            onClick={() => exportData('excel')}
            className="btn-secondary flex items-center gap-2"
          >
            <Download size={16} />
            Excel
          </button>
          <button
            data-testid="export-sales-csv-button"
            onClick={() => exportData('csv')}
            className="btn-primary flex items-center gap-2"
          >
            <Download size={16} />
            CSV
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
              <Tooltip
                contentStyle={{
                  background: 'white',
                  border: '1px solid #E7E5E4',
                  borderRadius: '8px',
                  padding: '12px'
                }}
              />
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
                <th>Voucher ID</th>
                <th>Date</th>
                <th>Customer</th>
                <th>Reference</th>
                <th className="numeric">Amount</th>
              </tr>
            </thead>
            <tbody>
              {filteredVouchers.length > 0 ? (
                filteredVouchers.map((voucher) => (
                  <tr key={voucher.voucher_id} data-testid={`sales-row-${voucher.voucher_id}`}>
                    <td className="font-medium text-stone-900">{voucher.voucher_id}</td>
                    <td>
                      <div className="flex items-center gap-2">
                        <Calendar size={14} className="text-stone-400" />
                        {voucher.voucher_date}
                      </div>
                    </td>
                    <td>{voucher.party_name}</td>
                    <td className="text-stone-500">{voucher.reference_number || '-'}</td>
                    <td className="numeric font-semibold text-[#064E3B]">
                      ₹{voucher.total_amount.toLocaleString('en-IN')}
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan="5" className="text-center py-8 text-stone-500">
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
    </div>
  );
};

export default Sales;
