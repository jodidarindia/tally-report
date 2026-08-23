// v9.8.27 — Shared renderers for AI Insights output (used by
// EnhancedAIReports.js and AIQueryBuilder.js). The LLM sometimes returns
// structured objects inside the `key_insights` / `recommendations` /
// `metrics` / `detailed_analysis` payload fields instead of plain
// strings. These helpers render whatever shape arrives without dumping
// raw JSON in the UI.

import React from 'react';

export const INDIAN_NUMBER = (n) => {
  if (n === null || n === undefined) return '—';
  if (typeof n !== 'number') return String(n);
  if (!Number.isFinite(n)) return String(n);
  if (Number.isInteger(n)) return n.toLocaleString('en-IN');
  return n.toLocaleString('en-IN', { maximumFractionDigits: 2 });
};

export const HUMAN_LABEL = (k) =>
  String(k).replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());

const PRIORITY_STYLE = {
  high:   'bg-red-100 text-red-700',
  medium: 'bg-amber-100 text-amber-700',
  low:    'bg-emerald-100 text-emerald-700',
};

export function renderStructuredInsight(insight) {
  if (insight === null || insight === undefined) return null;
  if (typeof insight === 'string') {
    const trimmed = insight.trim();
    if ((trimmed.startsWith('{') && trimmed.endsWith('}'))
        || (trimmed.startsWith('[') && trimmed.endsWith(']'))) {
      try { return renderStructuredInsight(JSON.parse(trimmed)); } catch { /* fallthrough */ }
    }
    return <p className="whitespace-pre-wrap">{insight}</p>;
  }
  if (Array.isArray(insight)) {
    return (
      <ul className="space-y-1 list-disc pl-5">
        {insight.map((it, i) => <li key={i}>{renderStructuredInsight(it)}</li>)}
      </ul>
    );
  }
  const { insight: title, detail, risk, ...rest } = insight;
  return (
    <div className="space-y-1">
      {title && <p className="font-medium text-slate-900">{title}</p>}
      {detail && <p className="text-sm text-slate-600">{detail}</p>}
      {risk && (
        <p className="text-sm text-amber-700 bg-amber-50 border border-amber-200 rounded px-2 py-1 mt-1 inline-block">
          <span className="font-semibold">Risk:</span> {risk}
        </p>
      )}
      {Object.keys(rest).length > 0 && (
        <div className="text-sm text-slate-600 mt-1 space-y-0.5">
          {Object.entries(rest).map(([k, v]) => (
            <div key={k}>
              <span className="text-slate-500">{HUMAN_LABEL(k)}: </span>
              <span>{typeof v === 'object' ? renderStructuredInsight(v) : String(v)}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

const SUMMARY_LABELS = {
  request: 'What was asked',
  definition_used: 'How we defined it',
  snapshot_limitations: 'Data caveats',
  scope: 'Scope',
  data_window: 'Data window',
  method: 'Method',
  assumptions: 'Assumptions',
  disclaimer: 'Disclaimer',
  overview: 'Overview',
  headline: 'Headline',
};

export function renderStructuredSummary(summary) {
  if (summary === null || summary === undefined) return null;
  if (typeof summary === 'string') {
    const trimmed = summary.trim();
    if (trimmed.startsWith('{') && trimmed.endsWith('}')) {
      try { return renderStructuredSummary(JSON.parse(trimmed)); } catch { /* fallthrough */ }
    }
    return <p className="whitespace-pre-wrap leading-relaxed">{summary}</p>;
  }
  if (Array.isArray(summary)) {
    return (
      <ul className="space-y-1.5 list-disc pl-5">
        {summary.map((it, i) => (
          <li key={i}>{typeof it === 'object' ? renderStructuredSummary(it) : String(it)}</li>
        ))}
      </ul>
    );
  }
  return (
    <div className="space-y-3">
      {Object.entries(summary).map(([k, v]) => {
        if (v === null || v === undefined || v === '') return null;
        return (
          <div key={k}>
            <div className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-1">
              {SUMMARY_LABELS[k] || HUMAN_LABEL(k)}
            </div>
            <div className="text-base text-slate-700 leading-relaxed">
              {typeof v === 'object' ? renderStructuredSummary(v) : String(v)}
            </div>
          </div>
        );
      })}
    </div>
  );
}

export function renderStructuredRecommendation(rec) {
  if (rec === null || rec === undefined) return null;
  if (typeof rec === 'string') {
    const trimmed = rec.trim();
    if (trimmed.startsWith('{') && trimmed.endsWith('}')) {
      try { return renderStructuredRecommendation(JSON.parse(trimmed)); } catch { /* fall through */ }
    }
    return <p className="whitespace-pre-wrap">{rec}</p>;
  }
  const { priority, action, expected_impact, impact, actions, ...rest } = rec;
  const prio = (priority || '').toString().toLowerCase();
  return (
    <div className="space-y-1.5">
      <div className="flex items-center gap-2 flex-wrap">
        {priority && (
          <span className={`px-2 py-0.5 text-[10px] font-bold rounded uppercase tracking-wide ${PRIORITY_STYLE[prio] || 'bg-slate-100 text-slate-700'}`}>
            {priority}
          </span>
        )}
        {action && <span className="text-slate-900 font-medium">{action}</span>}
      </div>
      {(expected_impact || impact) && (
        <p className="text-sm text-slate-600">
          <span className="text-slate-500">Expected impact: </span>{expected_impact || impact}
        </p>
      )}
      {Array.isArray(actions) && actions.length > 0 && (
        <div className="mt-1.5">
          <div className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1">Actions</div>
          <ul className="space-y-1 list-disc pl-5 text-sm text-slate-700 leading-relaxed">
            {actions.map((a, i) => (
              <li key={i}>{typeof a === 'object' ? renderStructuredRecommendation(a) : String(a)}</li>
            ))}
          </ul>
        </div>
      )}
      {Object.keys(rest).length > 0 && (
        <div className="text-sm text-slate-600 space-y-1 mt-1">
          {Object.entries(rest).map(([k, v]) => {
            if (v === null || v === undefined || v === '') return null;
            if (Array.isArray(v)) {
              if (!v.length) return null;
              return (
                <div key={k}>
                  <span className="text-slate-500">{HUMAN_LABEL(k)}: </span>
                  {typeof v[0] === 'object' ? (
                    <ul className="list-disc pl-5 mt-0.5 space-y-0.5">
                      {v.map((it, i) => <li key={i}>{renderStructuredRecommendation(it)}</li>)}
                    </ul>
                  ) : (
                    <span>{v.join(', ')}</span>
                  )}
                </div>
              );
            }
            if (typeof v === 'object') {
              return (
                <div key={k}>
                  <span className="text-slate-500">{HUMAN_LABEL(k)}: </span>
                  <div className="pl-3 border-l-2 border-slate-200 mt-0.5">
                    {renderStructuredRecommendation(v)}
                  </div>
                </div>
              );
            }
            return (
              <div key={k}>
                <span className="text-slate-500">{HUMAN_LABEL(k)}: </span>
                <span>{String(v)}</span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

export function renderMetricValue(value) {
  if (value === null || value === undefined) return <span className="text-slate-400">—</span>;
  if (typeof value === 'number') {
    return <span className="text-2xl font-semibold text-[#2563EB]">{INDIAN_NUMBER(value)}</span>;
  }
  if (typeof value === 'string') return <span className="text-base text-slate-800">{value}</span>;
  if (typeof value === 'boolean') return <span className="text-base text-slate-800">{value ? 'Yes' : 'No'}</span>;
  if (Array.isArray(value)) {
    if (value.length === 0) {
      return <span className="text-sm text-slate-400 italic">None</span>;
    }
    if (typeof value[0] === 'object' && value[0] !== null) {
      return (
        <div className="text-sm text-slate-700 space-y-2 mt-1">
          {value.slice(0, 5).map((row, i) => (
            <div key={i} className="bg-white rounded p-2 border border-slate-200">
              {Object.entries(row).map(([k, v]) => (
                <div key={k} className="flex items-baseline justify-between gap-2 leading-tight">
                  <span className="text-xs text-slate-500">{HUMAN_LABEL(k)}</span>
                  <span className="text-sm font-medium text-slate-800 text-right truncate">
                    {typeof v === 'number' ? INDIAN_NUMBER(v) : String(v ?? '—')}
                  </span>
                </div>
              ))}
            </div>
          ))}
          {value.length > 5 && (
            <p className="text-xs text-slate-400 italic">+{value.length - 5} more</p>
          )}
        </div>
      );
    }
    return <p className="text-sm text-slate-700">{value.join(', ')}</p>;
  }
  if (typeof value === 'object') {
    return (
      <div className="text-sm text-slate-700 space-y-0.5">
        {Object.entries(value).map(([k, v]) => (
          <div key={k} className="flex justify-between gap-2">
            <span className="text-xs text-slate-500">{HUMAN_LABEL(k)}</span>
            <span className="text-sm font-medium text-slate-800">
              {typeof v === 'number' ? INDIAN_NUMBER(v) : String(v ?? '—')}
            </span>
          </div>
        ))}
      </div>
    );
  }
  return <span>{String(value)}</span>;
}

export function renderDetailedAnalysis(detail) {
  if (detail === null || detail === undefined) return null;
  if (typeof detail === 'string') {
    return <p className="whitespace-pre-wrap leading-relaxed">{detail}</p>;
  }
  if (Array.isArray(detail)) {
    return (
      <ul className="space-y-2 list-disc pl-5">
        {detail.map((it, i) => <li key={i}>{renderDetailedAnalysis(it)}</li>)}
      </ul>
    );
  }
  return (
    <div className="space-y-4">
      {Object.entries(detail).map(([k, v]) => (
        <div key={k}>
          <h4 className="text-sm font-semibold text-slate-900 mb-1">{HUMAN_LABEL(k)}</h4>
          <div className="text-sm text-slate-700 pl-3 border-l-2 border-slate-200">
            {renderDetailedAnalysis(v)}
          </div>
        </div>
      ))}
    </div>
  );
}
