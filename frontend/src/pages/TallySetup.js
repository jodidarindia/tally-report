import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { CheckCircle, XCircle, Settings as SettingsIcon, Wifi, WifiOff, Clock, Monitor, Building2, RefreshCw, Download, Trash2, RotateCcw, AlertTriangle, ArrowUpCircle } from 'lucide-react';
import { toast } from 'sonner';
import CreditorGroupsPanel from '../components/CreditorGroupsPanel';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

// Compare two semver-ish version strings. Returns true if a < b.
const verLT = (a, b) => {
  const parse = (v) => String(v || '0').replace(/^v/, '').split('.').map((seg) => {
    const m = String(seg).match(/^\d+/);
    return m ? parseInt(m[0], 10) : 0;
  });
  const pa = parse(a); const pb = parse(b);
  for (let i = 0; i < Math.max(pa.length, pb.length); i++) {
    const x = pa[i] || 0; const y = pb[i] || 0;
    if (x !== y) return x < y;
  }
  return false;
};

const TallySetup = ({ companyId }) => {
  const [connectionType, setConnectionType] = useState('xml');
  const [host, setHost] = useState('localhost');
  const [port, setPort] = useState('9000');
  const [apiKey, setApiKey] = useState('');
  const [isConnected, setIsConnected] = useState(false);
  const [loading, setLoading] = useState(false);
  const [checking, setChecking] = useState(true);
  const [syncStatus, setSyncStatus] = useState(null);
  const [confirmAction, setConfirmAction] = useState(null); // {type: 'resync'|'delete', company}
  const [actionLoading, setActionLoading] = useState(false);
  const [latestRelease, setLatestRelease] = useState(null);
  // v9.8.24 — guard the .exe download behind a "quit running agent" modal.
  const [showDownloadModal, setShowDownloadModal] = useState(false);

  useEffect(() => {
    checkStatus();
    fetchSyncStatus();
    fetchLatestRelease();
    // Recheck the agent release manifest every 24 hours while this tab
    // stays open. The endpoint is read-only and cached server-side.
    const id = setInterval(fetchLatestRelease, 24 * 60 * 60 * 1000);
    return () => clearInterval(id);
  }, []);

  const fetchLatestRelease = async () => {
    try {
      const r = await axios.get(`${API}/agent/latest-version`);
      if (r.data?.success) setLatestRelease(r.data.data);
    } catch (_) {
      // Silent — never block the page if release manifest is unreachable.
    }
  };

  const checkStatus = async () => {
    setChecking(true);
    try {
      const response = await axios.get(`${API}/tally/status`);
      setIsConnected(response.data?.data?.is_connected || false);
    } catch (error) {
      console.error('Error checking status:', error);
    } finally {
      setChecking(false);
    }
  };

  const fetchSyncStatus = async () => {
    try {
      const token = localStorage.getItem('flowra_token');
      const response = await axios.get(`${API}/sync/connection-status`, {
        headers: { Authorization: `Bearer ${token}`, 'X-Company-ID': companyId || '' }
      });
      if (response.data?.success) {
        setSyncStatus(response.data.data);
      }
    } catch (error) {
      console.error('Error fetching sync status:', error);
    }
  };

  const handleConnect = async (e) => {
    e.preventDefault();
    setLoading(true);

    try {
      const payload = {
        connection_type: connectionType,
        host: connectionType === 'xml' ? host : undefined,
        port: connectionType === 'xml' ? parseInt(port) : undefined,
        api_key: connectionType === 'rest' ? apiKey : undefined
      };

      const response = await axios.post(`${API}/tally/connect`, payload);

      if (response.data?.success) {
        setIsConnected(true);
        toast.success('Successfully connected to Tally*!');
      } else {
        toast.error(response.data?.error || 'Connection failed');
      }
    } catch (error) {
      console.error('Error connecting:', error);
      toast.error('Failed to connect to Tally*');
    } finally {
      setLoading(false);
    }
  };

  const handleCompanyAction = async () => {
    if (!confirmAction) return;
    const { type, company } = confirmAction;
    setActionLoading(true);
    try {
      const res = await axios.post(`${API}/agent/commands`, {
        action: type,
        company_id: company.company_id,
        company_name: company.company_name,
      });
      if (res.data?.success) {
        if (type === 'delete') {
          toast.success(`${company.company_name} deleted. Agent will stop syncing this company.`);
        } else {
          toast.success(`Resync queued for ${company.company_name}. Run Desktop Agent to sync fresh.`);
        }
        fetchSyncStatus();
      } else {
        toast.error(res.data?.error || 'Action failed');
      }
    } catch (err) {
      toast.error(err.response?.data?.error || 'Action failed');
    } finally {
      setActionLoading(false);
      setConfirmAction(null);
    }
  };

  if (checking) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="loading-spinner" />
        <span className="ml-3 text-slate-600">Checking connection...</span>
      </div>
    );
  }

  return (
    <div data-testid="setup-page">
      <div className="mb-8">
        <h1 className="text-4xl font-light tracking-tight text-slate-900" style={{ fontFamily: 'Outfit, sans-serif' }}>
          Tally* Setup
        </h1>
        <p className="mt-2 text-base text-slate-600">Configure your Tally* connection</p>
      </div>

      <div className="max-w-2xl space-y-6">
        {/* Desktop Agent Download */}
        <div className="bg-gradient-to-r from-blue-50 to-indigo-50 border border-blue-200 rounded-xl p-6" data-testid="agent-download-card">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 bg-blue-600 rounded-xl flex items-center justify-center flex-shrink-0">
              <Download size={24} className="text-white" />
            </div>
            <div className="flex-1">
              <h2 className="text-base font-semibold text-slate-900">
                FLOWRA Tally Sync Agent (Windows)
                {latestRelease?.version && (
                  <span className="ml-2 inline-block text-[10px] font-semibold bg-blue-600 text-white px-1.5 py-0.5 rounded">
                    v{latestRelease.version}
                  </span>
                )}
              </h2>
              <p className="text-xs text-slate-600 mt-1">
                Latest: v{latestRelease?.version || '9.8.23'} · Native Windows GUI · system tray · auto-start · for Tally Prime on Windows 10/11.
              </p>

              {/* Update banner — visible when the agent currently syncing
                  reports an older version than the latest release. */}
              {latestRelease && syncStatus?.agent_version
                && verLT(syncStatus.agent_version, latestRelease.version) && (
                <div
                  className="mt-3 flex items-start gap-2 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2"
                  data-testid="agent-update-banner"
                >
                  <ArrowUpCircle size={16} className="text-amber-600 mt-0.5 shrink-0" />
                  <div className="flex-1">
                    <div className="text-xs font-semibold text-amber-900">
                      Agent update available — v{syncStatus.agent_version} → v{latestRelease.version}
                    </div>
                    <div className="text-[11px] text-amber-700 mt-0.5">
                      Your desktop agent will offer a one-click update on its
                      next 24-hour check, or open the agent now and click
                      "Update available" in the status bar. Sync data and
                      Tally are not affected.
                    </div>
                  </div>
                </div>
              )}

              <div className="flex flex-wrap items-center gap-3 mt-3">
                <button
                  onClick={() => setShowDownloadModal(true)}
                  className="inline-flex items-center gap-2 bg-blue-600 text-white px-5 py-2.5 rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors"
                  data-testid="download-agent-exe-btn"
                >
                  <Download size={14} /> Download FLOWRA Tally Sync Agent (.exe)
                </button>
                <a
                  href="/docs/FLOWRA_COMPLETE_DOCUMENTATION.pdf"
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-2 text-sm font-medium text-blue-700 hover:text-blue-800"
                  data-testid="agent-docs-link"
                >
                  View full setup guide →
                </a>
              </div>
              <p className="text-[11px] text-slate-500 mt-3">
                Single-file installer for Windows 10/11. No Python or other
                runtime required on the customer's PC — just double-click and run.
                The agent connects to Tally over ODBC port 9000 and syncs only
                the company you choose, encrypted end-to-end.
              </p>
            </div>
          </div>
        </div>

        {/* Connection Status Card */}
        <div className="bg-white border border-slate-200 rounded-xl p-6" data-testid="connection-status-card">
          <div className="flex items-center justify-between mb-5">
            <div className="flex items-center gap-3">
              <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${syncStatus?.last_sync ? 'bg-green-50' : 'bg-slate-100'}`}>
                {syncStatus?.last_sync ? <Wifi size={20} className="text-green-600" /> : <WifiOff size={20} className="text-slate-400" />}
              </div>
              <div>
                <h2 className="text-base font-semibold text-slate-900">Desktop Agent Status</h2>
                <p className="text-xs text-slate-500">Real-time sync connection info</p>
              </div>
            </div>
            <button onClick={fetchSyncStatus} className="p-2 text-slate-400 hover:text-slate-600 hover:bg-slate-50 rounded-lg" data-testid="refresh-sync-status">
              <RefreshCw size={16} />
            </button>
          </div>

          {syncStatus ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="p-3 rounded-lg bg-slate-50">
                <div className="text-xs text-slate-500 flex items-center gap-1 mb-1"><Clock size={12} /> Last Sync</div>
                <div className="text-sm font-medium text-slate-800" data-testid="last-sync-time">
                  {syncStatus.last_sync ? (() => {
                    const raw = syncStatus.last_sync;
                    const d = (raw.includes('+') || raw.includes('Z') || raw.endsWith('00:00'))
                      ? new Date(raw) : new Date(raw + 'Z');
                    return d.toLocaleString('en-IN', { timeZone: 'Asia/Kolkata' });
                  })() : 'Never synced'}
                </div>
              </div>
              <div className="p-3 rounded-lg bg-slate-50">
                <div className="text-xs text-slate-500 flex items-center gap-1 mb-1"><Monitor size={12} /> Agent Version</div>
                <div className="text-sm font-medium text-slate-800 flex items-center gap-2 flex-wrap" data-testid="agent-version">
                  <span>{syncStatus.agent_version || 'Unknown'}</span>
                  {latestRelease && syncStatus.agent_version
                    && verLT(syncStatus.agent_version, latestRelease.version) && (
                    <span
                      className="inline-flex items-center gap-1 bg-amber-100 text-amber-800 border border-amber-200 text-[10px] font-semibold px-1.5 py-0.5 rounded"
                      data-testid="agent-update-pill"
                      title={`Latest is v${latestRelease.version}`}
                    >
                      <ArrowUpCircle size={10} /> update available
                    </span>
                  )}
                </div>
              </div>
              <div className="p-3 rounded-lg bg-slate-50 sm:col-span-2">
                <div className="text-xs text-slate-500 flex items-center gap-1 mb-2"><Building2 size={12} /> Linked Companies</div>
                <div className="space-y-2" data-testid="linked-companies">
                  {syncStatus.companies?.length > 0 ? syncStatus.companies.map((c, i) => {
                    const name = typeof c === 'object' ? (c.company_name || c.company_id || '') : c;
                    const cObj = typeof c === 'object' ? c : { company_id: c, company_name: c };
                    return (
                      <div key={i} className="flex items-center justify-between bg-white border border-slate-200 rounded-lg px-3 py-2">
                        <div className="flex items-center gap-2 min-w-0">
                          <Building2 size={14} className="text-[#2563EB] shrink-0" />
                          <span className="text-sm font-medium text-slate-800 truncate">{name}</span>
                        </div>
                        <div className="flex items-center gap-1.5 shrink-0">
                          <button
                            onClick={() => setConfirmAction({ type: 'resync', company: cObj })}
                            className="p-1.5 rounded-lg text-amber-600 hover:bg-amber-50 transition-colors"
                            title="Resync — clear old data and sync fresh"
                            data-testid={`resync-btn-${i}`}
                          >
                            <RotateCcw size={14} />
                          </button>
                          <button
                            onClick={() => setConfirmAction({ type: 'delete', company: cObj })}
                            className="p-1.5 rounded-lg text-red-500 hover:bg-red-50 transition-colors"
                            title="Delete — remove all company data"
                            data-testid={`delete-btn-${i}`}
                          >
                            <Trash2 size={14} />
                          </button>
                        </div>
                      </div>
                    );
                  }) : (
                    <span className="text-xs text-slate-400">No companies synced yet. Run the Desktop Agent to start syncing.</span>
                  )}
                </div>
              </div>
              {syncStatus.sync_counts && (
                <div className="p-3 rounded-lg bg-slate-50 sm:col-span-2">
                  <div className="text-xs text-slate-500 mb-2">Synced Data</div>
                  <div className="flex flex-wrap gap-3">
                    {Object.entries(syncStatus.sync_counts).map(([key, val]) => (
                      <span key={key} className="text-xs text-slate-600"><span className="font-semibold text-slate-800">{val}</span> {key.replace(/_/g, ' ')}</span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="text-center py-6 text-sm text-slate-400">
              <WifiOff size={32} className="mx-auto mb-2 text-slate-300" />
              No sync data found. Install and run the FLOWRA Desktop Agent to start syncing.
            </div>
          )}
        </div>

        <div className="bg-white border border-slate-200 rounded-xl p-8">
          <div className="flex items-center gap-3 mb-6">
            <div className="w-12 h-12 bg-[#E7F5F0] rounded-lg flex items-center justify-center">
              <SettingsIcon className="text-[#2563EB]" size={24} />
            </div>
            <div>
              <h2 className="text-xl font-medium text-slate-900" style={{ fontFamily: 'Outfit, sans-serif' }}>
                Connection Settings
              </h2>
              <div className="flex items-center gap-2 mt-1">
                {isConnected ? (
                  <>
                    <CheckCircle className="text-green-600" size={16} />
                    <span className="text-sm text-green-600 font-medium">Connected</span>
                  </>
                ) : (
                  <>
                    <XCircle className="text-red-600" size={16} />
                    <span className="text-sm text-red-600 font-medium">Not Connected</span>
                  </>
                )}
              </div>
            </div>
          </div>

          <form onSubmit={handleConnect} className="space-y-6">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">
                Connection Type
              </label>
              <div className="flex gap-4">
                <button
                  type="button"
                  data-testid="connection-type-xml"
                  onClick={() => setConnectionType('xml')}
                  className={`flex-1 px-4 py-3 border-2 rounded-lg transition-all ${
                    connectionType === 'xml'
                      ? 'border-[#2563EB] bg-[#E7F5F0] text-[#2563EB]'
                      : 'border-slate-200 text-slate-600 hover:border-slate-300'
                  }`}
                >
                  <div className="font-medium">XML/HTTP API</div>
                  <div className="text-xs mt-1">Local Tally*</div>
                </button>
                <button
                  type="button"
                  data-testid="connection-type-rest"
                  onClick={() => setConnectionType('rest')}
                  className={`flex-1 px-4 py-3 border-2 rounded-lg transition-all ${
                    connectionType === 'rest'
                      ? 'border-[#2563EB] bg-[#E7F5F0] text-[#2563EB]'
                      : 'border-slate-200 text-slate-600 hover:border-slate-300'
                  }`}
                >
                  <div className="font-medium">REST API</div>
                  <div className="text-xs mt-1">Cloud-based</div>
                </button>
              </div>
            </div>

            {connectionType === 'xml' ? (
              <>
                <div>
                  <label htmlFor="host" className="block text-sm font-medium text-slate-700 mb-2">
                    Host
                  </label>
                  <input
                    id="host"
                    type="text"
                    data-testid="host-input"
                    value={host}
                    onChange={(e) => setHost(e.target.value)}
                    className="w-full px-4 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#2563EB] focus:border-transparent"
                    placeholder="localhost"
                  />
                </div>
                <div>
                  <label htmlFor="port" className="block text-sm font-medium text-slate-700 mb-2">
                    Port
                  </label>
                  <input
                    id="port"
                    type="text"
                    data-testid="port-input"
                    value={port}
                    onChange={(e) => setPort(e.target.value)}
                    className="w-full px-4 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#2563EB] focus:border-transparent"
                    placeholder="9000"
                  />
                </div>
              </>
            ) : (
              <div>
                <label htmlFor="apiKey" className="block text-sm font-medium text-slate-700 mb-2">
                  API Key
                </label>
                <input
                  id="apiKey"
                  type="password"
                  data-testid="api-key-input"
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  className="w-full px-4 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#2563EB] focus:border-transparent"
                  placeholder="Enter your Tally* API key"
                />
              </div>
            )}

            <button
              type="submit"
              data-testid="connect-button"
              disabled={loading}
              className="w-full btn-primary py-3 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? 'Connecting...' : 'Connect to Tally*'}
            </button>
          </form>

          <div className="mt-6 p-4 bg-[#F0F4FF] rounded-lg">
            <h3 className="text-sm font-semibold text-slate-900 mb-2">Setup Instructions</h3>
            <ul className="text-sm text-slate-600 space-y-1">
              <li>• For XML/HTTP: Ensure Tally* is running on your local machine</li>
              <li>• Default port is 9000 (can be configured in Tally* settings)</li>
              <li>• For REST API: Obtain your API key from Tally* Developer portal</li>
              <li>• This demo uses mock data for testing purposes</li>
            </ul>
          </div>
        </div>
      </div>

      {/* Creditor Groups — per-tenant config */}
      <CreditorGroupsPanel />

      {/* Confirmation Modal */}
      {confirmAction && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-[100]" data-testid="confirm-modal">
          <div className="bg-white rounded-2xl max-w-md w-full mx-4 p-6 shadow-2xl">
            <div className="flex items-center gap-3 mb-4">
              <div className={`w-12 h-12 rounded-xl flex items-center justify-center ${confirmAction.type === 'delete' ? 'bg-red-100' : 'bg-amber-100'}`}>
                <AlertTriangle size={24} className={confirmAction.type === 'delete' ? 'text-red-600' : 'text-amber-600'} />
              </div>
              <div>
                <h3 className="text-lg font-bold text-slate-900">
                  {confirmAction.type === 'delete' ? 'Delete Company' : 'Resync Company'}
                </h3>
                <p className="text-sm text-slate-500">{confirmAction.company.company_name}</p>
              </div>
            </div>

            {confirmAction.type === 'delete' ? (
              <div className="mb-6">
                <p className="text-sm text-slate-700 mb-3">This will <strong className="text-red-600">permanently delete ALL data</strong> for this company:</p>
                <ul className="text-sm text-slate-600 space-y-1 ml-4">
                  <li className="list-disc">All inventory items, sales vouchers, receipts</li>
                  <li className="list-disc">Customer records, credit notes, journals</li>
                  <li className="list-disc">Purchase data, contra vouchers, P&L data</li>
                  <li className="list-disc">Sync history and company mapping</li>
                </ul>
                <p className="text-sm text-red-600 font-medium mt-3">This action cannot be undone. The company will be removed from your account.</p>
              </div>
            ) : (
              <div className="mb-6">
                <p className="text-sm text-slate-700 mb-3">This will <strong className="text-amber-600">clear all existing data</strong> for this company and prepare for a fresh sync:</p>
                <ul className="text-sm text-slate-600 space-y-1 ml-4">
                  <li className="list-disc">All synced data (inventory, sales, customers, etc.) will be deleted</li>
                  <li className="list-disc">The company stays in your account</li>
                  <li className="list-disc">Run the Desktop Agent after this to sync fresh data</li>
                </ul>
                <p className="text-sm text-amber-600 font-medium mt-3">The app will show empty data until the next sync completes.</p>
              </div>
            )}

            <div className="flex gap-3">
              <button
                onClick={() => setConfirmAction(null)}
                disabled={actionLoading}
                className="flex-1 px-4 py-2.5 border border-slate-200 rounded-lg text-sm font-medium text-slate-600 hover:bg-slate-50 disabled:opacity-50"
                data-testid="confirm-cancel-btn"
              >
                Cancel
              </button>
              <button
                onClick={handleCompanyAction}
                disabled={actionLoading}
                className={`flex-1 px-4 py-2.5 rounded-lg text-sm font-medium text-white disabled:opacity-50 ${
                  confirmAction.type === 'delete' ? 'bg-red-600 hover:bg-red-700' : 'bg-amber-600 hover:bg-amber-700'
                }`}
                data-testid="confirm-action-btn"
              >
                {actionLoading ? 'Processing...' : confirmAction.type === 'delete' ? 'Yes, Delete Everything' : 'Yes, Clear & Resync'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* v9.8.24 — Download modal: warns the user to quit the running
          agent BEFORE saving the new .exe over the old one. */}
      {showDownloadModal && (
        <div
          className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4"
          onClick={() => setShowDownloadModal(false)}
          data-testid="download-modal-backdrop"
        >
          <div
            onClick={(e) => e.stopPropagation()}
            className="bg-white max-w-lg w-full rounded-xl shadow-xl overflow-hidden"
            data-testid="download-modal"
          >
            <div className="bg-blue-600 text-white px-5 py-3 flex items-center gap-2">
              <AlertTriangle size={18} />
              <h3 className="text-sm font-semibold">Before You Install — Quit the Running Agent</h3>
            </div>
            <div className="p-5 space-y-3 text-sm text-slate-700">
              <p>
                You're about to download <span className="font-semibold text-slate-900">FLOWRA Tally Sync Agent {latestRelease?.version ? `v${latestRelease.version}` : ''}</span>.
              </p>
              <div className="bg-amber-50 border border-amber-200 rounded-lg p-3">
                <p className="font-semibold text-amber-900 mb-1">Important — please do this in order:</p>
                <ol className="text-xs text-amber-800 list-decimal pl-4 space-y-1">
                  <li>If the FLOWRA agent is open, click <span className="font-mono bg-amber-100 px-1 rounded">Stop Sync</span> → File menu → <span className="font-mono bg-amber-100 px-1 rounded">Quit</span> (or right-click the system-tray icon → Exit).</li>
                  <li>Save the new <code>FlowraTallyAgent.exe</code> to the SAME folder as the old one and choose <span className="font-semibold">"Replace"</span> when Windows asks. Otherwise both versions will sit side-by-side and the wrong one may launch.</li>
                  <li>Double-click the new file to launch — your login, Tally settings and selected company are preserved.</li>
                </ol>
              </div>
              <p className="text-xs text-slate-500">
                The .exe is portable — no installer. The auto-update inside a running agent handles all of this automatically; this manual download is for fresh installs or recovering a broken install.
              </p>
            </div>
            <div className="px-5 py-3 bg-slate-50 flex flex-col sm:flex-row gap-2 sm:justify-end">
              <button
                onClick={() => setShowDownloadModal(false)}
                className="px-4 py-2 rounded-lg text-sm font-medium border border-slate-300 text-slate-700 hover:bg-slate-100"
                data-testid="download-modal-cancel"
              >
                Cancel
              </button>
              <a
                href={latestRelease?.download_url || "/FlowraTallyAgent.exe"}
                download
                onClick={() => {
                  // Close the modal after the browser kicks off the download.
                  setTimeout(() => setShowDownloadModal(false), 500);
                }}
                className="inline-flex items-center justify-center gap-2 bg-blue-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-blue-700"
                data-testid="download-modal-confirm"
              >
                <Download size={14} /> I've Quit the Old Agent — Download Now
              </a>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default TallySetup;
