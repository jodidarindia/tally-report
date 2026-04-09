import React, { useState, useEffect } from 'react';
import { Building2, ChevronRight } from 'lucide-react';

const CompanySelector = ({ companies, onSelect }) => {
  const [selected, setSelected] = useState('');

  // Auto-select if only one company
  useEffect(() => {
    if (companies && companies.length === 1) {
      onSelect(companies[0]);
    }
  }, [companies, onSelect]);

  if (!companies || companies.length <= 1) return null;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" data-testid="company-selector-modal">
      <div className="bg-white rounded-2xl p-8 w-full max-w-md mx-4">
        <div className="text-center mb-6">
          <div className="w-14 h-14 bg-blue-50 rounded-full flex items-center justify-center mx-auto mb-4">
            <Building2 size={28} className="text-[#2563EB]" />
          </div>
          <h2 className="text-xl font-bold text-slate-900">Select Company</h2>
          <p className="text-sm text-slate-500 mt-1">Choose which company data to view</p>
        </div>
        <div className="space-y-2 mb-6">
          {companies.map((company, idx) => (
            <button
              key={idx}
              onClick={() => setSelected(company)}
              className={`w-full p-4 rounded-xl border text-left transition-all flex items-center justify-between ${
                selected === company
                  ? 'border-[#2563EB] bg-blue-50 ring-2 ring-blue-100'
                  : 'border-slate-200 hover:border-slate-300 hover:bg-slate-50'
              }`}
              data-testid={`company-option-${idx}`}
            >
              <div className="flex items-center gap-3">
                <Building2 size={18} className={selected === company ? 'text-[#2563EB]' : 'text-slate-400'} />
                <span className={`font-medium ${selected === company ? 'text-[#2563EB]' : 'text-slate-700'}`}>{company}</span>
              </div>
              {selected === company && <ChevronRight size={18} className="text-[#2563EB]" />}
            </button>
          ))}
        </div>
        <button
          onClick={() => selected && onSelect(selected)}
          disabled={!selected}
          className="w-full py-3 bg-[#2563EB] text-white rounded-xl font-medium hover:bg-[#1D4ED8] disabled:opacity-50 disabled:cursor-not-allowed"
          data-testid="confirm-company-selection"
        >
          Continue
        </button>
      </div>
    </div>
  );
};

export default CompanySelector;
