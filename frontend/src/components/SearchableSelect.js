import React, { useState, useRef, useEffect } from 'react';
import { Search, ChevronDown, X, Check } from 'lucide-react';

/**
 * Searchable dropdown select component.
 * Props:
 *  - options: string[] — sorted automatically
 *  - value: string | string[] — currently selected
 *  - onChange: (val) => void
 *  - placeholder: string
 *  - multiple: boolean — checkbox mode
 *  - disabled: boolean
 *  - testId: string
 */
const SearchableSelect = ({
  options = [],
  value,
  onChange,
  placeholder = 'Select...',
  multiple = false,
  disabled = false,
  testId = 'searchable-select',
}) => {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState('');
  const ref = useRef(null);
  const inputRef = useRef(null);

  const sorted = [...options].sort((a, b) => (a || '').localeCompare(b || '', 'en', { sensitivity: 'base' }));
  const filtered = search
    ? sorted.filter(o => (o || '').toLowerCase().includes(search.toLowerCase()))
    : sorted;

  useEffect(() => {
    const handler = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  useEffect(() => {
    if (open && inputRef.current) inputRef.current.focus();
  }, [open]);

  const handleSelect = (opt) => {
    if (multiple) {
      const arr = Array.isArray(value) ? value : [];
      onChange(arr.includes(opt) ? arr.filter(v => v !== opt) : [...arr, opt]);
    } else {
      onChange(opt);
      setOpen(false);
      setSearch('');
    }
  };

  const displayText = multiple
    ? (Array.isArray(value) && value.length > 0 ? `${value.length} selected` : placeholder)
    : (value || placeholder);

  const isSelected = (opt) => multiple
    ? (Array.isArray(value) && value.includes(opt))
    : value === opt;

  return (
    <div className="relative" ref={ref} data-testid={testId}>
      <button
        type="button"
        disabled={disabled}
        onClick={() => setOpen(!open)}
        className={`w-full flex items-center justify-between px-3 py-2 border rounded-lg text-sm text-left transition-colors ${
          disabled ? 'bg-slate-50 text-slate-400 cursor-not-allowed border-slate-200'
          : open ? 'border-blue-500 ring-2 ring-blue-100' : 'border-slate-200 hover:border-slate-300'
        } ${!value || (Array.isArray(value) && value.length === 0) ? 'text-slate-400' : 'text-slate-800'}`}
        data-testid={`${testId}-trigger`}
      >
        <span className="truncate">{displayText}</span>
        <ChevronDown size={14} className={`flex-shrink-0 text-slate-400 transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>

      {open && (
        <div className="absolute z-50 mt-1 w-full bg-white border border-slate-200 rounded-lg shadow-lg max-h-64 flex flex-col" data-testid={`${testId}-dropdown`}>
          <div className="p-2 border-b border-slate-100">
            <div className="relative">
              <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400" />
              <input
                ref={inputRef}
                value={search}
                onChange={e => setSearch(e.target.value)}
                placeholder="Type to search..."
                className="w-full pl-8 pr-8 py-1.5 text-xs border border-slate-200 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500"
                data-testid={`${testId}-search`}
              />
              {search && (
                <button onClick={() => setSearch('')} className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600">
                  <X size={12} />
                </button>
              )}
            </div>
          </div>
          <div className="overflow-y-auto flex-1">
            {filtered.length === 0 ? (
              <div className="px-3 py-4 text-xs text-slate-400 text-center">No results found</div>
            ) : filtered.map((opt, i) => (
              <button
                key={i}
                type="button"
                onClick={() => handleSelect(opt)}
                className={`w-full flex items-center gap-2 px-3 py-2 text-xs text-left hover:bg-blue-50 transition-colors ${
                  isSelected(opt) ? 'bg-blue-50 text-blue-700 font-medium' : 'text-slate-700'
                }`}
                data-testid={`${testId}-option-${i}`}
              >
                {multiple && (
                  <div className={`w-4 h-4 rounded border flex items-center justify-center flex-shrink-0 ${
                    isSelected(opt) ? 'bg-blue-600 border-blue-600' : 'border-slate-300'
                  }`}>
                    {isSelected(opt) && <Check size={10} className="text-white" />}
                  </div>
                )}
                <span className="truncate">{opt}</span>
                {!multiple && isSelected(opt) && <Check size={12} className="ml-auto text-blue-600 flex-shrink-0" />}
              </button>
            ))}
          </div>
          {multiple && (
            <div className="p-2 border-t border-slate-100 flex items-center justify-between">
              <span className="text-[10px] text-slate-400">
                {Array.isArray(value) ? value.length : 0} / {options.length} selected
              </span>
              <button
                type="button"
                onClick={() => setOpen(false)}
                className="text-xs text-blue-600 font-medium hover:text-blue-700"
              >
                Done
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default SearchableSelect;
