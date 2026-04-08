import React from 'react';
import { Wifi, WifiOff, Loader2, CheckCircle2, AlertCircle, ArrowDownToLine } from 'lucide-react';

const SyncStatusBar = ({ wsConnected, syncProgress }) => {
  if (!syncProgress?.isSyncing && !syncProgress?.phase) return null;

  const isSyncing = syncProgress?.isSyncing;
  const phase = syncProgress?.phase;
  const progress = syncProgress?.progress || 0;
  const message = syncProgress?.message || '';

  if (phase === 'complete') {
    return (
      <div
        className="flex items-center gap-3 px-4 py-2.5 bg-emerald-50 border border-emerald-200 rounded-xl text-sm"
        data-testid="sync-status-complete"
      >
        <CheckCircle2 size={16} className="text-emerald-600 flex-shrink-0" />
        <span className="text-emerald-800 font-medium">Sync complete</span>
        <div className="flex items-center gap-3 ml-auto text-xs text-emerald-600">
          {syncProgress.inventoryCount != null && (
            <span>{syncProgress.inventoryCount} items</span>
          )}
          {syncProgress.salesCount != null && (
            <span>{syncProgress.salesCount} sales</span>
          )}
          {syncProgress.customerCount != null && (
            <span>{syncProgress.customerCount} customers</span>
          )}
        </div>
      </div>
    );
  }

  if (phase === 'error') {
    return (
      <div
        className="flex items-center gap-3 px-4 py-2.5 bg-red-50 border border-red-200 rounded-xl text-sm"
        data-testid="sync-status-error"
      >
        <AlertCircle size={16} className="text-red-600 flex-shrink-0" />
        <span className="text-red-800">{message}</span>
      </div>
    );
  }

  if (!isSyncing) return null;

  return (
    <div
      className="px-4 py-3 bg-blue-50 border border-blue-200 rounded-xl"
      data-testid="sync-status-progress"
    >
      <div className="flex items-center gap-3 text-sm">
        <Loader2 size={16} className="text-blue-600 animate-spin flex-shrink-0" />
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between mb-1">
            <span className="text-blue-800 font-medium truncate">{message}</span>
            {syncProgress.currentBatch > 0 && (
              <span className="text-xs text-blue-500 ml-2 flex-shrink-0">
                Batch {syncProgress.currentBatch}/{syncProgress.totalBatches}
              </span>
            )}
          </div>
          {progress > 0 && (
            <div className="w-full bg-blue-100 rounded-full h-1.5">
              <div
                className="bg-gradient-to-r from-blue-500 to-purple-500 h-1.5 rounded-full transition-all duration-500"
                style={{ width: `${progress}%` }}
              />
            </div>
          )}
          {syncProgress.vouchersSoFar > 0 && (
            <div className="flex items-center gap-1 mt-1 text-xs text-blue-500">
              <ArrowDownToLine size={12} />
              <span>{syncProgress.vouchersSoFar} vouchers fetched so far</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export const SyncConnectionBadge = ({ wsConnected }) => {
  return (
    <div
      className={`flex items-center gap-1.5 text-xs px-2 py-1 rounded-full ${
        wsConnected
          ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
          : 'bg-slate-50 text-slate-500 border border-slate-200'
      }`}
      data-testid="ws-connection-badge"
      title={wsConnected ? 'Real-time sync connected' : 'Real-time sync disconnected'}
    >
      {wsConnected ? (
        <Wifi size={12} className="text-emerald-600" />
      ) : (
        <WifiOff size={12} className="text-slate-400" />
      )}
      <span>{wsConnected ? 'Live' : 'Offline'}</span>
    </div>
  );
};

export default SyncStatusBar;
