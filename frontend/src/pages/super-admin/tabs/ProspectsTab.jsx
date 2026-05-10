import React from 'react';
import { ArrowRightCircle } from 'lucide-react';
import { formatDate } from '../utils';

export const ProspectsTab = ({ prospects, prospectStats, onUpdateStatus, onConvert }) => (
  <div data-testid="prospects-tab">
    <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-6">
      {[
        { label: 'Total', value: prospectStats.total || 0, color: 'text-slate-700' },
        { label: 'New', value: prospectStats.new || 0, color: 'text-blue-600' },
        { label: 'Contacted', value: prospectStats.contacted || 0, color: 'text-amber-600' },
        { label: 'Converted', value: prospectStats.converted || 0, color: 'text-emerald-600' },
        { label: 'Lost', value: prospectStats.lost || 0, color: 'text-red-600' },
      ].map(s => (
        <div key={s.label} className="bg-white border border-slate-200 rounded-xl p-4">
          <p className="text-xs text-slate-500">{s.label}</p>
          <p className={`text-xl font-bold ${s.color}`}>{s.value}</p>
        </div>
      ))}
    </div>
    <div className="space-y-3">
      {prospects.map(p => (
        <div key={p.prospect_id} className="bg-white border border-slate-200 rounded-xl p-4" data-testid={`prospect-${p.prospect_id}`}>
          <div className="flex items-center justify-between mb-2">
            <div>
              <h4 className="font-medium text-slate-900">{p.company_name || p.email}</h4>
              <p className="text-xs text-slate-500">{p.email} · {p.contact_person}</p>
            </div>
            <div className="flex items-center gap-2">
              <select value={p.status} onChange={e => onUpdateStatus(p.prospect_id, e.target.value)}
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
        </div>
      ))}
      {prospects.length === 0 && <p className="text-center text-slate-400 py-8">No prospects yet</p>}
    </div>
  </div>
);
