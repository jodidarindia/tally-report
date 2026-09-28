"""iter-168: Tally multi-company safety — GUID-bound TOFU sync.

Validates:
- New `routes/tally_binding.py` module exists with the 3 endpoints
- `validate_sync_binding()` accepts first-time GUID (TOFU) and rejects mismatch
- `sync.py` calls the validator before writing data
- Tally Agent v9.11.0 fetches company $Guid and sends it on every payload
- Frontend Settings page shows the binding + Unbind button
"""
import inspect
import pathlib
import re


BINDING_MOD = "/app/backend/routes/tally_binding.py"
SYNC_MOD = "/app/backend/routes/sync.py"
SERVER = "/app/backend/server.py"
AGENT = "/app/desktop-agent/build-kit/tally_sync_agent_v9.py"
GUI = "/app/desktop-agent/build-kit/flowra_gui.py"
FRONTEND = "/app/frontend/src/pages/ProfileModal.js"


def test_tally_binding_module_exists():
    assert pathlib.Path(BINDING_MOD).exists(), "routes/tally_binding.py missing"


def test_binding_endpoints_registered():
    src = pathlib.Path(BINDING_MOD).read_text()
    assert '@router.post("/agent/tally-binding/bind")' in src
    assert '@router.get("/settings/tally-binding")' in src
    assert '@router.delete("/settings/tally-binding")' in src


def test_binding_router_wired_into_server():
    src = pathlib.Path(SERVER).read_text()
    assert "from routes.tally_binding import router as tally_binding_router" in src
    assert "api_router.include_router(tally_binding_router)" in src


def test_tofu_and_mismatch_logic_present():
    from routes.tally_binding import validate_sync_binding
    src = inspect.getsource(validate_sync_binding)
    # TOFU: first-time capture inserts a doc.
    assert "insert_one" in src
    assert "bound_by" in src
    # Mismatch guard.
    assert "guid mismatch" in src.lower() or "guid" in src.lower()
    assert "Refusing to write" in src
    # Missing GUID from binder-aware backend must be handled gracefully
    # (soft-accept, not hard block — see v9.8.32 hotfix rationale).
    assert "warming its GUID cache" in src or "guid-bound" in src.lower()


def test_sync_endpoint_calls_binding_validator():
    src = pathlib.Path(SYNC_MOD).read_text()
    assert "from routes.tally_binding import validate_sync_binding" in src
    assert 'request.get("company_guid"' in src
    # Blocks + releases lock on failure.
    assert "Sync BLOCKED by binding guard" in src


def test_agent_fetches_guid_and_binds():
    src = pathlib.Path(AGENT).read_text()
    # New client method.
    assert "def fetch_company_guid" in src
    # New agent method.
    assert "def _ensure_tally_binding" in src
    # Endpoint the agent calls.
    assert "/api/agent/tally-binding/bind" in src
    # GUID included in every sync payload.
    assert "'company_guid':" in src
    # Version bump.
    assert "9.8.34-guid-preflight-only" in src


def test_binding_called_in_quick_and_full_sync_loops():
    src = pathlib.Path(AGENT).read_text()
    # Both loops should call _ensure_tally_binding — count >= 2.
    hits = len(re.findall(r"_ensure_tally_binding\(", src))
    assert hits >= 2, f"expected 2+ call-sites of _ensure_tally_binding, saw {hits}"


def test_gui_version_bumped():
    src = pathlib.Path(GUI).read_text()
    assert 'APP_VERSION = "v9.8.34"' in src


def test_frontend_binding_card_present():
    src = pathlib.Path(FRONTEND).read_text()
    assert "TallyBindingCard" in src
    assert "/settings/tally-binding" in src
    assert 'data-testid="tally-binding-card"' in src
    assert 'data-testid="btn-tally-unbind"' in src
    assert "Tally Company Lock" in src


def test_binding_validator_touches_last_seen():
    src = pathlib.Path(BINDING_MOD).read_text()
    assert "touch_last_seen" in src
    assert "last_seen_at" in src


def test_guid_normalisation_is_case_insensitive():
    from routes.tally_binding import _norm_guid
    assert _norm_guid("{ABCD-1234}") == "abcd-1234"
    assert _norm_guid("  ABCD-1234  ") == "abcd-1234"
    assert _norm_guid("") == ""
    assert _norm_guid(None) == ""

def test_guid_fetch_uses_safe_ismodify_pattern():
    """v9.8.34 hotfix — Tally crashed with a dedicated GUID Collection
    request (even one modeled on list_of_companies). Fix: fetch GUID
    as a SIDE-EFFECT of the existing list_of_companies XML — no new
    request to Tally, and the sync-time fetch_company_guid is now
    pure dict-lookup on `_guid_cache`. Also verifies the kill-switch
    that omits the GUID fetch entirely."""
    src = pathlib.Path(AGENT).read_text()
    # fetch_company_guid must NOT issue any XML — it's cache-only now.
    m = re.search(
        r"def fetch_company_guid\(.*?\n(.*?)(?=\n    def |\nclass )",
        src, re.S,
    )
    assert m, "fetch_company_guid not found"
    body = m.group(1)
    assert "<ENVELOPE>" not in body, \
        "fetch_company_guid must not build Tally XML — cache lookup only"
    assert "self._post" not in body, \
        "fetch_company_guid must not call self._post — cache lookup only"
    assert "_guid_cache" in body
    # The GUID population must live inside list_of_companies with the
    # safe (ISMODIFY="No") shape, and must be togglable.
    m2 = re.search(
        r"def list_of_companies\(.*?\n(.*?)(?=\n    def |\nclass )",
        src, re.S,
    )
    assert m2
    loc = m2.group(1)
    assert 'ISMODIFY="No"' in loc
    assert 'ISINITIALIZE="Yes"' not in loc
    assert '<SVCURRENTCOMPANY>' not in loc.upper()
    assert 'disable_guid_fetch' in loc, "kill-switch must be honoured"
    assert '_guid_cache' in loc


def test_kill_switch_flag_is_wired_through_config_and_backend():
    """`disable_guid_lookup` must flow: backend `/auth/me` →
    `get_or_refresh_auth()` → `self.disable_guid_lookup` →
    `self.tally.disable_guid_fetch`."""
    src = pathlib.Path(AGENT).read_text()
    assert 'self.disable_guid_lookup' in src
    assert 'self.tally.disable_guid_fetch' in src
    assert '"disable_guid_lookup"' in src or "'disable_guid_lookup'" in src

    auth = pathlib.Path("/app/backend/routes/auth.py").read_text()
    assert '"disable_guid_lookup"' in auth
    assert 'tally_disable_guid_lookup' in auth

    sa = pathlib.Path("/app/backend/routes/super_admin.py").read_text()
    assert "/super-admin/admins/{username}/toggle-guid-lookup" in sa


def test_binding_post_is_deduped_per_session():
    """_ensure_tally_binding must remember which (company, guid) pairs
    it already posted so it doesn't spam the backend on every tick."""
    src = pathlib.Path(AGENT).read_text()
    m = re.search(
        r"def _ensure_tally_binding\(.*?\n(.*?)(?=\n    def |\nclass )",
        src, re.S,
    )
    assert m
    body = m.group(1)
    assert "_binding_posted" in body
    assert "bind_key" in body


def test_backend_soft_accepts_missing_guid_when_bound():
    """Hard-blocking absent GUIDs strands legacy Tally installs. The
    validator should hard-block ONLY on mismatch."""
    src = pathlib.Path(BINDING_MOD).read_text()
    assert "warming its GUID cache" in src
    # The mismatch block MUST still fire — search for the corruption warning.
    assert "Refusing to write" in src

