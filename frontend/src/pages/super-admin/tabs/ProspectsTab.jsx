import React, { useMemo, useState } from 'react';
import { ArrowRightCircle, Calendar, ChevronDown, ChevronUp } from 'lucide-react';
import { formatDate } from '../utils';

export const ProspectsTab = ({ prospects, prospectStats, onUpdateStatus, onConvert }) => {
  const [filter, setFilter] = useState('all');       // iter-122 clickable summary cards
  const [expanded, setExpanded] = useState(null);    // iter-122 clickable prospect drill-down
  const [demoDateFor, setDemoDateFor] = useState(null);
  const [demoDate, setDemoDate] = useState(new Date().toISOString().slice(0, 10));

  const cards = [
    { id: 'all',       label: 'Total',     value: prospectStats.total || 0,     color: 'text-slate-700' },
    { id: 'new',       label: 'New',       value: prospectStats.new || 0,       color: 'text-blue-600' },
    { id: 'contacted', label: 'Contacted', value: prospectStats.contacted || 0, color: 'text-amber-600' },
    { id: 'converted', label: 'Converted', value: prospectStats.converted || 0, color: 'text-emerald-600' },
    { id: 'lost',      label: 'Lost',      value: prospectStats.lost || 0,      color: 'text-red-600' },
  ];

  const filtered = useMemo(() => {
    if (filter === 'all') return prospects;
    return prospects.filter(p => (p.status || 'new') === filter);
  }, [prospects, filter]);

  const onStatusChange = (prospect_id, next) => {
    if (next === 'demo_given') {
      // iter-122: capture the date the demo was actually given so the
      // Overview / Health tab can show accurate demo→convert funnels.
      setDemoDateFor(prospect_id);
      setDemoDate(new Date().toISOString().slice(0, 10));
      return;
    }
    onUpdateStatus(prospect_id, next);
  };

  const confirmDemoDate = () => {
    if (!demoDateFor) return;
    onUpdateStatus(demoDateFor, 'demo_given', { demo_given_at: demoDate });
    setDemoDateFor(null);
  };

  return (
  <div data-testid="prospects-tab">
    <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-6">
      {cards.map(s => {
        const active = filter === s.id;
        return (
          <button
            key={s.id}
            type="button"
            onClick={() => setFilter(active ? 'all' : s.id)}
            className={`bg-white border rounded-xl p-4 text-left transition-all ${active ? 'border-blue-500 ring-2 ring-blue-200 shadow-md' : 'border-slate-200 hover:shadow-sm'}`}
            data-testid={`prospect-card-${s.id}`}
          >
            <p className="text-xs text-slate-500 flex items-center justify-between">
              <span>{s.label}</span>
              {active && s.id !== 'all' && <span className="text-blue-600 text-[10px]">● Filtered</span>}
            </p>
            <p className={`text-xl font-bold ${s.color}`}>{s.value}</p>
          </button>
        );
      })}
    </div>
    <div className="space-y-3">
      {filtered.map(p => {
        const isOpen = expanded === p.prospect_id;
        return (
        <div key={p.prospect_id} className="bg-white border border-slate-200 rounded-xl p-4 cursor-pointer hover:shadow-sm transition-shadow" data-testid={`prospect-${p.prospect_id}`}
             onClick={() => setExpanded(isOpen ? null : p.prospect_id)}>
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              {isOpen ? <ChevronUp size={14} className="text-slate-400" /> : <ChevronDown size={14} className="text-slate-400" />}
              <div>
                <h4 className="font-medium text-slate-900">{p.company_name || p.email}</h4>
                <p className="text-xs text-slate-500">{p.email} · {p.contact_person}</p>
              </div>
            </div>
            <div className="flex items-center gap-2" onClick={e => e.stopPropagation()}>
              <select value={p.status} onChange={e => onStatusChange(p.prospect_id, e.target.value)}
                className="text-xs border border-slate-200 rounded-lg px-2 py-1.5" data-testid={`prospect-status-${p.prospect_id}`}>
                <option value="new">New</option>
                <option value="contacted">Contacted</option>
                <option value="demo_given">Demo Given</option>
                <option value="negotiating">Negotiating</option>
                <option value="converted">Converted</option>
                <option value="lost">Lost</option>
              </select>
              {p.status !== 'converted' && p.status !== 'lost' && (
                <button onClick={() => onConvert(p)}
                  className="text-xs bg-green-600 text-white px-3 py-1.5 rounded-lg font-medium hover:bg-green-700 flex items-center gap-1"
                  data-testid={`convert-${p.prospect_id}`}>
                  <ArrowRightCircle size={12} /> Convert
                </button>
              )}
            </div>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
            <div><span className="text-slate-400">Plan:</span> <span className="ml-1 capitalize">{p.selected_plan || '—'}</span></div>
            <div><span className="text-slate-400">Demo:</span> <span className={`ml-1 ${p.demo_completed ? 'text-green-600' : p.demo_requested ? 'text-amber-600' : 'text-slate-400'}`}>{p.demo_completed ? 'Done' : p.demo_requested ? 'Requested' : '—'}</span></div>
            <div><span className="text-slate-400">Phone:</span> <span className="ml-1">{p.phone || '—'}</span></div>
            <div><span className="text-slate-400">Date:</span> <span className="ml-1">{formatDate(p.created_at)}</span></div>
          </div>
          {isOpen && (
            <div className="mt-3 pt-3 border-t border-slate-100 grid grid-cols-1 md:grid-cols-3 gap-3 text-xs" data-testid={`prospect-drill-${p.prospect_id}`}>
              <div><span className="text-slate-400 block">Industry</span><span className="text-slate-700">{p.industry || '—'}</span></div>
              <div><span className="text-slate-400 block">Employees</span><span className="text-slate-700">{p.employees_count || '—'}</span></div>
              <div><span className="text-slate-400 block">Demo Given On</span><span className="text-slate-700">{p.demo_given_at ? formatDate(p.demo_given_at) : '—'}</span></div>
              <div className="md:col-span-3"><span className="text-slate-400 block">Notes</span><span className="text-slate-600">{p.notes || 'No notes recorded yet.'}</span></div>
            </div>
          )}
        </div>
        );
      })}
      {filtered.length === 0 && <p className="text-center text-slate-400 py-8">No prospects in this filter</p>}
    </div>

    {/* iter-122 — Demo Given date picker modal */}
    {demoDateFor && (
      <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4" data-testid="demo-date-modal"
           onClick={e => e.target === e.currentTarget && setDemoDateFor(null)}>
        <div className="bg-white rounded-xl w-full max-w-sm p-6">
          <h3 className="text-base font-semibold text-slate-900 mb-1 flex items-center gap-2"><Calendar size={16} className="text-emerald-600" /> When was the demo given?</h3>
          <p className="text-xs text-slate-500 mb-4">This helps us track demo→convert funnels accurately.</p>
          <input type="date" value={demoDate}
            onChange={e => setDemoDate(e.target.value)}
            max={new Date().toISOString().slice(0, 10)}
            className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm" data-testid="demo-date-input" />
          <div className="flex justify-end gap-2 mt-5">
            <button onClick={() => setDemoDateFor(null)} className="px-4 py-2 text-sm border border-slate-200 rounded-lg" data-testid="demo-date-cancel">Cancel</button>
            <button onClick={confirmDemoDate} className="px-4 py-2 text-sm bg-emerald-600 text-white rounded-lg hover:bg-emerald-700" data-testid="demo-date-confirm">Save</button>
          </div>
        </div>
      </div>
    )}
  </div>
  );
};
