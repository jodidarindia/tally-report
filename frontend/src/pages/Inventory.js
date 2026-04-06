import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Download, Search, Filter, Sparkles } from 'lucide-react';
import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const Inventory = () => {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('all');
  const [categories, setCategories] = useState([]);
  const [showPOModal, setShowPOModal] = useState(false);
  const [purchaseOrder, setPurchaseOrder] = useState(null);
  const [generatingPO, setGeneratingPO] = useState(false);

  useEffect(() => {
    fetchInventory();
  }, []);

  const fetchInventory = async () => {
    setLoading(true);
    try {
      const response = await axios.get(`${API}/inventory/items`);
      const itemsData = response.data?.data?.items || [];
      setItems(itemsData);

      const uniqueCategories = [...new Set(itemsData.map(item => item.category).filter(Boolean))];
      setCategories(uniqueCategories);
    } catch (error) {
      console.error('Error fetching inventory:', error);
    } finally {
      setLoading(false);
    }
  };

  const exportData = async (format) => {
    try {
      const response = await axios.post(
        `${API}/reports/export`,
        { report_type: 'inventory', format },
        { responseType: 'blob' }
      );

      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `inventory_report.${format}`);
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch (error) {
      console.error('Error exporting data:', error);
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

  const filteredItems = items.filter(item => {
    const matchesSearch = item.item_name.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesCategory = selectedCategory === 'all' || item.category === selectedCategory;
    return matchesSearch && matchesCategory;
  });

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64" data-testid="inventory-loading">
        <div className="loading-spinner" />
        <span className="ml-3 text-stone-600">Loading inventory...</span>
      </div>
    );
  }

  return (
    <div data-testid="inventory-page">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-4xl font-light tracking-tight text-stone-900" style={{ fontFamily: 'Outfit, sans-serif' }}>
            Inventory
          </h1>
          <p className="mt-2 text-base text-stone-600">Manage your stock items</p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={generatePurchaseOrder}
            disabled={generatingPO}
            className="btn-primary flex items-center gap-2"
            data-testid="generate-po-button"
          >
            <Sparkles size={16} />
            {generatingPO ? 'Generating...' : 'AI Purchase Order'}
          </button>
          <button
            data-testid="export-pdf-button"
            onClick={() => exportData('pdf')}
            className="btn-secondary flex items-center gap-2"
          >
            <Download size={16} />
            PDF
          </button>
          <button
            data-testid="export-excel-button"
            onClick={() => exportData('excel')}
            className="btn-secondary flex items-center gap-2"
          >
            <Download size={16} />
            Excel
          </button>
          <button
            data-testid="export-csv-button"
            onClick={() => exportData('csv')}
            className="btn-primary flex items-center gap-2"
          >
            <Download size={16} />
            CSV
          </button>
        </div>
      </div>

      <div className="bg-white border border-stone-200 rounded-xl p-6 mb-6">
        <div className="flex flex-col md:flex-row gap-4">
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-stone-400" size={18} />
            <input
              type="text"
              data-testid="search-inventory-input"
              placeholder="Search items..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-10 pr-4 py-2 border border-stone-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#064E3B] focus:border-transparent"
            />
          </div>
          <div className="relative">
            <Filter className="absolute left-3 top-1/2 transform -translate-y-1/2 text-stone-400" size={18} />
            <select
              data-testid="category-filter-select"
              value={selectedCategory}
              onChange={(e) => setSelectedCategory(e.target.value)}
              className="pl-10 pr-8 py-2 border border-stone-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#064E3B] focus:border-transparent appearance-none bg-white"
            >
              <option value="all">All Categories</option>
              {categories.map(cat => (
                <option key={cat} value={cat}>{cat}</option>
              ))}
            </select>
          </div>
        </div>
      </div>

      <div className="bg-white border border-stone-200 rounded-xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="data-table" data-testid="inventory-table">
            <thead>
              <tr>
                <th>Item Name</th>
                <th>Category</th>
                <th className="numeric">Quantity</th>
                <th>Unit</th>
                <th className="numeric">Price</th>
                <th className="numeric">Value</th>
                <th className="numeric">Reorder Level</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {filteredItems.length > 0 ? (
                filteredItems.map((item) => {
                  const isLowStock = item.quantity < (item.reorder_level || 0);
                  const itemValue = item.quantity * (item.price || 0);
                  
                  return (
                    <tr key={item.item_id} data-testid={`inventory-row-${item.item_id}`}>
                      <td className="font-medium text-stone-900">{item.item_name}</td>
                      <td>{item.category || '-'}</td>
                      <td className="numeric font-semibold">{item.quantity}</td>
                      <td>{item.unit}</td>
                      <td className="numeric">₹{item.price?.toLocaleString('en-IN') || 0}</td>
                      <td className="numeric font-semibold">₹{itemValue.toLocaleString('en-IN')}</td>
                      <td className="numeric">{item.reorder_level || '-'}</td>
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
                  <td colSpan="8" className="text-center py-8 text-stone-500">
                    No items found
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      <div className="mt-4 text-sm text-stone-500">
        Showing {filteredItems.length} of {items.length} items
      </div>

      {/* Purchase Order Modal */}
      {showPOModal && purchaseOrder && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-6 z-50" onClick={() => setShowPOModal(false)}>
          <div className="bg-white rounded-xl max-w-4xl w-full max-h-[90vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
            <div className="sticky top-0 bg-white border-b border-stone-200 p-6">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-2xl font-semibold text-stone-900" style={{ fontFamily: 'Outfit, sans-serif' }}>
                    AI-Generated Purchase Order
                  </h2>
                  <p className="text-sm text-stone-600 mt-1">Powered by GPT-5.2 Analysis</p>
                </div>
                <button onClick={() => setShowPOModal(false)} className="text-stone-400 hover:text-stone-600">
                  <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
            </div>

            <div className="p-6 space-y-6">
              {/* AI Analysis */}
              {purchaseOrder.analysis && (
                <div className="bg-[#E7F5F0] border border-[#064E3B]/20 rounded-lg p-4">
                  <h3 className="text-sm font-semibold text-[#064E3B] mb-2">AI Analysis</h3>
                  <p className="text-sm text-stone-700">{purchaseOrder.analysis}</p>
                </div>
              )}

              {/* Urgent Items */}
              {purchaseOrder.urgent_items && purchaseOrder.urgent_items.length > 0 && (
                <div>
                  <h3 className="text-lg font-semibold text-stone-900 mb-4">Items to Order</h3>
                  <div className="space-y-3">
                    {purchaseOrder.urgent_items.map((item, idx) => (
                      <div key={idx} className="bg-white border border-stone-200 rounded-lg p-4">
                        <div className="flex items-start justify-between">
                          <div className="flex-1">
                            <div className="flex items-center gap-3">
                              <h4 className="font-semibold text-stone-900">{item.item_name}</h4>
                              <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                                item.priority === 'urgent' ? 'bg-red-100 text-red-700' :
                                item.priority === 'high' ? 'bg-orange-100 text-orange-700' :
                                item.priority === 'medium' ? 'bg-yellow-100 text-yellow-700' :
                                'bg-blue-100 text-blue-700'
                              }`}>
                                {item.priority.toUpperCase()}
                              </span>
                            </div>
                            <p className="text-sm text-stone-600 mt-2">{item.reason}</p>
                            <div className="grid grid-cols-3 gap-4 mt-3">
                              <div>
                                <div className="text-xs text-stone-500">Current Stock</div>
                                <div className="text-sm font-semibold">{item.current_stock}</div>
                              </div>
                              <div>
                                <div className="text-xs text-stone-500">Reorder Level</div>
                                <div className="text-sm font-semibold">{item.reorder_level}</div>
                              </div>
                              <div>
                                <div className="text-xs text-stone-500">Recommended Qty</div>
                                <div className="text-sm font-semibold text-[#064E3B]">{item.recommended_quantity}</div>
                              </div>
                            </div>
                          </div>
                          <div className="text-right ml-4">
                            <div className="text-xs text-stone-500">Est. Cost</div>
                            <div className="text-lg font-semibold text-[#064E3B]">
                              ₹{item.estimated_cost.toLocaleString('en-IN')}
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
                  <h3 className="text-lg font-semibold text-stone-900 mb-3">Recommendations</h3>
                  <ul className="space-y-2">
                    {purchaseOrder.recommendations.map((rec, idx) => (
                      <li key={idx} className="flex items-start gap-2 text-sm text-stone-700">
                        <span className="text-[#064E3B] mt-0.5">•</span>
                        {rec}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Total */}
              <div className="bg-stone-50 rounded-lg p-4 flex items-center justify-between">
                <div>
                  <div className="text-sm text-stone-600">Total Estimated Cost</div>
                  <div className="text-xs text-stone-500 mt-1">
                    {purchaseOrder.urgent_items?.length || 0} items
                  </div>
                </div>
                <div className="text-3xl font-bold text-[#064E3B]">
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
