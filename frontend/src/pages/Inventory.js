import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Download, Search, Filter } from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const Inventory = () => {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('all');
  const [categories, setCategories] = useState([]);

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
    </div>
  );
};

export default Inventory;
