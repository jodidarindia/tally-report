import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Bot, Filter, X, Calendar, DollarSign, Package, Users, TrendingUp, FileText } from 'lucide-react';
import { toast } from 'sonner';
import {
  renderStructuredInsight,
  renderStructuredRecommendation,
  renderMetricValue,
  renderDetailedAnalysis,
} from '../components/AIInsightRenderers';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const EnhancedAIReports = () => {
  const [query, setQuery] = useState('');
  const [reportType, setReportType] = useState('general');
  const [filters, setFilters] = useState({
    start_date: '',
    end_date: '',
    category: '',
    customer: '',
    min_amount: '',
    max_amount: ''
  });
  const [showFilters, setShowFilters] = useState(false);
  const [loading, setLoading] = useState(false);
  const [report, setReport] = useState(null);

  const reportTypes = [
    { value: 'general', label: 'General Analysis', icon: FileText },
    { value: 'inventory', label: 'Inventory Focus', icon: Package },
    { value: 'sales', label: 'Sales Analysis', icon: TrendingUp },
    { value: 'customer', label: 'Customer Insights', icon: Users },
    { value: 'profit', label: 'Profit Analysis', icon: DollarSign },
    { value: 'movement', label: 'Movement Analysis', icon: TrendingUp }
  ];

  const sampleQueries = [
    "Show me items with low stock that need immediate reordering",
    "Which customers have outstanding payments over 90 days?",
    "Analyze profit margins and identify items sold below cost",
    "Compare sales performance across different product categories",
    "Identify slow-moving inventory that's been in stock for over 60 days"
  ];

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!query.trim()) {
      toast.error('Please enter a query');
      return;
    }

    setLoading(true);
    try {
      const cleanFilters = Object.fromEntries(
        Object.entries(filters).filter(([_, v]) => v !== '')
      );

      const response = await axios.post(`${API}/ai/advanced-query`, {
        query,
        report_type: reportType,
        filters: cleanFilters
      }, { timeout: 60000 });

      if (response.data?.success) {
        setReport(response.data.data);
      } else {
        toast.error(response.data?.error || 'Failed to generate report');
      }
    } catch (error) {
      console.error('Error generating report:', error);
      toast.error('Failed to generate report. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const clearFilter = (key) => {
    setFilters({ ...filters, [key]: '' });
  };

  const activeFilters = Object.entries(filters).filter(([_, v]) => v !== '');

  return (
    <div data-testid="enhanced-ai-page">
      <div className="mb-8">
        <h1 className="text-4xl font-light tracking-tight text-slate-900" style={{ fontFamily: 'Outfit, sans-serif' }}>
          Enhanced AI Reports
        </h1>
        <p className="mt-2 text-base text-slate-600">Advanced report generation with filters and specialized analysis</p>
      </div>

      {/* Report Type Selection */}
      <div className="bg-white border border-slate-200 rounded-xl p-6 mb-6">
        <h3 className="text-lg font-medium text-slate-900 mb-4">Select Report Type</h3>
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
          {reportTypes.map((type) => {
            const Icon = type.icon;
            return (
              <button
                key={type.value}
                onClick={() => setReportType(type.value)}
                data-testid={`report-type-${type.value}`}
                className={`flex flex-col items-center gap-2 p-4 rounded-lg border-2 transition-all ${
                  reportType === type.value
                    ? 'border-[#2563EB] bg-[#E7F5F0]'
                    : 'border-slate-200 hover:border-slate-300'
                }`}
              >
                <Icon size={24} className={reportType === type.value ? 'text-[#2563EB]' : 'text-slate-600'} />
                <span className="text-xs font-medium text-center">{type.label}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Filters Panel */}
      <div className="bg-white border border-slate-200 rounded-xl p-6 mb-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-medium text-slate-900">Filters</h3>
          <button
            onClick={() => setShowFilters(!showFilters)}
            className="flex items-center gap-2 text-sm text-[#2563EB] font-medium"
            data-testid="toggle-filters"
          >
            <Filter size={16} />
            {showFilters ? 'Hide Filters' : 'Show Filters'}
          </button>
        </div>

        {/* Active Filters */}
        {activeFilters.length > 0 && (
          <div className="flex flex-wrap gap-2 mb-4">
            {activeFilters.map(([key, value]) => (
              <div
                key={key}
                className="flex items-center gap-2 px-3 py-1 bg-[#E7F5F0] rounded-full text-sm"
              >
                <span className="text-slate-700">
                  <strong>{key.replace('_', ' ')}:</strong> {value}
                </span>
                <button onClick={() => clearFilter(key)} className="text-slate-500 hover:text-slate-700">
                  <X size={14} />
                </button>
              </div>
            ))}
          </div>
        )}

        {showFilters && (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">Start Date</label>
              <input
                type="date"
                value={filters.start_date}
                onChange={(e) => setFilters({ ...filters, start_date: e.target.value })}
                className="w-full px-4 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#2563EB]"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">End Date</label>
              <input
                type="date"
                value={filters.end_date}
                onChange={(e) => setFilters({ ...filters, end_date: e.target.value })}
                className="w-full px-4 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#2563EB]"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">Category</label>
              <input
                type="text"
                placeholder="e.g., Electronics"
                value={filters.category}
                onChange={(e) => setFilters({ ...filters, category: e.target.value })}
                className="w-full px-4 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#2563EB]"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">Customer</label>
              <input
                type="text"
                placeholder="Customer name"
                value={filters.customer}
                onChange={(e) => setFilters({ ...filters, customer: e.target.value })}
                className="w-full px-4 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#2563EB]"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">Min Amount</label>
              <input
                type="number"
                placeholder="0"
                value={filters.min_amount}
                onChange={(e) => setFilters({ ...filters, min_amount: e.target.value })}
                className="w-full px-4 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#2563EB]"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">Max Amount</label>
              <input
                type="number"
                placeholder="999999"
                value={filters.max_amount}
                onChange={(e) => setFilters({ ...filters, max_amount: e.target.value })}
                className="w-full px-4 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#2563EB]"
              />
            </div>
          </div>
        )}
      </div>

      {/* Query Input */}
      <div className="ai-query-container mb-6" style={{ backgroundImage: `url(${process.env.REACT_APP_AI_BACKGROUND_IMAGE})` }}>
        <div className="ai-query-bg" />
        
        <form onSubmit={handleSubmit}>
          <div className="ai-query-input-area">
            <div className="flex items-center gap-4 w-full">
              <Bot className="text-[#2563EB]" size={24} />
              <input
                type="text"
                placeholder="Ask detailed questions about your business data..."
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                disabled={loading}
                className="flex-1 bg-transparent border-none outline-none text-slate-900 placeholder-slate-400"
                data-testid="enhanced-ai-input"
              />
              <button
                type="submit"
                disabled={loading || !query.trim()}
                className="btn-primary"
                data-testid="generate-report-button"
              >
                {loading ? 'Generating...' : 'Generate Report'}
              </button>
            </div>
          </div>
        </form>

        <div className="relative z-10 mt-4">
          <div className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-2">Sample Queries</div>
          <div className="flex flex-wrap gap-2">
            {sampleQueries.map((sample, idx) => (
              <button
                key={idx}
                onClick={() => setQuery(sample)}
                className="px-3 py-2 bg-white/60 hover:bg-white border border-slate-200/50 rounded-lg text-xs text-slate-700 transition-all"
              >
                {sample}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Report Results */}
      {report && (
        <div className="space-y-6" data-testid="report-results">
          <div className="bg-white border border-slate-200 rounded-xl p-6">
            <h3 className="text-xl font-medium text-slate-900 mb-3">Summary</h3>
            <p className="text-base text-slate-700 leading-relaxed">
              {typeof report.summary === 'object' ? JSON.stringify(report.summary) : report.summary}
            </p>
          </div>

          {report.key_insights && report.key_insights.length > 0 && (
            <div className="bg-white border border-slate-200 rounded-xl p-6">
              <h3 className="text-xl font-medium text-slate-900 mb-4">Key Insights</h3>
              <ul className="space-y-3">
                {report.key_insights.map((insight, idx) => (
                  <li key={idx} className="flex items-start gap-3" data-testid={`ai-insight-${idx}`}>
                    <div className="w-6 h-6 bg-[#E7F5F0] rounded-full flex items-center justify-center flex-shrink-0 mt-0.5">
                      <span className="text-xs font-semibold text-[#2563EB]">{idx + 1}</span>
                    </div>
                    <div className="text-base text-slate-700 flex-1">
                      {renderStructuredInsight(insight)}
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {report.metrics && typeof report.metrics === 'object' && Object.keys(report.metrics).length > 0 && (
            <div className="bg-white border border-slate-200 rounded-xl p-6">
              <h3 className="text-xl font-medium text-slate-900 mb-4">Metrics</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {Object.entries(report.metrics).map(([key, value]) => (
                  <div key={key} className="p-4 bg-[#F0F4FF] rounded-lg" data-testid={`ai-metric-${key}`}>
                    <div className="text-xs uppercase tracking-wide font-semibold text-slate-500 mb-1.5">{key.replace(/_/g, ' ')}</div>
                    <div className="text-slate-800">
                      {renderMetricValue(value)}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {report.recommendations && report.recommendations.length > 0 && (
            <div className="bg-white border border-slate-200 rounded-xl p-6">
              <h3 className="text-xl font-medium text-slate-900 mb-4">Recommendations</h3>
              <ul className="space-y-3">
                {report.recommendations.map((rec, idx) => (
                  <li key={idx} className="flex items-start gap-3" data-testid={`ai-recommendation-${idx}`}>
                    <div className="w-2 h-2 bg-[#2563EB] rounded-full flex-shrink-0 mt-2.5" />
                    <div className="text-base text-slate-700 flex-1">
                      {renderStructuredRecommendation(rec)}
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {report.detailed_analysis && (
            <div className="bg-white border border-slate-200 rounded-xl p-6">
              <h3 className="text-xl font-medium text-slate-900 mb-4">Detailed Analysis</h3>
              <div className="text-base text-slate-700 leading-relaxed">
                {renderDetailedAnalysis(report.detailed_analysis)}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default EnhancedAIReports;
