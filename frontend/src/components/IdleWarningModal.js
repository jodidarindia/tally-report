import React from 'react';
import { Clock } from 'lucide-react';

const IdleWarningModal = ({ onDismiss }) => (
  <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-[100]" data-testid="idle-warning-modal">
    <div className="bg-white rounded-2xl max-w-sm w-full mx-4 p-8 text-center shadow-2xl">
      <div className="w-16 h-16 bg-amber-100 rounded-full flex items-center justify-center mx-auto mb-4">
        <Clock size={32} className="text-amber-600" />
      </div>
      <h2 className="text-xl font-bold text-slate-900 mb-2">Session Expiring</h2>
      <p className="text-slate-600 text-sm mb-6">
        You've been idle for a while. Your session will expire in <strong className="text-red-600">1 minute</strong>.
      </p>
      <button
        onClick={onDismiss}
        className="w-full py-3 bg-[#2563EB] text-white rounded-lg font-medium hover:bg-[#1D4ED8] transition-colors"
        data-testid="stay-logged-in-btn"
      >
        Stay Logged In
      </button>
    </div>
  </div>
);

export default IdleWarningModal;
