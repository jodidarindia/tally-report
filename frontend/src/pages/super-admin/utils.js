// Shared utilities and constants for the SuperAdmin Command Center.
// Extracted from the monolithic SuperAdminDashboard.js (Feb 2026 refactor).

export const ALL_FEATURES = [
  { id: 'dashboard', label: 'Dashboard', desc: 'Overview stats & charts' },
  { id: 'sales', label: 'Sales', desc: 'Sales vouchers & analytics' },
  { id: 'crm', label: 'CRM', desc: 'Customer outstanding & behavior' },
  { id: 'inventory', label: 'Inventory', desc: 'Stock management & items' },
  { id: 'analytics', label: 'Analytics', desc: 'Movement analysis & reports' },
  { id: 'salesman', label: 'Salesman', desc: 'Salesman performance & orders' },
  { id: 'ai_reports', label: 'AI Reports', desc: 'AI-powered insights' },
  { id: 'insider', label: 'Insider Result', desc: 'BI analytics & forecasts' },
  { id: 'ca_corner', label: 'CA Corner', desc: 'P&L, Balance Sheet, Cash Flow' },
  { id: 'dispatch', label: 'Dispatch', desc: 'Dispatch terminal & tracking' },
  { id: 'sync_history', label: 'Sync History', desc: 'Data sync logs' },
  { id: 'setup', label: 'Setup', desc: 'Tally* connection settings' },
];

export const PLANS = {
  starter: { name: 'Starter', monthly: 999, annual: 9990, maxCompanies: 1, maxEmployees: 2, features: ['dashboard', 'sales', 'inventory', 'sync_history', 'setup'] },
  professional: { name: 'Professional', monthly: 2499, annual: 24990, maxCompanies: 1, maxEmployees: 5, features: ['dashboard', 'sales', 'crm', 'inventory', 'analytics', 'salesman', 'sync_history', 'setup'] },
  enterprise: { name: 'Enterprise', monthly: 3799, annual: 37990, maxCompanies: 1, maxEmployees: 10, features: ALL_FEATURES.map(f => f.id) },
  trial: { name: 'Free Trial (14 days)', monthly: 0, annual: 0, maxCompanies: 1, maxEmployees: 10, trialDays: 14, features: ALL_FEATURES.map(f => f.id) },
};

export const STAFF_FEATURES_LIST = [
  { id: 'overview', label: 'Overview' },
  { id: 'subscriptions', label: 'Subscriptions' },
  { id: 'payments', label: 'Payments' },
  { id: 'invoices', label: 'Invoices' },
  { id: 'prospects', label: 'Prospects' },
  { id: 'health', label: 'Customer Health' },
  { id: 'admins', label: 'Admin Mgmt (view only)' },
  { id: 'renewals', label: 'Renewals' },
  { id: 'referrals', label: 'Referrals' },
  { id: 'questionnaires', label: 'Leads' },
  { id: 'backups', label: 'Backups' },
  { id: 'activity', label: 'Activity Log' },
];

export const formatINR = (n) =>
  `Rs.${(n || 0).toLocaleString('en-IN', { maximumFractionDigits: 0 })}`;

export const formatDate = (d) => {
  if (!d) return '—';
  const dt = (d.includes && (d.includes('+') || d.includes('Z'))) ? new Date(d) : new Date(d + 'Z');
  return dt.toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'Asia/Kolkata' });
};

// Cryptographically-strong 12-char password. Avoids visually-ambiguous chars
// (0/O, 1/l/I) so the user can read it from a welcome email.
export const generateStrongPassword = () => {
  const lower = 'abcdefghijkmnopqrstuvwxyz';
  const upper = 'ABCDEFGHJKLMNPQRSTUVWXYZ';
  const digit = '23456789';
  const sym = '@#$%&*?!';
  const all = lower + upper + digit + sym;
  const buf = new Uint32Array(12);
  (window.crypto || window.msCrypto).getRandomValues(buf);
  const pick = (set, n) => set.charAt(n % set.length);
  const arr = [
    pick(lower, buf[0]), pick(upper, buf[1]),
    pick(digit, buf[2]), pick(sym, buf[3]),
  ];
  for (let i = 4; i < 12; i++) arr.push(pick(all, buf[i]));
  const shuffleBuf = new Uint32Array(arr.length);
  (window.crypto || window.msCrypto).getRandomValues(shuffleBuf);
  for (let i = arr.length - 1; i > 0; i--) {
    const j = shuffleBuf[i] % (i + 1);
    [arr[i], arr[j]] = [arr[j], arr[i]];
  }
  return arr.join('');
};
