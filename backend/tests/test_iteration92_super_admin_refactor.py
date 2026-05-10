"""Iteration 92 — SuperAdminDashboard refactor structure test.

Asserts:
  - SuperAdminDashboard.js stays under a sane line cap (target: ≤1500 LOC).
  - Each per-tab component file exists and exports the expected name.
  - Shared utils file exports the expected helpers.
  - The parent imports each tab component.
"""
import os
import re

ROOT = "/app/frontend/src/pages"
PARENT = f"{ROOT}/SuperAdminDashboard.js"
TABS_DIR = f"{ROOT}/super-admin/tabs"
UTILS = f"{ROOT}/super-admin/utils.js"

EXPECTED_TABS = [
    "OverviewTab", "SubscriptionsTab", "PaymentsTab", "InvoicesTab",
    "ProspectsTab", "HealthTab", "AdminsTab", "RenewalsTab", "StaffTab",
]

EXPECTED_UTIL_EXPORTS = [
    "ALL_FEATURES", "PLANS", "STAFF_FEATURES_LIST",
    "formatINR", "formatDate", "generateStrongPassword",
]


def test_parent_file_size_capped():
    n = sum(1 for _ in open(PARENT))
    assert n <= 1500, (
        f"SuperAdminDashboard.js has grown to {n} lines — refactor more tabs out. "
        f"Target ≤1500 LOC."
    )


def test_each_tab_component_exists_and_exports():
    for name in EXPECTED_TABS:
        path = f"{TABS_DIR}/{name}.jsx"
        assert os.path.exists(path), f"Missing tab file: {path}"
        src = open(path).read()
        assert f"export const {name}" in src, f"{path} must export `{name}`"


def test_utils_exports_present():
    assert os.path.exists(UTILS), f"Missing utils file: {UTILS}"
    src = open(UTILS).read()
    for sym in EXPECTED_UTIL_EXPORTS:
        assert re.search(rf"export\s+(const|function)\s+{sym}\b", src), (
            f"utils.js must export `{sym}`"
        )


def test_parent_imports_each_tab():
    src = open(PARENT).read()
    for name in EXPECTED_TABS:
        assert (
            f"import {{ {name} }} from './super-admin/tabs/{name}'" in src
            or re.search(rf"import\s+\{{\s*{name}\s*\}}\s+from\s+'./super-admin/tabs/{name}'", src)
        ), f"SuperAdminDashboard.js must import `{name}` from ./super-admin/tabs/{name}"
