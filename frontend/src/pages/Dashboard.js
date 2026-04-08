import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Package, TrendingUp, AlertCircle, Activity, RefreshCw, Bell, Calendar, Clock } from 'lucide-react';
import { useSyncWebSocket } from '../hooks/useSyncWebSocket';
import SyncStatusBar from '../components/SyncStatusBar';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const Dashboard = ({ selectedFY }) => {
  const [inventorySummary, setInventorySummary] = useState(null);
  const [salesSummary, setSalesSummary] = useState(null);
  const [reminders, setReminders] = useState(null);
  const [loading, setLoading] = useState(true);
  const [syncStatus, setSyncStatus] = useState(null);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const { isConnected: wsConnected, syncProgress } = useSyncWebSocket();

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
  }, [autoRefresh, selectedFY]);

  const fetchData = async () => {
    setLoading(true);
    try {
      const fyParam = selectedFY ? `?fy=${selectedFY}` : '';
      const [inventoryRes, salesRes] = await Promise.all([
        axios.get(`${API}/inventory/summary${fyParam}`),
        axios.get(`${API}/sales/summary${fyParam}`)
      ]);
      setInventorySummary(inventoryRes.data?.data || null);
      setSalesSummary(salesRes.data?.data || null);
    } catch (error) {
      console.error('Error fetching dashboard data:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchSyncStatus = async () => {
    try {
      const response = await axios.get(`${API}/sync/status`);
      setSyncStatus(response.data?.data || null);
    } catch (error) {
      console.error('Error fetching sync status:', error);
    }
  };

  const fetchReminders = async () => {
    try {
      const response = await axios.get(`${API}/customers/followups/reminders`);
      setReminders(response.data?.data || null);
    } catch (error) {
      console.error('Error fetching reminders:', error);
    }
  };

  const StatCard = ({ title, value, subtitle, icon: Icon, color }) => (
    <div className="bg-white border border-slate-200 rounded-xl p-6 hover:shadow-lg transition-shadow" data-testid={`stat-${title.toLowerCase().replace(/\s+/g, '-')}`}>
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm text-slate-500 mb-1">{title}</p>
          <p className="text-2xl font-bold text-slate-900">{value}</p>
          {subtitle && <p className="text-xs text-slate-400 mt-1">{subtitle}</p>}
        </div>
        <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${color}`}>
          <Icon size={20} />
        </div>
      </div>
    </div>
  );

  return (
    <div className="space-y-6" data-testid="dashboard-page">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Dashboard</h1>
          <p className="text-slate-500 text-sm">
            {syncStatus?.last_sync ? `Last sync: ${new Date(syncStatus.last_sync).toLocaleString()}` : 'Awaiting first sync'}
            {selectedFY && ` | FY ${selectedFY}`}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => { fetchData(); fetchSyncStatus(); fetchReminders(); }}
            className="flex items-center gap-2 px-3 py-2 bg-white border border-slate-200 rounded-lg hover:bg-slate-50 text-sm"
            data-testid="refresh-btn"
          >
            <RefreshCw size={14} /> Refresh
          </button>
          <label className="flex items-center gap-2 text-sm text-slate-600">
            <input type="checkbox" checked={autoRefresh} onChange={e => setAutoRefresh(e.target.checked)} className="rounded" />
            Auto-refresh
          </label>
        </div>
      </div>

      {/* Live Sync Status Bar */}
      {(syncProgress?.isSyncing || syncProgress?.phase) && (
        <div data-testid="live-sync-status">
          <SyncStatusBar wsConnected={wsConnected} syncProgress={syncProgress} />
        </div>
      )}

      {/* Reminder Banner */}
      {reminders?.today_count > 0 && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 flex items-center gap-3" data-testid="reminder-banner">
          <Bell size={20} className="text-amber-600" />
          <div>
            <p className="font-medium text-amber-900">{reminders.today_count} follow-up{reminders.today_count > 1 ? 's' : ''} due today</p>
            <p className="text-sm text-amber-700">{reminders.overdue_count} overdue</p>
          </div>
        </div>
      )}

      {/* Stat Cards */}
      {!loading && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard
            title="Total Sales"
            value={`Rs.${(salesSummary?.total_sales || 0).toLocaleString('en-IN')}`}
            subtitle={`${salesSummary?.total_vouchers || 0} vouchers`}
            icon={TrendingUp}
            color="bg-blue-50 text-blue-600"
          />
          <StatCard
            title="Inventory Items"
            value={inventorySummary?.total_items || 0}
            subtitle={`Value: Rs.${(inventorySummary?.total_value || 0).toLocaleString('en-IN')}`}
            icon={Package}
            color="bg-purple-50 text-purple-600"
          />
          <StatCard
            title="Low Stock"
            value={inventorySummary?.low_stock_items || 0}
            subtitle="Items below reorder level"
            icon={AlertCircle}
            color="bg-red-50 text-red-600"
          />
          <StatCard
            title="FY Sales Value"
            value={`Rs.${(inventorySummary?.fy_sales_value || salesSummary?.total_sales || 0).toLocaleString('en-IN')}`}
            subtitle={selectedFY ? `FY ${selectedFY}` : 'Current FY'}
            icon={Activity}
            color="bg-cyan-50 text-cyan-600"
          />
        </div>
      )}

      {/* Recent Transactions + Top Customers */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Recent 10 Transactions */}
        <div className="bg-white border border-slate-200 rounded-xl p-6" data-testid="recent-transactions">
          <h3 className="text-sm font-semibold text-slate-700 mb-4 flex items-center gap-2">
            <Clock size={16} /> Recent Transactions (Last 10)
          </h3>
          {salesSummary?.recent_vouchers?.length > 0 ? (
            <div className="space-y-3">
              {salesSummary.recent_vouchers.map((v, i) => (
                <div key={i} className="flex justify-between items-center py-2 border-b border-slate-50 last:border-0">
                  <div>
                    <p className="text-sm font-medium text-slate-800">{v.party_name}</p>
                    <p className="text-xs text-slate-400 flex items-center gap-1"><Calendar size={10} />{v.voucher_date}</p>
                  </div>
                  <span className="text-sm font-semibold text-[#2563EB]">Rs.{(v.total_amount || 0).toLocaleString('en-IN')}</span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-slate-400 text-center py-8">No transactions in this FY</p>
          )}
        </div>

        {/* Top 10 Customers */}
        <div className="bg-white border border-slate-200 rounded-xl p-6" data-testid="top-customers">
          <h3 className="text-sm font-semibold text-slate-700 mb-4 flex items-center gap-2">
            <TrendingUp size={16} /> Top Customers
          </h3>
          {salesSummary?.top_customers?.length > 0 ? (
            <div className="space-y-3">
              {salesSummary.top_customers.map((c, i) => (
                <div key={i} className="flex justify-between items-center py-2 border-b border-slate-50 last:border-0">
                  <div className="flex items-center gap-3">
                    <span className="w-6 h-6 rounded-full bg-blue-50 text-blue-600 text-xs flex items-center justify-center font-bold">{i + 1}</span>
                    <p className="text-sm font-medium text-slate-800">{c.name}</p>
                  </div>
                  <span className="text-sm font-semibold text-[#2563EB]">Rs.{(c.total || 0).toLocaleString('en-IN')}</span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-slate-400 text-center py-8">No customer data in this FY</p>
          )}
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
