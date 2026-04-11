import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { CheckCircle, XCircle, Settings as SettingsIcon, Wifi, WifiOff, Clock, Monitor, Building2, RefreshCw, Download } from 'lucide-react';
import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const TallySetup = ({ companyId }) => {
  const [connectionType, setConnectionType] = useState('xml');
  const [host, setHost] = useState('localhost');
  const [port, setPort] = useState('9000');
  const [apiKey, setApiKey] = useState('');
  const [isConnected, setIsConnected] = useState(false);
  const [loading, setLoading] = useState(false);
  const [checking, setChecking] = useState(true);
  const [syncStatus, setSyncStatus] = useState(null);

  useEffect(() => {
    checkStatus();
    fetchSyncStatus();
  }, []);

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
        toast.success('Successfully connected to Tally!');
      } else {
        toast.error(response.data?.error || 'Connection failed');
      }
    } catch (error) {
      console.error('Error connecting:', error);
      toast.error('Failed to connect to Tally');
    } finally {
      setLoading(false);
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
          Tally Setup
        </h1>
        <p className="mt-2 text-base text-slate-600">Configure your TallyPrime connection</p>
      </div>

      <div className="max-w-2xl space-y-6">
        {/* Desktop Agent Download */}
        <div className="bg-gradient-to-r from-blue-50 to-indigo-50 border border-blue-200 rounded-xl p-6" data-testid="agent-download-card">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 bg-blue-600 rounded-xl flex items-center justify-center flex-shrink-0">
              <Download size={24} className="text-white" />
            </div>
            <div className="flex-1">
              <a href="/tally_sync_agent_v7.py" download className="inline-flex items-center gap-2 bg-blue-600 text-white px-5 py-2.5 rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors" data-testid="download-agent-btn">
                <Download size={14} /> Download Desktop Connector
              </a>
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
                  {syncStatus.last_sync ? new Date(syncStatus.last_sync).toLocaleString('en-IN', { timeZone: 'Asia/Kolkata' }) : 'Never synced'}
                </div>
              </div>
              <div className="p-3 rounded-lg bg-slate-50">
                <div className="text-xs text-slate-500 flex items-center gap-1 mb-1"><Monitor size={12} /> Agent Version</div>
                <div className="text-sm font-medium text-slate-800" data-testid="agent-version">
                  {syncStatus.agent_version || 'Unknown'}
                </div>
              </div>
              <div className="p-3 rounded-lg bg-slate-50 sm:col-span-2">
                <div className="text-xs text-slate-500 flex items-center gap-1 mb-2"><Building2 size={12} /> Linked Companies</div>
                <div className="flex flex-wrap gap-2" data-testid="linked-companies">
                  {syncStatus.companies?.length > 0 ? syncStatus.companies.map((c, i) => (
                    <span key={i} className="px-3 py-1 bg-white border border-slate-200 rounded-full text-xs font-medium text-slate-700">
                      {typeof c === 'object' ? (c.company_name || c.company_id || '') : c}
                    </span>
                  )) : (
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
                  <div className="text-xs mt-1">Local TallyPrime</div>
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
                  placeholder="Enter your Tally API key"
                />
              </div>
            )}

            <button
              type="submit"
              data-testid="connect-button"
              disabled={loading}
              className="w-full btn-primary py-3 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? 'Connecting...' : 'Connect to Tally'}
            </button>
          </form>

          <div className="mt-6 p-4 bg-[#F0F4FF] rounded-lg">
            <h3 className="text-sm font-semibold text-slate-900 mb-2">Setup Instructions</h3>
            <ul className="text-sm text-slate-600 space-y-1">
              <li>• For XML/HTTP: Ensure TallyPrime is running on your local machine</li>
              <li>• Default port is 9000 (can be configured in Tally settings)</li>
              <li>• For REST API: Obtain your API key from Tally Developer portal</li>
              <li>• This demo uses mock data for testing purposes</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
};

export default TallySetup;
