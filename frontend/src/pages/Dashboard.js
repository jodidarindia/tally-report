import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Package, TrendingUp, AlertCircle, Activity, RefreshCw } from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const Dashboard = () => {
  const [inventorySummary, setInventorySummary] = useState(null);
  const [salesSummary, setSalesSummary] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [inventoryRes, salesRes] = await Promise.all([
        axios.get(`${API}/inventory/summary`),
        axios.get(`${API}/sales/summary`)
      ]);

      setInventorySummary(inventoryRes.data?.data);
      setSalesSummary(salesRes.data?.data);
    } catch (error) {
      console.error('Error fetching dashboard data:', error);
    } finally {
      setLoading(false);
    }
  };

  const syncData = async () => {
    try {
      await Promise.all([
        axios.get(`${API}/inventory/items`),
        axios.get(`${API}/sales/vouchers`)
      ]);
      fetchData();
    } catch (error) {
      console.error('Error syncing data:', error);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64" data-testid="dashboard-loading">
        <div className="loading-spinner" />
        <span className="ml-3 text-stone-600">Loading dashboard...</span>
      </div>
    );
  }

  return (
    <div data-testid="dashboard-page">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-4xl font-light tracking-tight text-stone-900" style={{ fontFamily: 'Outfit, sans-serif' }}>
            Dashboard
          </h1>
          <p className="mt-2 text-base text-stone-600">Overview of your Tally data</p>
        </div>
        <button
          data-testid="sync-data-button"
          onClick={syncData}
          className="btn-primary flex items-center gap-2"
        >
          <RefreshCw size={16} />
          Sync Data
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        <div className="stat-card" data-testid="total-items-card">
          <div className="flex items-center justify-between mb-3">
            <div className="w-12 h-12 bg-[#E7F5F0] rounded-lg flex items-center justify-center">
              <Package className="text-[#064E3B]" size={24} />
            </div>
          </div>
          <div className="text-3xl font-semibold text-stone-900">
            {inventorySummary?.total_items || 0}
          </div>
          <div className="text-sm text-stone-500 mt-1">Total Items</div>
        </div>

        <div className="stat-card" data-testid="inventory-value-card">
          <div className="flex items-center justify-between mb-3">
            <div className="w-12 h-12 bg-[#E7F5F0] rounded-lg flex items-center justify-center">
              <TrendingUp className="text-[#064E3B]" size={24} />
            </div>
          </div>
          <div className="text-3xl font-semibold text-stone-900">
            ₹{inventorySummary?.total_value?.toLocaleString('en-IN') || 0}
          </div>
          <div className="text-sm text-stone-500 mt-1">Inventory Value</div>
        </div>

        <div className="stat-card" data-testid="low-stock-card">
          <div className="flex items-center justify-between mb-3">
            <div className="w-12 h-12 bg-[#FEF3E2] rounded-lg flex items-center justify-center">
              <AlertCircle className="text-[#B45309]" size={24} />
            </div>
          </div>
          <div className="text-3xl font-semibold text-stone-900">
            {inventorySummary?.low_stock_items || 0}
          </div>
          <div className="text-sm text-stone-500 mt-1">Low Stock Items</div>
        </div>

        <div className="stat-card" data-testid="total-sales-card">
          <div className="flex items-center justify-between mb-3">
            <div className="w-12 h-12 bg-[#E7F5F0] rounded-lg flex items-center justify-center">
              <Activity className="text-[#064E3B]" size={24} />
            </div>
          </div>
          <div className="text-3xl font-semibold text-stone-900">
            ₹{salesSummary?.total_sales?.toLocaleString('en-IN') || 0}
          </div>
          <div className="text-sm text-stone-500 mt-1">Total Sales</div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white border border-stone-200 rounded-xl p-6">
          <h3 className="text-xl font-medium text-stone-900 mb-4" style={{ fontFamily: 'Outfit, sans-serif' }}>
            Top Customers
          </h3>
          {salesSummary?.top_customers?.length > 0 ? (
            <div className="space-y-3">
              {salesSummary.top_customers.map((customer, index) => (
                <div key={index} className="flex items-center justify-between p-3 bg-[#FDFBF7] rounded-lg">
                  <span className="text-sm font-medium text-stone-700">{customer.name}</span>
                  <span className="text-sm font-semibold text-[#064E3B]">
                    ₹{customer.total.toLocaleString('en-IN')}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-stone-500 text-sm">No customer data available</p>
          )}
        </div>

        <div className="bg-white border border-stone-200 rounded-xl p-6">
          <h3 className="text-xl font-medium text-stone-900 mb-4" style={{ fontFamily: 'Outfit, sans-serif' }}>
            Recent Transactions
          </h3>
          {salesSummary?.recent_vouchers?.length > 0 ? (
            <div className="space-y-3">
              {salesSummary.recent_vouchers.map((voucher, index) => (
                <div key={index} className="flex items-center justify-between p-3 bg-[#FDFBF7] rounded-lg">
                  <div>
                    <div className="text-sm font-medium text-stone-700">{voucher.party_name}</div>
                    <div className="text-xs text-stone-500">{voucher.voucher_date}</div>
                  </div>
                  <span className="text-sm font-semibold text-[#064E3B]">
                    ₹{voucher.total_amount.toLocaleString('en-IN')}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-stone-500 text-sm">No recent transactions</p>
          )}
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
