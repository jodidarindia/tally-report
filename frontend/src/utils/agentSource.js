// v1.5.7 — Detects whether the current tenant is syncing from Tally or
// Busy so UI labels ("Set in Tally" / "Tally ✓" / "Sync from Tally*")
// swap to the correct ERP name dynamically.
//
// Source of truth: the `agent_version` string returned by
// `/api/agent/sync-status` (e.g. "busy-1.5.7-invoice-fields" or
// "tally-9.8.7-…"). Dashboard.js caches it in localStorage on load;
// any page can then call `getErpLabel()` cheaply without another
// network hop.

const KEY = "flowra_agent_source";

export function setAgentSourceFromVersion(agentVersion) {
  if (!agentVersion) return;
  const av = String(agentVersion).toLowerCase();
  if (av.startsWith("busy")) {
    localStorage.setItem(KEY, "busy");
  } else if (av.startsWith("tally")) {
    localStorage.setItem(KEY, "tally");
  }
}

export function getAgentSource() {
  const v = (localStorage.getItem(KEY) || "").toLowerCase();
  if (v === "busy" || v === "tally") return v;
  return "tally"; // default — most tenants are Tally
}

// UI-facing helpers.
export function getErpLabel() {
  return getAgentSource() === "busy" ? "Busy" : "Tally";
}

// Trailing "*" retained to match the existing branding footnote in the
// app ("Tally is a trademark of Tally Solutions Pvt Ltd").
export function getErpLabelMarked() {
  return getAgentSource() === "busy" ? "Busy*" : "Tally*";
}

// Used by the CRM Outstanding tab's "verified" chip.
export function getErpBadgeLabel() {
  return getErpLabel();
}
