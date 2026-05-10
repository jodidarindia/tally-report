import React from 'react';
import { Plus, Pencil, Key, Trash2, ToggleLeft, ToggleRight, ChevronDown, ChevronUp } from 'lucide-react';
import { ALL_FEATURES, formatDate } from '../utils';

export const AdminsTab = ({
  admins, expandedAdmin, setExpandedAdmin,
  onCreateAdmin, onToggleActive, onEditAdmin, onResetPassword, onDeleteAdmin,
}) => (
  <div data-testid="admins-tab">
    <div className="flex items-center justify-between mb-6">
      <h2 className="text-lg font-semibold text-slate-900">Admin Management</h2>
      <button onClick={onCreateAdmin} className="px-4 py-2 text-sm bg-[#2563EB] text-white rounded-lg hover:bg-[#1D4ED8] flex items-center gap-1.5" data-testid="create-admin-btn">
        <Plus size={14} /> New Admin
      </button>
    </div>
    <div className="space-y-4">
      {admins.map(admin => {
        const subMonths = admin.subscription_months || 12;
        const subStart = admin.subscription_start || admin.created_at || '';
        let subEndDate = '—';
        if (subStart) { const s = new Date(subStart); const e = new Date(s); e.setMonth(e.getMonth() + subMonths); subEndDate = formatDate(e.toISOString()); }
        return (
          <div key={admin.username} className="bg-white border border-slate-200 rounded-xl overflow-hidden" data-testid={`admin-card-${admin.username}`}>
            <div className="p-5">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-4 flex-1 min-w-0 cursor-pointer" onClick={() => setExpandedAdmin(expandedAdmin === admin.username ? null : admin.username)}>
                  <div className={`w-3 h-3 rounded-full flex-shrink-0 ${admin.active ? 'bg-green-500' : 'bg-red-400'}`} />
                  <div className="min-w-0">
                    <div className="font-semibold text-slate-900">{admin.name || admin.username}</div>
                    <div className="text-xs text-slate-500">@{admin.username} · {admin.employee_count || 0}/{admin.max_employees || 20} employees</div>
                  </div>
                </div>
                <div className="flex items-center gap-2 flex-shrink-0">
                  <span className={`text-[10px] px-2 py-0.5 rounded-full font-bold uppercase ${admin.plan === 'enterprise' ? 'bg-purple-50 text-purple-700' : admin.plan === 'professional' ? 'bg-blue-50 text-blue-700' : 'bg-slate-100 text-slate-600'}`}>{admin.plan || 'enterprise'}</span>
                  <button onClick={e => { e.stopPropagation(); onToggleActive(admin.username); }} className={`px-3 py-1.5 text-xs rounded-lg font-medium flex items-center gap-1 ${admin.active ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'}`} data-testid={`toggle-active-${admin.username}`}>
                    {admin.active ? <ToggleRight size={14} /> : <ToggleLeft size={14} />} {admin.active ? 'Active' : 'Inactive'}
                  </button>
                  <button onClick={e => { e.stopPropagation(); onEditAdmin(admin); }} className="p-1.5 text-slate-400 hover:text-blue-600 hover:bg-blue-50 rounded-lg" data-testid={`edit-admin-${admin.username}`}><Pencil size={14} /></button>
                  <button onClick={e => { e.stopPropagation(); onResetPassword(admin.username); }} className="p-1.5 text-slate-400 hover:text-blue-600 hover:bg-blue-50 rounded-lg" data-testid={`reset-pwd-${admin.username}`}><Key size={14} /></button>
                  <button onClick={e => { e.stopPropagation(); onDeleteAdmin(admin.username); }} className="p-1.5 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded-lg" data-testid={`delete-admin-${admin.username}`}><Trash2 size={14} /></button>
                  <button onClick={() => setExpandedAdmin(expandedAdmin === admin.username ? null : admin.username)} className="p-1.5 text-slate-400 rounded-lg" data-testid={`expand-admin-${admin.username}`}>
                    {expandedAdmin === admin.username ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                  </button>
                </div>
              </div>
            </div>
            {expandedAdmin === admin.username && (
              <div className="border-t border-slate-100 p-5 bg-slate-50 space-y-4">
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                  <div><span className="text-slate-400 text-xs">Companies:</span><div className="font-medium">{admin.companies?.join(', ') || 'None'}</div></div>
                  <div><span className="text-slate-400 text-xs">Subscription:</span><div className="font-medium">{formatDate(subStart)} → {subEndDate}</div></div>
                  <div><span className="text-slate-400 text-xs">Billing:</span><div className="font-medium capitalize">{admin.billing_cycle || 'annual'} · {subMonths}mo</div></div>
                  <div><span className="text-slate-400 text-xs">Features:</span><div className="font-medium">{admin.features?.length || 0}/{ALL_FEATURES.length}</div></div>
                </div>
                <div className="flex flex-wrap gap-1">
                  {ALL_FEATURES.map(f => (
                    <span key={f.id} className={`text-[10px] px-2 py-0.5 rounded ${admin.features?.includes(f.id) ? 'bg-emerald-50 text-emerald-700' : 'bg-slate-100 text-slate-400'}`}>{f.label}</span>
                  ))}
                </div>
              </div>
            )}
          </div>
        );
      })}
    </div>
  </div>
);
