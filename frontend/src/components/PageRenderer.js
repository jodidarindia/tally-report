import React from 'react';
import { Lock } from 'lucide-react';
import Dashboard from '../pages/Dashboard';
import Inventory from '../pages/Inventory';
import Sales from '../pages/Sales';
import CustomerCRM from '../pages/CustomerCRM';
import InventoryAnalytics from '../pages/InventoryAnalytics';
import EnhancedAIReports from '../pages/EnhancedAIReports';
import SalesmanPerformance from '../pages/SalesmanPerformance';
import SyncHistory from '../pages/SyncHistory';
import TallySetup from '../pages/TallySetup';
import ActivityLog from '../pages/ActivityLog';
import ReferAndEarn from '../pages/ReferAndEarn';
import Tutorials from '../pages/Tutorials';
import CACorner from '../pages/CACorner';
import InsiderResult from '../pages/InsiderResult';
import DispatchAdmin from '../pages/DispatchAdmin';
import SalesmanOrderApp from '../pages/SalesmanOrderApp';
import UserAdminDataExport from '../pages/UserAdminDataExport';

const FeatureLocked = ({ featureId }) => (
  <div className="flex items-center justify-center h-[60vh]" data-testid="feature-locked">
    <div className="text-center p-8 bg-white rounded-2xl border border-slate-200 max-w-md">
      <div className="w-16 h-16 bg-slate-100 rounded-full flex items-center justify-center mx-auto mb-4">
        <Lock size={28} className="text-slate-400" />
      </div>
      <h3 className="text-lg font-semibold text-slate-900 mb-2">Feature Not Activated</h3>
      <p className="text-slate-500 text-sm">
        Subscribe for this feature. Contact your FLOWRA administrator to activate{' '}
        <strong className="capitalize">{featureId.replace('_', ' ')}</strong>.
      </p>
    </div>
  </div>
);

const PageRenderer = ({ currentPage, user, selectedFY, selectedCompany, excludeBranches, token }) => {
  // Don't render anything once the user is being logged out — prevents the
  // "Feature Not Activated" flash for non-admin roles whose default page
  // (e.g. 'dashboard') isn't in their feature list.
  if (!user || !token) return null;
  const features = user?.features || [];
  const isActive = (f) => features.includes(f);
  const gated = (featureId, component) => isActive(featureId) ? component : <FeatureLocked featureId={featureId} />;

  switch (currentPage) {
    case 'dashboard': return gated('dashboard', <Dashboard selectedFY={selectedFY} companyId={selectedCompany} excludeBranches={excludeBranches} />);
    case 'inventory': return gated('inventory', <Inventory selectedFY={selectedFY} companyId={selectedCompany} excludeBranches={excludeBranches} />);
    case 'sales': return gated('sales', <Sales selectedFY={selectedFY} companyId={selectedCompany} excludeBranches={excludeBranches} />);
    case 'crm': return gated('crm', <CustomerCRM selectedFY={selectedFY} companyId={selectedCompany} excludeBranches={excludeBranches} />);
    case 'analytics': return gated('analytics', <InventoryAnalytics selectedFY={selectedFY} companyId={selectedCompany} excludeBranches={excludeBranches} />);
    case 'ai-reports': return gated('ai_reports', <EnhancedAIReports selectedFY={selectedFY} companyId={selectedCompany} excludeBranches={excludeBranches} />);
    case 'sync-history': return gated('sync_history', <SyncHistory companyId={selectedCompany} />);
    case 'setup': return gated('setup', <TallySetup companyId={selectedCompany} />);
    case 'activity': return <ActivityLog token={token} role={user?.role} />;
    case 'referral': return <ReferAndEarn />;
    case 'tutorials': return <Tutorials />;
    case 'ca-corner': return gated('ca_corner', <CACorner selectedFY={selectedFY} excludeBranches={excludeBranches} userRole={user?.role} />);
    case 'insider': return gated('insider', <InsiderResult selectedFY={selectedFY} companyId={selectedCompany} excludeBranches={excludeBranches} />);
    case 'dispatch': {
      const role = user?.role;
      // Dispatch employees get the SAME UX as useradmin (all tabs + features) —
      // ONLY the Employees tab is hidden and create-card / start-date controls
      // are gated. This is enforced via the `isEmployee` prop on DispatchAdmin.
      if (role === 'dispatch') return <DispatchAdmin selectedFY={selectedFY} companyId={selectedCompany} isEmployee={true} />;
      return gated('dispatch', <DispatchAdmin selectedFY={selectedFY} companyId={selectedCompany} />);
    }
    case 'salesman': {
      // SECURITY GUARD — Salesmen MUST NEVER see the useradmin
      // SalesmanPerformance page (which exposes other salesmen's targets,
      // achievement % and customer counts). Route them to their own
      // ordering app regardless of how they got here.
      // NOTE: previously this file had a duplicate `case 'salesman':` above
      // that always matched first and bypassed this guard — that bug
      // re-leaked the admin view to salesmen. Do NOT add another match.
      if (user?.role === 'salesman') {
        return <SalesmanOrderApp user={user} selectedFY={selectedFY} companyId={selectedCompany} />;
      }
      return gated('salesman', <SalesmanPerformance selectedFY={selectedFY} companyId={selectedCompany} excludeBranches={excludeBranches} />);
    }
    case 'salesman-orders': {
      return <SalesmanOrderApp user={user} selectedFY={selectedFY} companyId={selectedCompany} />;
    }
    case 'data-export': {
      // Tenant admin only — DPDP right-to-portability download
      if (user?.role !== 'admin' && user?.role !== 'super_admin') {
        return <FeatureLocked featureId="data_export" />;
      }
      return <UserAdminDataExport />;
    }
    default: return gated('dashboard', <Dashboard selectedFY={selectedFY} companyId={selectedCompany} excludeBranches={excludeBranches} />);
  }
};

export default PageRenderer;
