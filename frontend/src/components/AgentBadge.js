import React from 'react';

/**
 * Small colored badge identifying which desktop sync agent synced a company.
 *   - Tally v9.x  → blue
 *   - Busy v1.x   → amber
 *   - Unknown     → slate
 */
const AgentBadge = ({ agentVersion, size = 'sm', className = '' }) => {
  const v = (agentVersion || '').toString().toLowerCase().trim();
  if (!v) return null;

  let label, color;
  if (v.startsWith('busy')) {
    label = `Busy ${v.replace(/^busy-?/, '') || 'v1'}`;
    color = 'bg-amber-100 text-amber-800 border-amber-200';
  } else if (v.startsWith('tally') || /^\d+\.\d/.test(v)) {
    const ver = v.replace(/^tally-?/, '');
    label = `Tally v${ver.split('-')[0]}`;
    color = 'bg-blue-100 text-blue-800 border-blue-200';
  } else {
    label = v;
    color = 'bg-slate-100 text-slate-700 border-slate-200';
  }

  const sizeCls = size === 'xs'
    ? 'px-1.5 py-0.5 text-[10px]'
    : 'px-2 py-0.5 text-xs';

  return (
    <span
      className={`inline-flex items-center rounded-full border font-medium ${color} ${sizeCls} ${className}`}
      data-testid="agent-badge"
      title={`Synced by agent: ${agentVersion}`}
    >
      {label}
    </span>
  );
};

export default AgentBadge;
