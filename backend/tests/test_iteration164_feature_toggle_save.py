"""iter-164: SuperAdmin → Edit Admin — feature-toggle save regression.

**The bug**: ``saveEditAdmin`` in ``SuperAdminDashboard.js`` sent
``plan.features`` (the full default feature set for the selected plan)
instead of ``editAdmin.features`` (the SuperAdmin's edited selection).
So every un-tick in the modal was silently overwritten — the tenant
kept every feature.

Reported by user: "in superadmin, admin mgmt- for tenant
amitbajaj.india@gmail.com, i have unchecked some features like sales,
crm, inventory and saved. even after this all features are still active
for tenant."

**The fix**: send ``editAdmin.features`` instead. Verify by grepping the
source file — a UI regression would flip the wrong array back in.
"""
import pathlib
import re


def _load_source():
    return pathlib.Path("/app/frontend/src/pages/SuperAdminDashboard.js").read_text()


def test_edit_admin_sends_edited_features_not_plan_default():
    """The PUT /super-admin/admins/{username}/edit body must reference
    ``editAdmin.features`` — never ``plan.features`` — so the
    SuperAdmin's un-ticks reach the backend."""
    src = _load_source()
    # Find the PUT to /edit and inspect the payload literal.
    m = re.search(
        r"axios\.put\(\s*`\$\{API\}/super-admin/admins/\$\{editAdmin\.username\}/edit`,\s*\{([^}]*)\}",
        src, re.DOTALL,
    )
    assert m, "PUT /super-admin/admins/{username}/edit call not found"
    payload = m.group(1)
    # The features field must reference editAdmin.features (not plan.features).
    assert re.search(r"features:\s*editAdmin\.features", payload), (
        "features must be sourced from editAdmin.features, not plan.features"
    )
    assert "features: plan.features" not in payload, (
        "regression: features again sourced from plan default — un-ticks will be lost"
    )


def test_convert_prospect_respects_user_features():
    """Prospect conversion has the same shape — send user-edited features
    when the modal exposes them, else fall back to plan default."""
    src = _load_source()
    m = re.search(
        r"const convertProspect = async \(\) => \{(.+?)\n  \};",
        src, re.DOTALL,
    )
    assert m, "convertProspect function not found"
    body = m.group(1)
    # Must not blindly send plan.features anymore.
    assert "features: plan.features" not in body, (
        "regression: convertProspect again ignores user-edited features"
    )
    assert "convertData.features" in body, (
        "convertProspect should fall back to convertData.features when provided"
    )
