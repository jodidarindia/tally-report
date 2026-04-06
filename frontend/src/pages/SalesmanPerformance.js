import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Users, TrendingUp, Award, Target } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const SalesmanPerformance = () => {
  const [performance, setPerformance] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchPerformance();
  }, []);

  const fetchPerformance = async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${API}/salesman/performance`);
      setPerformance(res.data?.data?.salesman || []);
    } catch (error) {
      console.error('Error fetching performance:', error);
    } finally {
      setLoading(false);
    }
  };

  const chartData = performance.map(p => ({
    name: p.salesman_name,
    target: p.target_amount,
    achieved: p.achieved_amount,
    percentage: p.achievement_percentage
  }));

  const topPerformer = performance.length > 0 ? performance[0] : null;

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="loading-spinner" />
      </div>
    );
  }

  return (
    <div data-testid="salesman-page">
      <div className="mb-8">
        <h1 className="text-4xl font-light tracking-tight text-stone-900" style={{ fontFamily: 'Outfit, sans-serif' }}>
          Salesman Performance
        </h1>
        <p className="mt-2 text-base text-stone-600">Track sales team achievements and targets</p>
      </div>

      {/* Top Performer Card */}
      {topPerformer && (
        <div className="bg-gradient-to-r from-[#064E3B] to-[#047857] text-white rounded-xl p-8 mb-6">
          <div className="flex items-center gap-3 mb-4">
            <Award size={32} />
            <h2 className="text-2xl font-semibold">Top Performer</h2>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
            <div>
              <div className="text-sm opacity-90">Salesman</div>
              <div className="text-2xl font-bold mt-1">{topPerformer.salesman_name}</div>
            </div>
            <div>
              <div className="text-sm opacity-90">Achievement</div>
              <div className="text-2xl font-bold mt-1">{topPerformer.achievement_percentage.toFixed(1)}%</div>
            </div>
            <div>
              <div className="text-sm opacity-90">Total Sales</div>
              <div className="text-2xl font-bold mt-1">₹{topPerformer.achieved_amount.toLocaleString('en-IN')}</div>
            </div>
            <div>
              <div className="text-sm opacity-90">Customers</div>
              <div className="text-2xl font-bold mt-1">{topPerformer.total_customers}</div>
            </div>
          </div>
        </div>
      )}

      {/* Performance Chart */}
      <div className="bg-white border border-stone-200 rounded-xl p-6 mb-6">
        <h3 className="text-xl font-medium text-stone-900 mb-4">Target vs Achievement</h3>
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#E7E5E4" />
            <XAxis dataKey="name" stroke="#78716C" style={{ fontSize: '12px' }} />
            <YAxis stroke="#78716C" style={{ fontSize: '12px' }} />
            <Tooltip
              contentStyle={{
                background: 'white',
                border: '1px solid #E7E5E4',
                borderRadius: '8px'
              }}
            />
            <Bar dataKey="target" fill="#D1D5DB" name="Target" radius={[4, 4, 0, 0]} />
            <Bar dataKey="achieved" fill="#064E3B" name="Achieved" radius={[4, 4, 0, 0]}>
              {chartData.map((entry, index) => (
                <Cell key={`cell-${index}`} fill={entry.percentage >= 100 ? '#10B981' : '#064E3B'} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Performance Table */}
      <div className="bg-white border border-stone-200 rounded-xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="data-table" data-testid="performance-table">
            <thead>
              <tr>
                <th>Rank</th>
                <th>Salesman</th>
                <th className="numeric">Target</th>
                <th className="numeric">Achieved</th>
                <th className="numeric">Achievement %</th>
                <th className="numeric">Customers</th>
                <th className="numeric">Transactions</th>
                <th className="numeric">Avg Transaction</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {performance.map((person, idx) => (
                <tr key={idx}>
                  <td className="font-bold">
                    {idx === 0 ? '🥇' : idx === 1 ? '🥈' : idx === 2 ? '🥉' : idx + 1}
                  </td>
                  <td className="font-medium text-stone-900">{person.salesman_name}</td>
                  <td className="numeric">₹{person.target_amount.toLocaleString('en-IN')}</td>
                  <td className="numeric font-semibold text-[#064E3B]">
                    ₹{person.achieved_amount.toLocaleString('en-IN')}
                  </td>
                  <td className="numeric">
                    <div className="flex items-center gap-2">
                      <div className="flex-1 h-2 bg-stone-200 rounded-full overflow-hidden max-w-[100px]">
                        <div
                          className={`h-full ${
                            person.achievement_percentage >= 100 ? 'bg-green-500' : 'bg-[#064E3B]'
                          }`}
                          style={{ width: `${Math.min(person.achievement_percentage, 100)}%` }}
                        />
                      </div>
                      <span className="text-sm font-medium">
                        {person.achievement_percentage.toFixed(1)}%
                      </span>
                    </div>
                  </td>
                  <td className="numeric">{person.total_customers}</td>
                  <td className="numeric">{person.total_transactions}</td>
                  <td className="numeric">₹{person.average_transaction.toLocaleString('en-IN')}</td>
                  <td>
                    {person.achievement_percentage >= 100 ? (
                      <span className="status-badge" style={{ background: '#D1FAE5', color: '#065F46' }}>
                        ✓ Achieved
                      </span>
                    ) : person.achievement_percentage >= 75 ? (
                      <span className="status-badge" style={{ background: '#FEF3E2', color: '#B45309' }}>
                        On Track
                      </span>
                    ) : (
                      <span className="status-badge" style={{ background: '#FEE2E2', color: '#991B1B' }}>
                        Behind
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default SalesmanPerformance;
