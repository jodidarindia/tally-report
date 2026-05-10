import React from 'react';
import { UserPlus, Pencil, Key, Trash2, ToggleLeft, ToggleRight } from 'lucide-react';
import { formatDate, generateStrongPassword } from '../utils';

export const StaffTab = ({ staffList, onNewStaff, onEditStaff, onResetPassword, onToggleActive, onDeleteStaff }) => (
  <div data-testid="staff-tab">
    <div className="flex items-center justify-between mb-4">
      <div>
        <h2 className="text-lg font-semibold text-slate-900">Flowra Staff (Control-panel employees)</h2>
        <p className="text-xs text-slate-500 mt-0.5">Delegate command-center access. Tick the tabs each employee needs — they only see what's enabled.</p>
      </div>
      <button
        onClick={() => onNewStaff({ _isNew: true, username: '', name: '', password: generateStrongPassword(), features: ['overview'] })}
        className="px-3 py-2 bg-[#2563EB] text-white text-sm font-medium rounded-lg hover:bg-[#1D4ED8] flex items-center gap-1.5"
        data-testid="staff-new-btn">
        <UserPlus size={14} /> New Staff
      </button>
    </div>

    <div className="bg-white border border-slate-200 rounded-xl overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-sm" data-testid="staff-table">
          <thead>
            <tr className="bg-slate-50 text-xs text-slate-500 uppercase">
              <th className="py-3 px-4 text-left">Name / Email</th>
              <th className="py-3 px-4 text-left">Tabs Enabled</th>
              <th className="py-3 px-4 text-left">Created</th>
              <th className="py-3 px-4 text-center">Status</th>
              <th className="py-3 px-4 text-center">Actions</th>
            </tr>
          </thead>
          <tbody>
            {staffList.length === 0 && (
              <tr><td colSpan={5} className="py-12 text-center text-sm text-slate-400">No staff accounts yet. Click "New Staff" to delegate access.</td></tr>
            )}
            {staffList.map(s => (
              <tr key={s.username} className="border-t border-slate-100 hover:bg-slate-50/50" data-testid={`staff-row-${s.username}`}>
                <td className="py-3 px-4">
                  <div className="font-medium text-slate-900">{s.name || s.username}</div>
                  <div className="text-xs text-slate-500">{s.username}</div>
                </td>
                <td className="py-3 px-4">
                  <div className="flex flex-wrap gap-1">
                    {(s.staff_features || []).length === 0 && <span className="text-xs text-slate-400">No tabs enabled</span>}
                    {(s.staff_features || []).map(f => (
                      <span key={f} className="px-2 py-0.5 bg-blue-50 text-blue-700 rounded text-[10px] capitalize">{f.replace(/_/g, ' ')}</span>
                    ))}
                  </div>
                </td>
                <td className="py-3 px-4 text-xs text-slate-500">{formatDate(s.created_at)}</td>
                <td className="py-3 px-4 text-center">
                  <button onClick={() => onToggleActive(s.username)}
                    className={`inline-flex items-center gap-1 px-2 py-1 rounded text-xs font-medium ${s.active ? 'bg-emerald-50 text-emerald-700' : 'bg-slate-100 text-slate-500'}`}
                    data-testid={`staff-toggle-${s.username}`}>
                    {s.active ? <ToggleRight size={14} /> : <ToggleLeft size={14} />}
                    {s.active ? 'Active' : 'Disabled'}
                  </button>
                </td>
                <td className="py-3 px-4">
                  <div className="flex items-center justify-center gap-1">
                    <button onClick={() => onEditStaff({ _isNew: false, username: s.username, name: s.name, features: [...(s.staff_features || [])] })}
                      className="p-1.5 hover:bg-slate-100 rounded text-slate-500" title="Edit features"
                      data-testid={`staff-edit-${s.username}`}>
                      <Pencil size={14} />
                    </button>
                    <button onClick={() => onResetPassword({ username: s.username, password: generateStrongPassword() })}
                      className="p-1.5 hover:bg-slate-100 rounded text-slate-500" title="Reset password"
                      data-testid={`staff-reset-${s.username}`}>
                      <Key size={14} />
                    </button>
                    <button onClick={() => onDeleteStaff(s.username)}
                      className="p-1.5 hover:bg-red-50 rounded text-red-500" title="Delete"
                      data-testid={`staff-delete-${s.username}`}>
                      <Trash2 size={14} />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  </div>
);
