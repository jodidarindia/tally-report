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
AGENT = "/app/desktop-agent/build-kit-2/tally_sync_agent_v9.py"
GUI = "/app/desktop-agent/build-kit-2/flowra_gui.py"
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
    # Missing GUID from binder-aware backend must be rejected.
    assert "v9.11.0" in src


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
    assert "9.11.0-multi-company-guid-binding" in src


def test_binding_called_in_quick_and_full_sync_loops():
    src = pathlib.Path(AGENT).read_text()
    # Both loops should call _ensure_tally_binding — count >= 2.
    hits = len(re.findall(r"_ensure_tally_binding\(", src))
    assert hits >= 2, f"expected 2+ call-sites of _ensure_tally_binding, saw {hits}"


def test_gui_version_bumped():
    src = pathlib.Path(GUI).read_text()
    assert 'APP_VERSION = "v9.11.0"' in src


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
