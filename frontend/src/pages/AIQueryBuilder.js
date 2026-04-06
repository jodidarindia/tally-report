import React, { useState } from 'react';
import axios from 'axios';
import { Bot, Send, Sparkles } from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const AIQueryBuilder = () => {
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [report, setReport] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!query.trim()) return;

    setLoading(true);
    try {
      const response = await axios.post(`${API}/ai/query`, { query });
      
      if (response.data?.success) {
        setReport(response.data.data);
      } else {
        console.error('AI query failed:', response.data?.error);
      }
    } catch (error) {
      console.error('Error processing AI query:', error);
    } finally {
      setLoading(false);
    }
  };

  const sampleQueries = [
    "What are the top selling items this month?",
    "Show me items that need reordering",
    "Which customers have the highest purchase value?",
    "What is the total inventory value by category?"
  ];

  return (
    <div data-testid="ai-query-page">
      <div className="mb-8">
        <h1 className="text-4xl font-light tracking-tight text-stone-900" style={{ fontFamily: 'Outfit, sans-serif' }}>
          AI Report Builder
        </h1>
        <p className="mt-2 text-base text-stone-600">Ask questions in natural language and get instant insights</p>
      </div>

      <div
        className="ai-query-container"
        data-testid="ai-query-container"
        style={{
          backgroundImage: 'url(https://static.prod-images.emergentagent.com/jobs/e93f8a38-4ad0-4d0c-b41a-81b9cd3b283f/images/1e9e8fc2367de38e12a3264a83ec836765e5585a923a048af222e80cdb30cf72.png)'
        }}
      >
        <div className="ai-query-bg" />
        
        <form onSubmit={handleSubmit} className="mb-6">
          <div className="ai-query-input-area">
            <div className="flex items-center gap-4 w-full">
              <div className="w-10 h-10 bg-[#064E3B] rounded-lg flex items-center justify-center flex-shrink-0">
                <Bot className="text-white" size={20} />
              </div>
              <input
                type="text"
                data-testid="ai-query-input"
                placeholder="Ask me anything about your inventory or sales data..."
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                disabled={loading}
                className="flex-1 bg-transparent border-none outline-none text-stone-900 placeholder-stone-400 text-base"
                style={{ fontFamily: 'Work Sans, sans-serif' }}
              />
              <button
                type="submit"
                data-testid="ai-submit-button"
                disabled={loading || !query.trim()}
                className="w-10 h-10 bg-[#064E3B] hover:bg-[#047857] disabled:bg-stone-300 rounded-lg flex items-center justify-center transition-colors flex-shrink-0"
              >
                {loading ? (
                  <div className="loading-spinner" style={{ borderTopColor: 'white', borderWidth: '2px' }} />
                ) : (
                  <Send className="text-white" size={18} />
                )}
              </button>
            </div>
          </div>
        </form>

        <div className="relative z-10">
          <div className="flex items-center gap-2 mb-3">
            <Sparkles size={16} className="text-[#064E3B]" />
            <span className="text-xs font-semibold uppercase tracking-wider text-stone-500">Sample Queries</span>
          </div>
          <div className="flex flex-wrap gap-2">
            {sampleQueries.map((sample, index) => (
              <button
                key={index}
                data-testid={`sample-query-${index}`}
                onClick={() => setQuery(sample)}
                className="px-4 py-2 bg-white/60 hover:bg-white border border-stone-200/50 rounded-lg text-sm text-stone-700 transition-all hover:shadow-sm"
              >
                {sample}
              </button>
            ))}
          </div>
        </div>
      </div>

      {report && (
        <div className="mt-8 space-y-6" data-testid="ai-report-result">
          <div className="bg-white border border-stone-200 rounded-xl p-6">
            <h3 className="text-xl font-medium text-stone-900 mb-3" style={{ fontFamily: 'Outfit, sans-serif' }}>
              Summary
            </h3>
            <p className="text-base text-stone-700 leading-relaxed">{report.summary}</p>
          </div>

          {report.key_insights && report.key_insights.length > 0 && (
            <div className="bg-white border border-stone-200 rounded-xl p-6">
              <h3 className="text-xl font-medium text-stone-900 mb-4" style={{ fontFamily: 'Outfit, sans-serif' }}>
                Key Insights
              </h3>
              <ul className="space-y-2">
                {report.key_insights.map((insight, index) => (
                  <li key={index} className="flex items-start gap-3">
                    <div className="w-6 h-6 bg-[#E7F5F0] rounded-full flex items-center justify-center flex-shrink-0 mt-0.5">
                      <span className="text-xs font-semibold text-[#064E3B]">{index + 1}</span>
                    </div>
                    <span className="text-base text-stone-700">{insight}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {report.metrics && Object.keys(report.metrics).length > 0 && (
            <div className="bg-white border border-stone-200 rounded-xl p-6">
              <h3 className="text-xl font-medium text-stone-900 mb-4" style={{ fontFamily: 'Outfit, sans-serif' }}>
                Metrics
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {Object.entries(report.metrics).map(([key, value]) => (
                  <div key={key} className="p-4 bg-[#FDFBF7] rounded-lg">
                    <div className="text-sm text-stone-500 mb-1">{key.replace(/_/g, ' ').toUpperCase()}</div>
                    <div className="text-2xl font-semibold text-[#064E3B]">
                      {typeof value === 'object' && value !== null 
                        ? JSON.stringify(value, null, 2) 
                        : value}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {report.recommendations && report.recommendations.length > 0 && (
            <div className="bg-white border border-stone-200 rounded-xl p-6">
              <h3 className="text-xl font-medium text-stone-900 mb-4" style={{ fontFamily: 'Outfit, sans-serif' }}>
                Recommendations
              </h3>
              <ul className="space-y-2">
                {report.recommendations.map((rec, index) => (
                  <li key={index} className="flex items-start gap-3">
                    <div className="w-2 h-2 bg-[#064E3B] rounded-full flex-shrink-0 mt-2" />
                    <span className="text-base text-stone-700">{rec}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default AIQueryBuilder;
