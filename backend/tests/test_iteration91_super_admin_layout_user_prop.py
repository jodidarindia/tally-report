"""Iteration 91 — Regression: SuperAdminLayout MUST pass `user` prop to SuperAdminDashboard.

Without the prop, `isSuperAdmin` evaluates to `false` inside the dashboard,
collapsing the entire tab strip and hiding the Staff tab + every other tab.
"""
import re


def test_super_admin_layout_passes_user_prop():
    src = open("/app/frontend/src/components/SuperAdminLayout.js").read()
    # Find the render of <SuperAdminDashboard ... /> and check it includes user=
    m = re.search(r"<SuperAdminDashboard\s+([^/>]+?)/?>", src)
    assert m, "Could not find <SuperAdminDashboard /> tag in SuperAdminLayout.js"
    props = m.group(1)
    assert "user=" in props, (
        "SuperAdminLayout.js must pass `user={user}` to <SuperAdminDashboard /> "
        "— otherwise isSuperAdmin is undefined and the tab strip disappears. "
        f"Got: <SuperAdminDashboard {props}/>"
    )
    assert "token=" in props, "SuperAdminLayout must also pass `token`"
