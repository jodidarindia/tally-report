import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Download, Search, Filter, Sparkles, ChevronDown, RefreshCw, Edit2, Check, X } from 'lucide-react';
import { toast } from 'sonner';
import { fuzzyMatchAny } from '../utils/fuzzySearch';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const Inventory = ({ selectedFY, excludeBranches }) => {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('all');
  const [selectedGroups, setSelectedGroups] = useState([]);
  const [showGroupDropdown, setShowGroupDropdown] = useState(false);
  const [categories, setCategories] = useState([]);
  const [stockGroups, setStockGroups] = useState([]);
  const [rootStockGroups, setRootStockGroups] = useState([]);
  const [selectedRootGroup, setSelectedRootGroup] = useState('all');
  const [showPOModal, setShowPOModal] = useState(false);
  const [purchaseOrder, setPurchaseOrder] = useState(null);
  const [generatingPO, setGeneratingPO] = useState(false);
  const [sortField, setSortField] = useState('item_name');
  const [sortDir, setSortDir] = useState('asc');
  const [editingReorder, setEditingReorder] = useState(null);
  const [reorderValue, setReorderValue] = useState('');
  const [autoReorderLoading, setAutoReorderLoading] = useState(false);
  const [autoAbcLoading, setAutoAbcLoading] = useState(false);
  const [editingAbc, setEditingAbc] = useState(null);
  const [abcFilter, setAbcFilter] = useState('all');
  // Mobile-friendly: render incrementally rather than slamming 7,500 rows
  // into the DOM on first paint. KSC-scale tenants hung the mobile browser
  // for 8-12 seconds. Default page size keeps initial render under 100ms.
  const [renderLimit, setRenderLimit] = useState(200);
  const [searchQuery, setSearchQuery] = useState('');

  useEffect(() => {
    fetchInventory();
  }, [selectedGroups, selectedRootGroup, excludeBranches, selectedFY]);

  const fetchInventory = async () => {
    setLoading(true);
    try {
      const params = {};
      if (selectedGroups.length > 0) params.stock_group = selectedGroups.join(',');
      if (selectedRootGroup && selectedRootGroup !== 'all') params.root_stock_group = selectedRootGroup;
      if (selectedFY) params.fy = selectedFY;
      const response = await axios.get(`${API}/inventory/items`, { params });
      const itemsData = response.data?.data?.items || [];
      setItems(itemsData);

      const uniqueCategories = [...new Set(itemsData.map(item => item.category).filter(Boolean))];
      setCategories(uniqueCategories);

      const groups = response.data?.data?.stock_groups || [];
      if (groups.length > 0) setStockGroups(groups);
      const rootGroups = response.data?.data?.root_stock_groups || [];
      // Only update if we got a non-empty list (preserves dropdown when filtering by sub-group)
      if (rootGroups.length > 0) setRootStockGroups(rootGroups);
    } catch (error) {
      console.error('Error fetching inventory:', error);
    } finally {
      setLoading(false);
    }
  };

  const exportData = async (format) => {
    try {
      // iter-111: pass current UI filters so the file matches what the user sees,
      // and map format → real file extension (csv|xlsx|pdf) so the browser
      // saves with the correct suffix (Excel was being saved as ".excel").
      const filters = {
        category: selectedCategory !== 'all' ? selectedCategory : undefined,
        stock_group: selectedGroups.length > 0 ? selectedGroups.join(',') : undefined,
        root_stock_group: selectedRootGroup !== 'all' ? selectedRootGroup : undefined,
        abc: abcFilter !== 'all' ? abcFilter : undefined,
        search: (searchTerm || '').trim() || undefined,
      };
      const response = await axios.post(
        `${API}/reports/export`,
        { report_type: 'inventory', format, filters },
        { responseType: 'blob' }
      );

      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      const extMap = { csv: 'csv', excel: 'xlsx', pdf: 'pdf' };
      const ext = extMap[format] || format;
      link.setAttribute('download', `inventory_report.${ext}`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (error) {
      console.error('Error exporting data:', error);
      toast.error('Export failed');
    }
  };

  const generatePurchaseOrder = async () => {
    setGeneratingPO(true);
    try {
      const response = await axios.post(`${API}/inventory/generate-purchase-order`);
      
      if (response.data?.success) {
        setPurchaseOrder(response.data.data);
        setShowPOModal(true);
        toast.success('Purchase order generated successfully!');
      } else {
        toast.error(response.data?.error || 'Failed to generate purchase order');
      }
    } catch (error) {
      console.error('Error generating PO:', error);
      toast.error('Failed to generate purchase order');
    } finally {
      setGeneratingPO(false);
    }
  };

  const autoSetReorderLevels = async () => {
    setAutoReorderLoading(true);
    try {
      const res = await axios.post(`${API}/inventory/auto-reorder-levels`, {});
      if (res.data?.success) {
        toast.success(res.data.message);
        fetchInventory();
      } else toast.error(res.data?.error || 'Failed');
    } catch { toast.error('Failed to set auto reorder levels'); }
    finally { setAutoReorderLoading(false); }
  };

  const saveReorderLevel = async (itemId) => {
    try {
      const res = await axios.post(`${API}/inventory/set-reorder-level`, { item_id: itemId, reorder_level: parseFloat(reorderValue) || 0 });
      if (res.data?.success) {
        toast.success('Reorder level updated');
        setEditingReorder(null);
        fetchInventory();
      } else toast.error(res.data?.error || 'Failed');
    } catch { toast.error('Failed to update reorder level'); }
  };

  const setAbc = async (itemId, abc) => {
    try {
      const res = await axios.patch(`${API}/inventory/items/${encodeURIComponent(itemId)}/abc`, { abc_category: abc });
      if (res.data?.success) {
        toast.success(`Set to ${abc || '—'}`);
        setEditingAbc(null);
        // Optimistic update
        setItems(prev => prev.map(it => it.item_id === itemId ? {...it, abc_category: abc} : it));
      } else toast.error(res.data?.error || 'Failed');
    } catch { toast.error('Failed to set ABC category'); }
  };

  const autoAssignAbc = async () => {
    if (!window.confirm('Auto-assign A/B/C/D using Pareto analysis?\n\nA = top 80% revenue\nB = next 15%\nC = next 4%\nD = remainder (incl. zero-revenue items)\n\nThis will overwrite existing tags.')) return;
    setAutoAbcLoading(true);
    try {
      const res = await axios.post(`${API}/inventory/abc/auto-assign`, { fy: selectedFY || '' });
      if (res.data?.success) {
        const c = res.data.data.counts;
        toast.success(`Done — A:${c.A} B:${c.B} C:${c.C} D:${c.D}`);
        fetchInventory();
      } else toast.error(res.data?.error || 'Failed');
    } catch { toast.error('Auto-assign failed'); }
    finally { setAutoAbcLoading(false); }
  };

  const ABC_COLORS = { A:'#10b981', B:'#3b82f6', C:'#f59e0b', D:'#94a3b8' };

  const filteredItems = items.filter(item => {
    // Fuzzy match — ignores spaces & separator chars (-/()!:.,&_'") so
    // "tvs 10" matches "TVS-10", "TVS(10)", "TVS/10". Searches across
    // item_name, part_number AND aliases (Tally LANGUAGENAME).
    const matchesSearch = !searchTerm || fuzzyMatchAny(searchTerm, [
      item.item_name, item.part_number, item.aliases,
    ]);
    const matchesCategory = selectedCategory === 'all' || item.category === selectedCategory;
    const matchesGroup = selectedGroups.length === 0 || selectedGroups.includes(item.stock_group);
    const matchesAbc = abcFilter === 'all' || (item.abc_category || '') === abcFilter;
    return matchesSearch && matchesCategory && matchesGroup && matchesAbc;
  }).sort((a, b) => {
    const dir = sortDir === 'asc' ? 1 : -1;
    if (sortField === 'item_name') return dir * (a.item_name || '').localeCompare(b.item_name || '');
    if (sortField === 'quantity') return dir * ((a.quantity || 0) - (b.quantity || 0));
    if (sortField === 'price') return dir * ((a.price || 0) - (b.price || 0));
    if (sortField === 'standard_price') {
      const aPrice = a.standard_price > 0 ? a.standard_price : (a.last_sale_price || 0);
      const bPrice = b.standard_price > 0 ? b.standard_price : (b.last_sale_price || 0);
      return dir * (aPrice - bPrice);
    }
    if (sortField === 'value') return dir * (((a.quantity || 0) * (a.price || 0)) - ((b.quantity || 0) * (b.price || 0)));
    if (sortField === 'stock_group') return dir * (a.stock_group || '').localeCompare(b.stock_group || '');
    if (sortField === 'abc_category') return dir * ((a.abc_category || 'Z').localeCompare(b.abc_category || 'Z'));
    return 0;
  });

  // Render-cap: only paint `renderLimit` rows at a time. "Load more" button
  // adds another 200. Keeps mobile DOM under 200-400 rows even for 7,500-item
  // tenants. Reset cap when search/filter changes.
  const visibleItems = filteredItems.slice(0, renderLimit);

  // Reset render-cap when filter / search / sort changes — otherwise a small
  // result set might be invisible (page 36 of 36). Keeps initial paint cheap.
  useEffect(() => { setRenderLimit(200); }, [searchTerm, selectedCategory, selectedGroups, selectedRootGroup, abcFilter, sortField, sortDir]);

  const handleSort = (field) => {
    if (sortField === field) setSortDir(sortDir === 'asc' ? 'desc' : 'asc');
    else { setSortField(field); setSortDir('asc'); }
  };

  const SortHeader = ({ field, label, className = '' }) => (
    <th className={`cursor-pointer select-none hover:bg-slate-50 ${className}`} onClick={() => handleSort(field)} data-testid={`sort-${field}`}>
      <span className="flex items-center gap-1">{label} {sortField === field ? (sortDir === 'asc' ? '↑' : '↓') : ''}</span>
    </th>
  );

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64" data-testid="inventory-loading">
        <div className="loading-spinner" />
        <span className="ml-3 text-slate-600">Loading inventory...</span>
      </div>
    );
  }

  return (
    <div data-testid="inventory-page">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between mb-6 gap-3">
        <div>
          <h1 className="text-2xl sm:text-4xl font-light tracking-tight text-slate-900" style={{ fontFamily: 'Outfit, sans-serif' }}>
            Inventory
          </h1>
          <p className="mt-1 text-sm text-slate-600">Manage your stock items</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            onClick={generatePurchaseOrder}
            disabled={generatingPO}
            className="btn-primary flex items-center gap-1.5 text-xs sm:text-sm"
            data-testid="generate-po-button"
          >
            <Sparkles size={14} />
            {generatingPO ? 'Generating...' : 'AI PO'}
          </button>
          <button data-testid="export-pdf-button" onClick={() => exportData('pdf')} className="btn-secondary flex items-center gap-1.5 text-xs sm:text-sm">
            <Download size={14} /> PDF
          </button>
          <button data-testid="export-excel-button" onClick={() => exportData('excel')} className="btn-secondary flex items-center gap-1.5 text-xs sm:text-sm">
            <Download size={14} /> Excel
          </button>
          <button
            onClick={autoSetReorderLevels}
            disabled={autoReorderLoading}
            className="flex items-center gap-1.5 text-xs sm:text-sm px-3 py-2 bg-amber-500 text-white rounded-lg hover:bg-amber-600 disabled:opacity-50"
            data-testid="auto-reorder-btn"
            title="Set reorder levels based on 2-month average sales"
          >
            <RefreshCw size={14} className={autoReorderLoading ? 'animate-spin' : ''} />
            {autoReorderLoading ? 'Calculating...' : 'Auto Reorder'}
          </button>
          <button
            onClick={autoAssignAbc}
            disabled={autoAbcLoading}
            className="flex items-center gap-1.5 text-xs sm:text-sm px-3 py-2 bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 disabled:opacity-50"
            data-testid="auto-abc-btn"
            title="Auto-assign A/B/C/D using Pareto (80-15-4-1) revenue analysis"
          >
            <Sparkles size={14} className={autoAbcLoading ? 'animate-pulse' : ''} />
            {autoAbcLoading ? 'Analyzing...' : 'Auto ABC'}
          </button>
          <button data-testid="export-csv-button" onClick={() => exportData('csv')} className="btn-primary flex items-center gap-1.5 text-xs sm:text-sm">
            <Download size={14} /> CSV
          </button>
        </div>
      </div>

      <div className="bg-white border border-slate-200 rounded-xl p-3 sm:p-6 mb-6">
        <div className="flex flex-col sm:flex-row gap-3">
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-slate-400" size={18} />
            <input
              type="text"
              data-testid="search-inventory-input"
              placeholder="Search items..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-10 pr-4 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#2563EB] focus:border-transparent"
            />
          </div>
          <div className="relative">
            <Filter className="absolute left-3 top-1/2 transform -translate-y-1/2 text-slate-400" size={18} />
            <select
              data-testid="root-stock-group-filter"
              value={selectedRootGroup}
              onChange={(e) => setSelectedRootGroup(e.target.value)}
              className="pl-10 pr-8 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#2563EB] focus:border-transparent appearance-none bg-white text-sm min-w-[180px] capitalize"
              title="Tally Primary (root) stock-group filter"
            >
              <option value="all">All Primary Groups</option>
              {[...rootStockGroups].sort((a, b) => a.localeCompare(b, 'en', { sensitivity: 'base' })).map(g => (
                <option key={g} value={g} className="capitalize">{g}</option>
              ))}
            </select>
          </div>
          <div className="relative">
            <button
              onClick={() => setShowGroupDropdown(!showGroupDropdown)}
              className="flex items-center gap-2 pl-10 pr-8 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#2563EB] bg-white text-sm min-w-[180px]"
              data-testid="stock-group-filter"
            >
              <Filter className="absolute left-3 top-1/2 transform -translate-y-1/2 text-slate-400" size={18} />
              {selectedGroups.length === 0 ? 'All Stock Groups' : `${selectedGroups.length} group${selectedGroups.length > 1 ? 's' : ''}`}
              <ChevronDown size={14} className="ml-auto text-slate-400" />
            </button>
            {showGroupDropdown && (
              <div className="absolute z-20 mt-1 bg-white border border-slate-200 rounded-lg shadow-lg max-h-60 overflow-y-auto w-64" data-testid="stock-group-dropdown">
                <div className="p-2 border-b border-slate-100">
                  <button onClick={() => setSelectedGroups([])} className="text-xs text-[#2563EB] hover:underline">Clear all</button>
                </div>
                {[...stockGroups].sort((a, b) => a.localeCompare(b, 'en', { sensitivity: 'base' })).map(g => (
                  <label key={g} className="flex items-center gap-2 px-3 py-2 hover:bg-slate-50 cursor-pointer text-sm">
                    <input
                      type="checkbox"
                      checked={selectedGroups.includes(g)}
                      onChange={() => {
                        setSelectedGroups(prev =>
                          prev.includes(g) ? prev.filter(x => x !== g) : [...prev, g]
                        );
                      }}
                      className="rounded border-slate-300"
                    />
                    {g}
                  </label>
                ))}
              </div>
            )}
          </div>
          <div className="relative">
            <Filter className="absolute left-3 top-1/2 transform -translate-y-1/2 text-slate-400" size={18} />
            <select
              data-testid="category-filter-select"
              value={selectedCategory}
              onChange={(e) => setSelectedCategory(e.target.value)}
              className="pl-10 pr-8 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#2563EB] focus:border-transparent appearance-none bg-white"
            >
              <option value="all">All Categories</option>
              {[...categories].sort((a, b) => a.localeCompare(b, 'en', { sensitivity: 'base' })).map(cat => (
                <option key={cat} value={cat}>{cat}</option>
              ))}
            </select>
          </div>
          <div className="relative">
            <Filter className="absolute left-3 top-1/2 transform -translate-y-1/2 text-slate-400" size={18} />
            <select
              data-testid="abc-filter-select"
              value={abcFilter}
              onChange={(e) => setAbcFilter(e.target.value)}
              className="pl-10 pr-8 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#2563EB] focus:border-transparent appearance-none bg-white text-sm"
            >
              <option value="all">All ABC</option>
              <option value="A">A only</option>
              <option value="B">B only</option>
              <option value="C">C only</option>
              <option value="D">D only</option>
              <option value="">Untagged</option>
            </select>
          </div>
        </div>
      </div>

      <div className="bg-white border border-slate-200 rounded-xl overflow-auto max-h-[calc(100vh-280px)]">
          <table className="data-table min-w-[800px]" data-testid="inventory-table">
            <thead>
              <tr>
                <SortHeader field="item_name" label="Item Name" />
                <th>Part No.</th>
                <SortHeader field="stock_group" label="Stock Group" />
                <SortHeader field="abc_category" label="ABC" />
                <SortHeader field="quantity" label="Quantity" className="numeric" />
                <th>Unit</th>
                <SortHeader field="standard_price" label="Sale Price" className="numeric" />
                <SortHeader field="price" label="Cost (Pre-GST)" className="numeric" />
                <SortHeader field="value" label="Value (Pre-GST)" className="numeric" />
                <th className="numeric">Reorder Level</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {filteredItems.length > 0 ? (
                visibleItems.map((item) => {
                  const isLowStock = item.quantity < (item.reorder_level || 0);
                  const itemValue = item.quantity * (item.price || 0);
                  
                  return (
                    <tr key={item.item_id} data-testid={`inventory-row-${item.item_id}`}>
                      <td className="font-medium text-slate-900">
                        <div className="flex flex-col">
                          <span>{item.item_name}</span>
                          {Array.isArray(item.aliases) && item.aliases.length > 0 && (
                            <span className="text-[10px] text-slate-400 mt-0.5" data-testid="alias-chips">
                              alias: {item.aliases.slice(0, 3).join(', ')}{item.aliases.length > 3 ? ` +${item.aliases.length - 3}` : ''}
                            </span>
                          )}
                        </div>
                      </td>
                      <td className="text-slate-500 text-xs">{item.part_number || '-'}</td>
                      <td className="text-slate-600">{item.stock_group || '-'}</td>
                      <td>
                        {editingAbc === item.item_id ? (
                          <div className="flex items-center gap-1">
                            {['A','B','C','D',''].map(v => (
                              <button key={v||'X'} onClick={() => setAbc(item.item_id, v)}
                                className="w-7 h-6 text-[10px] font-bold rounded border border-slate-200 hover:bg-slate-100"
                                style={v ? {color: ABC_COLORS[v]} : {color:'#94a3b8'}}
                                data-testid={`abc-set-${item.item_id}-${v||'clear'}`}>{v || '—'}</button>
                            ))}
                            <button onClick={() => setEditingAbc(null)} className="text-slate-400"><X size={12}/></button>
                          </div>
                        ) : (
                          <button onClick={() => setEditingAbc(item.item_id)}
                            className="px-2 py-0.5 rounded-full text-[10px] font-bold border border-slate-200 hover:bg-slate-50 cursor-pointer"
                            style={item.abc_category ? {color: ABC_COLORS[item.abc_category], background: ABC_COLORS[item.abc_category]+'15', borderColor: ABC_COLORS[item.abc_category]+'40'} : {color:'#94a3b8'}}
                            data-testid={`abc-edit-${item.item_id}`}
                            title="Click to set A/B/C/D">
                            {item.abc_category || '—'}
                          </button>
                        )}
                      </td>
                      <td className="numeric font-semibold">{item.quantity}</td>
                      <td>{item.unit}</td>
                      <td className="numeric font-semibold" data-testid={`sale-price-${item.item_id}`}>
                        {(() => {
                          const stdPrice = item.standard_price || 0;
                          const lastPrice = item.last_sale_price || 0;
                          const lastDate = item.last_sale_date || '';
                          const lastInv = item.last_sale_invoice || '';
                          if (stdPrice > 0) {
                            return (
                              <span className="text-emerald-700" title="From Tally master Standard Selling Rate">
                                ₹{stdPrice.toLocaleString('en-IN')}
                              </span>
                            );
                          }
                          if (lastPrice > 0) {
                            return (
                              <span
                                className="text-slate-700"
                                title={`Last sale: ${lastDate}${lastInv ? ` (Inv ${lastInv})` : ''}\nTally master STANDARDPRICE not set — showing most recent invoice rate.`}
                              >
                                ₹{lastPrice.toLocaleString('en-IN')}
                                <span className="block text-[10px] font-normal text-slate-400 mt-0.5">
                                  Last sold {lastDate ? lastDate.slice(0, 10) : ''}
                                </span>
                              </span>
                            );
                          }
                          return (
                            <span
                              className="text-amber-500 text-xs font-medium"
                              title="No Tally STANDARDPRICE master AND no past sale on record. Set it in Tally → Stock Item → Standard Selling Rate, or sell it once to populate Last Sale price."
                            >
                              Set in Tally
                            </span>
                          );
                        })()}
                      </td>
                      <td className="numeric">₹{(item.price || 0).toLocaleString('en-IN')}</td>
                      <td className="numeric font-semibold">₹{itemValue.toLocaleString('en-IN')}</td>
                      <td className="numeric">
                        {editingReorder === item.item_id ? (
                          <div className="flex items-center gap-1 justify-end">
                            <input type="number" value={reorderValue} onChange={e => setReorderValue(e.target.value)}
                              className="w-16 px-1.5 py-1 border border-slate-300 rounded text-xs text-right" autoFocus
                              onKeyDown={e => { if (e.key === 'Enter') saveReorderLevel(item.item_id); if (e.key === 'Escape') setEditingReorder(null); }}
                              data-testid={`reorder-input-${item.item_id}`} />
                            <button onClick={() => saveReorderLevel(item.item_id)} className="text-green-600 hover:text-green-800" data-testid={`reorder-save-${item.item_id}`}><Check size={14} /></button>
                            <button onClick={() => setEditingReorder(null)} className="text-slate-400 hover:text-slate-600"><X size={14} /></button>
                          </div>
                        ) : (
                          <span className="cursor-pointer hover:text-[#2563EB] group" onClick={() => { setEditingReorder(item.item_id); setReorderValue(item.reorder_level || ''); }}
                            data-testid={`reorder-edit-${item.item_id}`} title="Click to edit">
                            {item.reorder_level || '-'}
                            <Edit2 size={10} className="inline ml-1 opacity-0 group-hover:opacity-100 text-slate-400" />
                          </span>
                        )}
                      </td>
                      <td>
                        {isLowStock ? (
                          <span className="status-badge" style={{ background: '#FEE2E2', color: '#991B1B' }}>
                            Low Stock
                          </span>
                        ) : (
                          <span className="status-badge connected">In Stock</span>
                        )}
                      </td>
                    </tr>
                  );
                })
              ) : (
                <tr>
                  <td colSpan="11" className="text-center py-8 text-slate-500">
                    No items found
                  </td>
                </tr>
              )}
            </tbody>
          </table>
      </div>

      <div className="mt-4 flex items-center justify-between flex-wrap gap-2">
        <div className="text-sm text-slate-500" data-testid="inventory-count">
          Showing <span className="font-medium text-slate-700">{Math.min(visibleItems.length, filteredItems.length)}</span>
          {' '}of <span className="font-medium text-slate-700">{filteredItems.length}</span> filtered
          {filteredItems.length !== items.length && (
            <span className="text-slate-400"> ({items.length} total)</span>
          )}
        </div>
        {visibleItems.length < filteredItems.length && (
          <button
            onClick={() => setRenderLimit(r => r + 200)}
            className="px-4 py-1.5 text-sm font-medium border border-slate-200 rounded-lg hover:bg-slate-50 text-slate-700"
            data-testid="load-more-inventory"
          >
            Load 200 more <span className="text-slate-400">({filteredItems.length - visibleItems.length} remaining)</span>
          </button>
        )}
      </div>

      {/* Purchase Order Modal */}
      {showPOModal && purchaseOrder && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-6 z-50" onClick={() => setShowPOModal(false)}>
          <div className="bg-white rounded-xl max-w-4xl w-full max-h-[90vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
            <div className="sticky top-0 bg-white border-b border-slate-200 p-6">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-2xl font-semibold text-slate-900" style={{ fontFamily: 'Outfit, sans-serif' }}>
                    AI-Generated Purchase Order
                  </h2>
                  <p className="text-sm text-slate-600 mt-1">Powered by GPT-5.2 Analysis</p>
                </div>
                <button onClick={() => setShowPOModal(false)} className="text-slate-400 hover:text-slate-600">
                  <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
            </div>

            <div className="p-6 space-y-6">
              {/* AI Analysis */}
              {purchaseOrder.analysis && (
                <div className="bg-[#E7F5F0] border border-[#2563EB]/20 rounded-lg p-4">
                  <h3 className="text-sm font-semibold text-[#2563EB] mb-2">AI Analysis</h3>
                  <p className="text-sm text-slate-700">{purchaseOrder.analysis}</p>
                </div>
              )}

              {/* Urgent Items */}
              {purchaseOrder.urgent_items && purchaseOrder.urgent_items.length > 0 && (
                <div>
                  <h3 className="text-lg font-semibold text-slate-900 mb-4">Items to Order</h3>
                  <div className="space-y-3">
                    {purchaseOrder.urgent_items.map((item, idx) => (
                      <div key={idx} className="bg-white border border-slate-200 rounded-lg p-4">
                        <div className="flex items-start justify-between">
                          <div className="flex-1">
                            <div className="flex items-center gap-3">
                              <h4 className="font-semibold text-slate-900">{item.item_name}</h4>
                              <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                                item.priority === 'urgent' ? 'bg-red-100 text-red-700' :
                                item.priority === 'high' ? 'bg-orange-100 text-orange-700' :
                                item.priority === 'medium' ? 'bg-yellow-100 text-yellow-700' :
                                'bg-blue-100 text-blue-700'
                              }`}>
                                {(item.priority || 'medium').toUpperCase()}
                              </span>
                            </div>
                            <p className="text-sm text-slate-600 mt-2">{item.reason}</p>
                            <div className="grid grid-cols-3 gap-4 mt-3">
                              <div>
                                <div className="text-xs text-slate-500">Current Stock</div>
                                <div className="text-sm font-semibold">{item.current_stock ?? '-'}</div>
                              </div>
                              <div>
                                <div className="text-xs text-slate-500">Reorder Level</div>
                                <div className="text-sm font-semibold">{item.reorder_level ?? '-'}</div>
                              </div>
                              <div>
                                <div className="text-xs text-slate-500">Recommended Qty</div>
                                <div className="text-sm font-semibold text-[#2563EB]">{item.recommended_quantity ?? '-'}</div>
                              </div>
                            </div>
                          </div>
                          <div className="text-right ml-4">
                            <div className="text-xs text-slate-500">Est. Cost</div>
                            <div className="text-lg font-semibold text-[#2563EB]">
                              ₹{(item.estimated_cost || 0).toLocaleString('en-IN')}
                            </div>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Recommendations */}
              {purchaseOrder.recommendations && purchaseOrder.recommendations.length > 0 && (
                <div>
                  <h3 className="text-lg font-semibold text-slate-900 mb-3">Recommendations</h3>
                  <ul className="space-y-2">
                    {purchaseOrder.recommendations.map((rec, idx) => (
                      <li key={idx} className="flex items-start gap-2 text-sm text-slate-700">
                        <span className="text-[#2563EB] mt-0.5">•</span>
                        {rec}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Total */}
              <div className="bg-slate-50 rounded-lg p-4 flex items-center justify-between">
                <div>
                  <div className="text-sm text-slate-600">Total Estimated Cost</div>
                  <div className="text-xs text-slate-500 mt-1">
                    {purchaseOrder.urgent_items?.length || 0} items
                  </div>
                </div>
                <div className="text-3xl font-bold text-[#2563EB]">
                  ₹{(purchaseOrder.total_estimated_cost || 0).toLocaleString('en-IN')}
                </div>
              </div>

              {/* Actions */}
              <div className="flex gap-3">
                <button className="flex-1 btn-primary py-3">
                  Approve & Send to Supplier
                </button>
                <button onClick={() => setShowPOModal(false)} className="flex-1 btn-secondary py-3">
                  Close
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Inventory;
