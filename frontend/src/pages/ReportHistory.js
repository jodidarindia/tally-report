import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Clock, MessageSquare } from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const ReportHistory = () => {
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchHistory();
  }, []);

  const fetchHistory = async () => {
    setLoading(true);
    try {
      const response = await axios.get(`${API}/reports/history`);
      setHistory(response.data?.data?.queries || []);
    } catch (error) {
      console.error('Error fetching report history:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64" data-testid="history-loading">
        <div className="loading-spinner" />
        <span className="ml-3 text-stone-600">Loading history...</span>
      </div>
    );
  }

  return (
    <div data-testid="history-page">
      <div className="mb-8">
        <h1 className="text-4xl font-light tracking-tight text-stone-900" style={{ fontFamily: 'Outfit, sans-serif' }}>
          Report History
        </h1>
        <p className="mt-2 text-base text-stone-600">View your past AI-generated reports</p>
      </div>

      <div className="space-y-4">
        {history.length > 0 ? (
          history.map((item, index) => (
            <div
              key={item.id || index}
              data-testid={`history-item-${index}`}
              className="bg-white border border-stone-200 rounded-xl p-6 hover:shadow-md transition-shadow"
            >
              <div className="flex items-start gap-4">
                <div className="w-12 h-12 bg-[#E7F5F0] rounded-lg flex items-center justify-center flex-shrink-0">
                  <MessageSquare className="text-[#064E3B]" size={20} />
                </div>
                <div className="flex-1">
                  <div className="flex items-center gap-3 mb-2">
                    <h3 className="text-lg font-medium text-stone-900">{item.query_text}</h3>
                  </div>
                  {item.created_at && (
                    <div className="flex items-center gap-2 text-sm text-stone-500 mb-3">
                      <Clock size={14} />
                      {new Date(item.created_at).toLocaleString()}
                    </div>
                  )}
                  {item.response && (
                    <div className="p-4 bg-[#FDFBF7] rounded-lg">
                      <p className="text-sm text-stone-700 line-clamp-3">{item.response}</p>
                    </div>
                  )}
                </div>
              </div>
            </div>
          ))
        ) : (
          <div className="bg-white border border-stone-200 rounded-xl p-12 text-center">
            <MessageSquare className="mx-auto text-stone-300 mb-4" size={48} />
            <h3 className="text-lg font-medium text-stone-900 mb-2">No reports yet</h3>
            <p className="text-stone-500">Start using the AI Query Builder to generate reports</p>
          </div>
        )}
      </div>
    </div>
  );
};

export default ReportHistory;
