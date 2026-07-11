import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Package, TrendingUp, AlertCircle, Activity, RefreshCw, Bell, Calendar, Clock, AlertTriangle, ChevronDown, ChevronUp, Phone, Database } from 'lucide-react';
import { useSyncWebSocket } from '../hooks/useSyncWebSocket';
import { useAuth } from '../hooks/useAuth';
import SyncStatusBar from '../components/SyncStatusBar';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const Dashboard = ({ selectedFY, companyId, excludeBranches }) => {
  const [inventorySummary, setInventorySummary] = useState(null);
  const [salesSummary, setSalesSummary] = useState(null);
  const [reminders, setReminders] = useState(null);
  const [overdueDigest, setOverdueDigest] = useState(null);
  const [overdueExpanded, setOverdueExpanded] = useState(false);
  const [loading, setLoading] = useState(true);
  const [syncStatus, setSyncStatus] = useState(null);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const { user } = useAuth();
  // Scope sync events to this tenant — prevents cross-tenant WS leak.
  // Only admins need the live progress feed; employees see only the static
  // "Last sync" stamp, so we skip the WS subscription entirely for them
  // (saves a backend connection per shop-floor login).
  const wsTenant = user?.role === 'admin' ? user?.tenant_id : null;
  const { isConnected: wsConnected, syncProgress } = useSyncWebSocket(wsTenant);

  useEffect(() => {
    fetchData();
    fetchSyncStatus();
    fetchReminders();
    fetchOverdueDigest();

    let intervalId;
    if (autoRefresh) {
      intervalId = setInterval(() => {
        fetchData();
        fetchSyncStatus();
        fetchReminders();
        fetchOverdueDigest();
      }, 30000);
    }

    return () => { if (intervalId) clearInterval(intervalId); };
  }, [autoRefresh, selectedFY, excludeBranches, companyId]);

  const fetchData = async () => {
    setLoading(true);
    try {
      const fyParam = selectedFY ? `?fy=${selectedFY}` : '';
      const [inventoryRes, salesRes, allSalesRes] = await Promise.all([
        axios.get(`${API}/inventory/summary${fyParam}`),
        axios.get(`${API}/sales/summary${fyParam}`),
        axios.get(`${API}/sales/summary`)  // All FYs combined
      ]);
      setInventorySummary(inventoryRes.data?.data || null);
      const salesData = salesRes.data?.data || null;
      const allSalesData = allSalesRes.data?.data || {};
      // Attach all-FY totals to sales summary
      if (salesData) {
        salesData.all_fy_total_sales = allSalesData.total_sales || 0;
        salesData.all_fy_total_vouchers = allSalesData.total_vouchers || 0;
      }
      setSalesSummary(salesData);
    } catch (error) {
      console.error('Error fetching dashboard data:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchSyncStatus = async () => {
    try {
      const [syncRes, tallyRes] = await Promise.all([
        axios.get(`${API}/sync/status`).catch(() => null),
        axios.get(`${API}/tally/status`).catch(() => null)
      ]);
      const syncData = syncRes?.data?.data || {};
      const tallyData = tallyRes?.data?.data || {};
      // Use the most recent sync time from either source
      const syncTime = syncData.last_sync || '';
      const tallyTime = tallyData.last_sync || '';
      const latestSync = syncTime > tallyTime ? syncTime : tallyTime;
      setSyncStatus({
        ...syncData,
        last_sync: latestSync || syncData.last_sync,
        company_name: tallyData.company_name || syncData.company_name
      });
    } catch (error) {
      console.error('Error fetching sync status:', error);
    }
  };

  const fetchReminders = async () => {
    try {
      const response = await axios.get(`${API}/dashboard/reminders`);
      setReminders(response.data?.data || null);
    } catch (error) {
      console.error('Error fetching reminders:', error);
    }
  };

  const fetchOverdueDigest = async () => {
    try {
      const response = await axios.get(`${API}/dashboard/overdue-digest`);
      setOverdueDigest(response.data?.data || null);
    } catch (error) {
      console.error('Error fetching overdue digest:', error);
    }
  };

  // eslint-disable-next-line react/no-unstable-nested-components
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
            {(() => {
              const hasData = (salesSummary?.total_sales || 0) > 0 || (inventorySummary?.total_items || 0) > 0;
              if (!syncStatus?.last_sync) return 'Awaiting first sync';
              if (!hasData) return `No data found for FY ${selectedFY || ''}`;
              const rawSync = syncStatus.last_sync;
              // Normalize: if no timezone marker, treat as UTC
              const syncDate = rawSync.includes('+') || rawSync.includes('Z') || rawSync.endsWith('00:00')
                ? new Date(rawSync)
                : new Date(rawSync + 'Z');
              return `Last sync: ${syncDate.toLocaleString('en-IN', { timeZone: 'Asia/Kolkata' })} IST`;
            })()}
            {selectedFY && ` | FY ${selectedFY}`}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => { fetchData(); fetchSyncStatus(); fetchReminders(); fetchOverdueDigest(); }}
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

      {/* Live Sync Status Bar — admin-only. Employees (employee/dispatch/
          salesman) only see the static "Last sync: ..." stamp in the header
          above; the live progress UI is admin-only to avoid noise on shop-
          floor logins. */}
      {user?.role === 'admin' && (syncProgress?.isSyncing || syncProgress?.phase) && (
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

      {/* Not Synced / No Data Banner */}
      {!loading && (
        <>
          {!syncStatus?.last_sync && (salesSummary?.total_sales || 0) === 0 && (inventorySummary?.total_items || 0) === 0 && (
            <div className="bg-amber-50 border border-amber-200 rounded-xl p-6 text-center" data-testid="not-synced-banner">
              <Database size={28} className="mx-auto text-amber-500 mb-3" />
              <h3 className="text-lg font-semibold text-amber-900 mb-1">Data Not Synced Yet</h3>
              <p className="text-sm text-amber-700 mb-3">Your data has not been synced from Tally* yet. Please download and run the FLOWRA Desktop Agent to connect with Tally*.</p>
              <p className="text-xs text-amber-600">Go to <strong>Setup</strong> menu to configure your Tally* connection and download the Desktop Agent.</p>
            </div>
          )}
          {syncStatus?.last_sync && (salesSummary?.total_sales || 0) === 0 && (inventorySummary?.total_items || 0) === 0 && (
            <div className="bg-blue-50 border border-blue-200 rounded-xl p-6 text-center" data-testid="no-data-banner">
              <Database size={28} className="mx-auto text-blue-500 mb-3" />
              <h3 className="text-lg font-semibold text-blue-900 mb-1">No Data Available for FY {selectedFY}</h3>
              <p className="text-sm text-blue-700 mb-3">No transactions were found for the selected financial year. This could mean:</p>
              <ul className="text-sm text-blue-700 text-left max-w-md mx-auto space-y-1 mb-3">
                <li>- The selected FY has no transactions in Tally*</li>
                <li>- Data for this FY has not been synced yet from the Desktop Agent</li>
                <li>- The company was not active during this financial year</li>
              </ul>
              <p className="text-xs text-blue-600">Try selecting a different financial year from the dropdown above, or run a fresh sync from the FLOWRA Desktop Agent.</p>
            </div>
          )}
        </>
      )}

      {/* Stat Cards */}
      {!loading && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard
            title="Total Sales"
            value={`Rs.${(salesSummary?.all_fy_total_sales || salesSummary?.total_sales || 0).toLocaleString('en-IN')}`}
            subtitle={`${salesSummary?.all_fy_total_vouchers || salesSummary?.total_vouchers || 0} vouchers (All FYs)`}
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
            subtitle="Out-of-stock or below reorder"
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

      {/* Overdue Digest (55+ days) */}
      {overdueDigest && overdueDigest.total_overdue_invoices > 0 && (
        <div className="bg-white border border-red-200 rounded-xl overflow-hidden" data-testid="overdue-digest">
          <div
            className="flex items-center justify-between p-5 cursor-pointer hover:bg-red-50/40 transition-colors"
            onClick={() => setOverdueExpanded(!overdueExpanded)}
            data-testid="overdue-digest-header"
          >
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-red-50 flex items-center justify-center">
                <AlertTriangle size={20} className="text-red-600" />
              </div>
              <div>
                <h3 className="text-sm font-semibold text-slate-900">
                  Overdue Payments ({overdueDigest.total_overdue_invoices} invoices)
                </h3>
                <p className="text-xs text-slate-500">
                  {overdueDigest.total_customers_overdue} customers with invoices older than {overdueDigest.threshold_days} days
                </p>
              </div>
            </div>
            <div className="flex items-center gap-4">
              <span className="text-lg font-bold text-red-600" data-testid="overdue-total-amount">
                Rs.{(overdueDigest.total_overdue_amount || 0).toLocaleString('en-IN')}
              </span>
              {overdueExpanded ? <ChevronUp size={18} className="text-slate-400" /> : <ChevronDown size={18} className="text-slate-400" />}
            </div>
          </div>

          {overdueExpanded && (
            <div className="border-t border-red-100">
              {/* Customer Summary */}
              <div className="p-5 pb-3">
                <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">Customer-wise Overdue</h4>
                <div className="space-y-2">
                  {overdueDigest.customer_summary?.map((c, i) => (
                    <div key={i} className="flex items-center justify-between py-2 px-3 rounded-lg bg-slate-50/70 hover:bg-slate-100/70 transition-colors" data-testid={`overdue-customer-${i}`}>
                      <div className="flex items-center gap-3">
                        <span className="w-6 h-6 rounded-full bg-red-100 text-red-700 text-xs flex items-center justify-center font-bold">{i + 1}</span>
                        <div>
                          <p className="text-sm font-medium text-slate-800">{c.customer_name}</p>
                          <p className="text-xs text-slate-400">{c.invoice_count} invoice{c.invoice_count > 1 ? 's' : ''} | Oldest: {c.oldest_days} days</p>
                        </div>
                      </div>
                      <div className="flex items-center gap-3">
                        {c.phone && (
                          <a href={`tel:${c.phone}`} className="text-slate-400 hover:text-blue-500" title={c.phone}>
                            <Phone size={14} />
                          </a>
                        )}
                        <span className="text-sm font-semibold text-red-600">Rs.{(c.total_overdue || 0).toLocaleString('en-IN')}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Invoice Detail Table */}
              {overdueDigest.overdue_invoices?.length > 0 && (
                <div className="p-5 pt-2">
                  <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">Invoice Details (Top {Math.min(overdueDigest.overdue_invoices.length, 50)})</h4>
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="text-left text-xs text-slate-500 uppercase border-b border-slate-200">
                          <th className="pb-2 pr-4 font-medium">Invoice</th>
                          <th className="pb-2 pr-4 font-medium">Customer</th>
                          <th className="pb-2 pr-4 font-medium">Date</th>
                          <th className="pb-2 pr-4 font-medium text-right">Amount</th>
                          <th className="pb-2 pr-4 font-medium text-right">Paid</th>
                          <th className="pb-2 pr-4 font-medium text-right">Overdue</th>
                          <th className="pb-2 font-medium text-right">Days</th>
                        </tr>
                      </thead>
                      <tbody>
                        {overdueDigest.overdue_invoices.map((inv, i) => (
                          <tr key={i} className="border-b border-slate-50 hover:bg-slate-50/50" data-testid={`overdue-invoice-${i}`}>
                            <td className="py-2 pr-4 text-slate-700 font-mono text-xs">{inv.reference_number || inv.voucher_id}</td>
                            <td className="py-2 pr-4 text-slate-700">{inv.party_name}</td>
                            <td className="py-2 pr-4 text-slate-500">{inv.voucher_date}</td>
                            <td className="py-2 pr-4 text-right text-slate-700">Rs.{(inv.invoice_amount || 0).toLocaleString('en-IN')}</td>
                            <td className="py-2 pr-4 text-right text-green-600">Rs.{(inv.paid_amount || 0).toLocaleString('en-IN')}</td>
                            <td className="py-2 pr-4 text-right font-semibold text-red-600">Rs.{(inv.overdue_amount || 0).toLocaleString('en-IN')}</td>
                            <td className="py-2 text-right">
                              <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${
                                inv.days_overdue > 120 ? 'bg-red-100 text-red-700' :
                                inv.days_overdue > 90 ? 'bg-orange-100 text-orange-700' :
                                'bg-amber-100 text-amber-700'
                              }`}>
                                {inv.days_overdue}d
                              </span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* Last computed timestamp */}
              {overdueDigest.computed_at && (
                <div className="px-5 pb-4 text-xs text-slate-400 text-right">
                  Last computed: {(() => { const r = overdueDigest.computed_at; const d = (r.includes('+') || r.includes('Z')) ? new Date(r) : new Date(r + 'Z'); return d.toLocaleString('en-IN', { timeZone: 'Asia/Kolkata' }); })()}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Empty overdue state */}
      {overdueDigest && overdueDigest.total_overdue_invoices === 0 && (
        <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-4 flex items-center gap-3" data-testid="no-overdue-banner">
          <div className="w-8 h-8 rounded-lg bg-emerald-100 flex items-center justify-center">
            <Activity size={16} className="text-emerald-600" />
          </div>
          <p className="text-sm text-emerald-800 font-medium">No overdue payments! All invoices within 55-day window.</p>
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

      {/* Updates & Changelog */}
      <div className="mt-6 bg-white rounded-xl border border-slate-200 overflow-hidden" data-testid="dashboard-updates">
        <div className="px-4 py-3 border-b border-slate-100 flex items-center gap-2">
          <Bell size={14} className="text-blue-600" />
          <h3 className="text-sm font-semibold text-slate-900">FLOWRA Updates</h3>
        </div>
        <div className="max-h-48 sm:max-h-56 overflow-y-auto divide-y divide-slate-50">
          {[
            { d: '2026-07-11', tag: 'FIX', tagColor: '#ef4444', title: 'Busy Sync Agent v1.3.1', desc: 'pyodbc bundled + Busy DB password fallback chain (Busy 21/18/older) + BUSY_DB_PASSWORD override field in Settings.' },
            { d: '2026-07-08', tag: 'FIX', tagColor: '#ef4444', title: 'Tally Agent v9.8.30 — Forward-Dated Voucher Fix', desc: 'Quick-sync window now extends to today, not stops at stored LVD. Reconcile is date-scoped — prevents mass deletions when a voucher is added with a future date.' },
            { d: '2026-07-08', tag: 'NEW', tagColor: '#8b5cf6', title: 'Busy Sync Agent v1.2 — Full Tally Parity', desc: 'Complete 1:1 Tally clone GUI: 4 connectivity cards, Sync Status panel, Subscription block with Request Renewal, auto-detect companies + FYs on folder pick.' },
            { d: '2026-07-08', tag: 'NEW', tagColor: '#8b5cf6', title: 'Investor Pitch Kit', desc: '16-page pitch PDF + 10-page cold-email teaser + editable Excel projection model. Auto-generated from a single source of truth.' },
            { d: '2026-07-05', tag: 'NEW', tagColor: '#8b5cf6', title: 'Tally Agent v9.8.29 — LVD & AlterID Persist', desc: 'Per-company LVD + AlterID + timestamp saved to disk. 7-day full-sync skip window if AlterID unchanged.' },
            { d: '2026-07-02', tag: 'NEW', tagColor: '#8b5cf6', title: 'Marketing Kit', desc: 'Auto-generated pitch decks (detailed + pointers), print-ready visiting cards (front/back QR), Tally-vs-Busy-vs-FLOWRA comparison charts.' },
            { d: '2026-06-30', tag: 'FIX', tagColor: '#ef4444', title: 'Inventory Export Bugs', desc: 'CSV/Excel list→string coercion, PDF payload updates, multi-group filter fix. All export formats now handle nested product data correctly.' },
            { d: '2026-06-25', tag: 'NEW', tagColor: '#8b5cf6', title: 'Beat Run — Mandatory Order/Payment + Close Day', desc: 'Yes/No flags on every stop. Unplanned existing-customer dropdown. End-of-Day PDF & Excel with breakdown by salesman.' },
            { d: '2026-06-20', tag: 'NEW', tagColor: '#8b5cf6', title: 'Salesman Copy-From', desc: 'One-click copy of another salesman\'s customer mapping + beat plan. Speeds up new-hire onboarding by ~90%.' },
            { d: '2026-06-15', tag: 'NEW', tagColor: '#8b5cf6', title: 'Employee Active/Deactivate Toggle', desc: 'Deactivate a user without deleting audit history. Deactivated users lose login but their data + reports remain intact.' },
            { d: '2026-06-01', tag: 'NEW', tagColor: '#8b5cf6', title: 'Tally Agent v9.8.28 — SVCurrentCompany Fix', desc: 'Fixed XML header format that some Tally builds rejected. Zero errors on 5,000+ voucher syncs after fix.' },
            { d: '2026-05-10', tag: 'NEW', tagColor: '#8b5cf6', title: 'Cancel Dispatch Cards', desc: 'Cancel a card up to the Packed lane with a reason; cancelled cards strikethrough until end-of-day, then auto-archive.' },
            { d: '2026-05-10', tag: 'NEW', tagColor: '#8b5cf6', title: 'Tally Invoice Drift Detection', desc: 'Cards now auto-flag (amber/red badge) when the source Tally invoice is modified or deleted after sync — no silent drift.' },
            { d: '2026-05-09', tag: 'NEW', tagColor: '#8b5cf6', title: 'Fuzzy Search Everywhere', desc: '"tvs 10" now finds "TVS-10", "TVS(10)", "TVS/10". Spaces and separators (- / ( ) ! : . , & _) ignored across all search boxes.' },
            { d: '2026-05-08', tag: 'IMPROVE', tagColor: '#0891b2', title: 'SPIP — 12-Month Rolling Window', desc: 'Added rolling 12-month fallback and a "No Movement" bucket for idle items. Aliases included in global search.' },
            { d: '2026-05-07', tag: 'FIX', tagColor: '#ef4444', title: 'SPIP & YoY Limits Removed', desc: 'Lifted the 5,000-row cap so all items surface in SPIP. Cross-FY YoY sales comparison + forecast tables added.' },
            { d: '2026-05-05', tag: 'IMPROVE', tagColor: '#0891b2', title: 'Mobile Performance', desc: 'Server-side pagination + render caps for Inventory and Customer CRM. Tally API delay 2s → 0.5s. New compound DB indexes.' },
            { d: '2026-05-03', tag: 'NEW', tagColor: '#8b5cf6', title: 'Tally Agent v9.8.7', desc: 'Standard price via STANDARDPRICELIST, root-group hierarchy, and item alias (LANGUAGENAME) extraction.' },
            { d: '2026-05-01', tag: 'FIX', tagColor: '#ef4444', title: 'CA Corner BS & P&L Parity', desc: 'Fixed Assets, Sundry Debtors and Creditors re-mapped via root-group hierarchy. Removed double-counting of Stock-in-Hand.' },
            { d: '2026-04-28', tag: 'NEW', tagColor: '#8b5cf6', title: 'Beat Run Monthly Report', desc: 'Salesman beat coverage and visit summary, exportable to Excel.' },
            { d: '2026-04-23', tag: 'NEW', tagColor: '#8b5cf6', title: 'Dispatch Terminal', desc: 'Kanban board, LR tracking, document uploads, porter settlement.' },
            { d: '2026-04-16', tag: 'FIX', tagColor: '#ef4444', title: 'Outstanding Calculation Fixed', desc: 'Opening balances per FY and journal voucher party amounts corrected.' },
            { d: '2026-04-10', tag: 'NEW', tagColor: '#8b5cf6', title: 'Desktop Agent v9', desc: 'Deletion reconciliation, command queue, dual-schedule syncing.' },
            { d: '2026-04-08', tag: 'NEW', tagColor: '#8b5cf6', title: 'CRM Targets Overhaul', desc: 'Bulk targets, customer removal/reactivation, read-only past FYs.' },
            { d: '2026-04-05', tag: 'NEW', tagColor: '#8b5cf6', title: 'Digital Questionnaire', desc: 'Public customer forms with SuperAdmin leads and Excel export.' },
          ].map((u, i) => (
            <div key={i} className="px-4 py-2.5 flex items-start gap-3 hover:bg-slate-25 transition" data-testid={`update-${i}`}>
              <span className="text-[9px] font-bold px-1.5 py-0.5 rounded mt-0.5 flex-shrink-0" style={{ background: u.tagColor + '15', color: u.tagColor }}>{u.tag}</span>
              <div className="min-w-0 flex-1">
                <div className="text-xs font-semibold text-slate-900">{u.title}</div>
                <div className="text-[10px] text-slate-500 leading-relaxed">{u.desc}</div>
              </div>
              <span className="text-[9px] text-slate-400 flex-shrink-0 mt-0.5">{u.d}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
