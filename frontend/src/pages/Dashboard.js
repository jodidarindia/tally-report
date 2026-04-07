import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Package, TrendingUp, AlertCircle, Activity, RefreshCw, Bell, Calendar, Clock } from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const Dashboard = () => {
  const [inventorySummary, setInventorySummary] = useState(null);
  const [salesSummary, setSalesSummary] = useState(null);
  const [reminders, setReminders] = useState(null);
  const [loading, setLoading] = useState(true);
  const [syncStatus, setSyncStatus] = useState(null);
  const [autoRefresh, setAutoRefresh] = useState(true);

  useEffect(() => {
    fetchData();
    fetchSyncStatus();
    fetchReminders();

    let intervalId;
    if (autoRefresh) {
      intervalId = setInterval(() => {
        fetchData();
        fetchSyncStatus();
        fetchReminders();
      }, 30000);
    }

    return () => { if (intervalId) clearInterval(intervalId); };
  }, [autoRefresh]);

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

  const fetchSyncStatus = async () => {
    try {
      const response = await axios.get(`${API}/sync/status`);
      setSyncStatus(response.data?.data);
    } catch (error) {
      console.error('Error fetching sync status:', error);
    }
  };

  const fetchReminders = async () => {
    try {
      const response = await axios.get(`${API}/dashboard/reminders`);
      setReminders(response.data?.data);
    } catch (error) {
      console.error('Error fetching reminders:', error);
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

  const hasReminders = reminders && (reminders.overdue_count > 0 || reminders.today_count > 0 || reminders.upcoming?.length > 0);

  return (
    <div data-testid="dashboard-page">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-4xl font-light tracking-tight text-stone-900" style={{ fontFamily: 'Outfit, sans-serif' }}>
            Dashboard
          </h1>
          <div className="flex items-center gap-4 mt-2">
            <p className="text-base text-stone-600">Overview of your Tally data</p>
            {syncStatus?.last_sync && (
              <div className="flex items-center gap-2 text-sm text-stone-500">
                <Activity size={14} />
                Last sync: {new Date(syncStatus.last_sync).toLocaleTimeString()}
              </div>
            )}
          </div>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => setAutoRefresh(!autoRefresh)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              autoRefresh
                ? 'bg-[#E7F5F0] text-[#064E3B] border border-[#064E3B]'
                : 'bg-white border border-stone-200 text-stone-600 hover:bg-stone-50'
            }`}
            data-testid="auto-refresh-toggle"
          >
            {autoRefresh ? 'Auto-refresh ON' : 'Auto-refresh OFF'}
          </button>
          <button
            data-testid="sync-data-button"
            onClick={syncData}
            className="btn-primary flex items-center gap-2"
          >
            <RefreshCw size={16} />
            Sync Now
          </button>
        </div>
      </div>

      {/* Follow-up Reminders Banner */}
      {hasReminders && (
        <div className="mb-6 bg-white border border-stone-200 rounded-xl overflow-hidden" data-testid="reminders-section">
          <div className="px-6 py-4 flex items-center gap-3 border-b border-stone-100 bg-stone-50">
            <Bell size={20} className="text-[#064E3B]" />
            <h3 className="text-lg font-medium text-stone-900" style={{ fontFamily: 'Outfit, sans-serif' }}>Follow-up Reminders</h3>
            <span className="ml-auto text-sm text-stone-500">{reminders.total_pending} pending</span>
          </div>
          <div className="p-4 space-y-2">
            {/* Overdue */}
            {reminders.overdue?.map((f, idx) => (
              <div key={`o-${idx}`} className="flex items-center gap-4 px-4 py-3 bg-red-50 border border-red-200 rounded-lg" data-testid={`reminder-overdue-${idx}`}>
                <div className="w-2 h-2 rounded-full bg-red-500 flex-shrink-0" />
                <div className="flex-1">
                  <span className="font-medium text-stone-900">{f.customer_name}</span>
                  <span className="text-sm text-red-600 ml-3">OVERDUE</span>
                </div>
                <div className="flex items-center gap-2 text-sm text-stone-500">
                  <Calendar size={14} />
                  {new Date(f.followup_date).toLocaleDateString()}
                </div>
                <span className="px-2 py-0.5 rounded text-xs bg-stone-100 text-stone-600 capitalize">{f.followup_type}</span>
              </div>
            ))}
            {/* Today */}
            {reminders.today?.map((f, idx) => (
              <div key={`t-${idx}`} className="flex items-center gap-4 px-4 py-3 bg-amber-50 border border-amber-200 rounded-lg" data-testid={`reminder-today-${idx}`}>
                <div className="w-2 h-2 rounded-full bg-amber-500 flex-shrink-0" />
                <div className="flex-1">
                  <span className="font-medium text-stone-900">{f.customer_name}</span>
                  <span className="text-sm text-amber-600 ml-3">Today</span>
                </div>
                <div className="flex items-center gap-2 text-sm text-stone-500">
                  <Clock size={14} />
                  {new Date(f.followup_date).toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'})}
                </div>
                <span className="px-2 py-0.5 rounded text-xs bg-stone-100 text-stone-600 capitalize">{f.followup_type}</span>
              </div>
            ))}
            {/* Upcoming */}
            {reminders.upcoming?.map((f, idx) => (
              <div key={`u-${idx}`} className="flex items-center gap-4 px-4 py-3 bg-stone-50 border border-stone-200 rounded-lg" data-testid={`reminder-upcoming-${idx}`}>
                <div className="w-2 h-2 rounded-full bg-stone-400 flex-shrink-0" />
                <div className="flex-1">
                  <span className="font-medium text-stone-900">{f.customer_name}</span>
                </div>
                <div className="flex items-center gap-2 text-sm text-stone-500">
                  <Calendar size={14} />
                  {new Date(f.followup_date).toLocaleDateString()}
                </div>
                <span className="px-2 py-0.5 rounded text-xs bg-stone-100 text-stone-600 capitalize">{f.followup_type}</span>
              </div>
            ))}
          </div>
        </div>
      )}

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
            Rs.{inventorySummary?.total_value?.toLocaleString('en-IN') || 0}
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
            Rs.{salesSummary?.total_sales?.toLocaleString('en-IN') || 0}
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
                    Rs.{customer.total.toLocaleString('en-IN')}
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
                    Rs.{voucher.total_amount.toLocaleString('en-IN')}
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
