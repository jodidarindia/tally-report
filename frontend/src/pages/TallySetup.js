import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { CheckCircle, XCircle, Settings as SettingsIcon } from 'lucide-react';
import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const TallySetup = () => {
  const [connectionType, setConnectionType] = useState('xml');
  const [host, setHost] = useState('localhost');
  const [port, setPort] = useState('9000');
  const [apiKey, setApiKey] = useState('');
  const [isConnected, setIsConnected] = useState(false);
  const [loading, setLoading] = useState(false);
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    checkStatus();
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
        <span className="ml-3 text-stone-600">Checking connection...</span>
      </div>
    );
  }

  return (
    <div data-testid="setup-page">
      <div className="mb-8">
        <h1 className="text-4xl font-light tracking-tight text-stone-900" style={{ fontFamily: 'Outfit, sans-serif' }}>
          Tally Setup
        </h1>
        <p className="mt-2 text-base text-stone-600">Configure your TallyPrime connection</p>
      </div>

      <div className="max-w-2xl">
        <div className="bg-white border border-stone-200 rounded-xl p-8">
          <div className="flex items-center gap-3 mb-6">
            <div className="w-12 h-12 bg-[#E7F5F0] rounded-lg flex items-center justify-center">
              <SettingsIcon className="text-[#064E3B]" size={24} />
            </div>
            <div>
              <h2 className="text-xl font-medium text-stone-900" style={{ fontFamily: 'Outfit, sans-serif' }}>
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
              <label className="block text-sm font-medium text-stone-700 mb-2">
                Connection Type
              </label>
              <div className="flex gap-4">
                <button
                  type="button"
                  data-testid="connection-type-xml"
                  onClick={() => setConnectionType('xml')}
                  className={`flex-1 px-4 py-3 border-2 rounded-lg transition-all ${
                    connectionType === 'xml'
                      ? 'border-[#064E3B] bg-[#E7F5F0] text-[#064E3B]'
                      : 'border-stone-200 text-stone-600 hover:border-stone-300'
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
                      ? 'border-[#064E3B] bg-[#E7F5F0] text-[#064E3B]'
                      : 'border-stone-200 text-stone-600 hover:border-stone-300'
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
                  <label htmlFor="host" className="block text-sm font-medium text-stone-700 mb-2">
                    Host
                  </label>
                  <input
                    id="host"
                    type="text"
                    data-testid="host-input"
                    value={host}
                    onChange={(e) => setHost(e.target.value)}
                    className="w-full px-4 py-2 border border-stone-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#064E3B] focus:border-transparent"
                    placeholder="localhost"
                  />
                </div>
                <div>
                  <label htmlFor="port" className="block text-sm font-medium text-stone-700 mb-2">
                    Port
                  </label>
                  <input
                    id="port"
                    type="text"
                    data-testid="port-input"
                    value={port}
                    onChange={(e) => setPort(e.target.value)}
                    className="w-full px-4 py-2 border border-stone-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#064E3B] focus:border-transparent"
                    placeholder="9000"
                  />
                </div>
              </>
            ) : (
              <div>
                <label htmlFor="apiKey" className="block text-sm font-medium text-stone-700 mb-2">
                  API Key
                </label>
                <input
                  id="apiKey"
                  type="password"
                  data-testid="api-key-input"
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  className="w-full px-4 py-2 border border-stone-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#064E3B] focus:border-transparent"
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

          <div className="mt-6 p-4 bg-[#FDFBF7] rounded-lg">
            <h3 className="text-sm font-semibold text-stone-900 mb-2">Setup Instructions</h3>
            <ul className="text-sm text-stone-600 space-y-1">
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
