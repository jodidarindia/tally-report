import React from 'react';
import { AlertTriangle, X } from 'lucide-react';

const RenewalPopup = ({ daysLeft, onDismiss, onOpenSubscription }) => {
  if (daysLeft === null || daysLeft === undefined || daysLeft > 30) return null;

  const isExpired = daysLeft < 0;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-[60]" data-testid="renewal-popup">
      <div className={`bg-white rounded-2xl w-full max-w-md mx-4 p-6 border-2 ${isExpired ? 'border-red-300' : 'border-amber-300'}`}>
        <div className="flex items-start justify-between mb-4">
          <div className={`w-12 h-12 rounded-full flex items-center justify-center ${isExpired ? 'bg-red-100' : 'bg-amber-100'}`}>
            <AlertTriangle size={24} className={isExpired ? 'text-red-600' : 'text-amber-600'} />
          </div>
          <button onClick={onDismiss} className="text-slate-400 hover:text-slate-600" data-testid="renewal-popup-close">
            <X size={20} />
          </button>
        </div>
        <h3 className={`text-lg font-bold mb-2 ${isExpired ? 'text-red-900' : 'text-amber-900'}`}>
          {isExpired ? 'Subscription Expired' : 'Subscription Expiring Soon'}
        </h3>
        <p className="text-sm text-slate-600 mb-4">
          {isExpired
            ? 'Your FLOWRA subscription has expired. Data sync has been disabled. Please renew immediately to continue using all features.'
            : `Your subscription expires in ${daysLeft} day${daysLeft !== 1 ? 's' : ''}. Renew now to avoid any interruption to your Tally sync and analytics access.`
          }
        </p>
        <div className="flex gap-3">
          <button
            onClick={onOpenSubscription}
            className={`flex-1 py-2.5 rounded-lg font-medium text-sm text-white ${isExpired ? 'bg-red-600 hover:bg-red-700' : 'bg-amber-600 hover:bg-amber-700'}`}
            data-testid="renewal-popup-renew"
          >
            Renew Now
          </button>
          <button
            onClick={onDismiss}
            className="px-4 py-2.5 border border-slate-200 rounded-lg text-sm text-slate-600 hover:bg-slate-50"
            data-testid="renewal-popup-dismiss"
          >
            Remind Later
          </button>
        </div>
      </div>
    </div>
  );
};

export default RenewalPopup;
