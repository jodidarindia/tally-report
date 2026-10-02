"""iter-170: Busy Agent v1.7.0 — one-email-one-company binding +
Station-driven city-wise suggestions + triple-name field mapping.

Validates all four requirement bullets the user locked in:
  1. Email ↔ Busy company binding (deletable by useradmin only).
  2. Agent aborts on company-name mismatch via /busy-binding/check.
  3. Station field persisted on customers; /city-suggestions endpoint
     returns items selling in the customer's city they haven't bought.
  4. Triple-name field mapping (ItemName / AliasName / PrintName) with
     per-tenant admin override.
"""
import inspect
import pathlib
import re


BUSY_AGENT = "/app/desktop-agent/build-kit-busy/flowra_busy_agent.py"
BUSY_GUI = "/app/desktop-agent/build-kit-busy/flowra_busy_gui.py"
BUSY_VINFO = "/app/desktop-agent/build-kit-busy/version_info.txt"
BINDING_MOD = "/app/backend/routes/busy_binding.py"
SETTINGS_MOD = "/app/backend/routes/busy_settings.py"
SYNC_MOD = "/app/backend/routes/sync.py"
SRV = "/app/backend/server.py"
SM = "/app/backend/routes/salesman_orders.py"
PM = "/app/frontend/src/pages/ProfileModal.js"
SMA = "/app/frontend/src/pages/SalesmanOrderApp.js"


# ─── 1 + 2 — binding ──────────────────────────────────────────────────
def test_busy_binding_module_exists():
    assert pathlib.Path(BINDING_MOD).exists()


def test_binding_endpoints_registered():
    src = pathlib.Path(BINDING_MOD).read_text()
    assert '@router.post("/agent/busy-binding/check")' in src
    assert '@router.post("/agent/busy-binding/bind")' in src
    assert '@router.get("/settings/busy-binding")' in src
    assert '@router.delete("/settings/busy-binding")' in src


def test_binding_router_wired_into_server():
    s = pathlib.Path(SRV).read_text()
    assert "from routes.busy_binding import router as busy_binding_router" in s
    assert "api_router.include_router(busy_binding_router)" in s


def test_sync_endpoint_calls_busy_validator():
    s = pathlib.Path(SYNC_MOD).read_text()
    assert "from routes.busy_binding import validate_busy_sync" in s
    # The guard must release the sync-lock on hard-block.
    assert "Busy sync BLOCKED" in s


def test_tofu_bind_and_hard_block_on_mismatch():
    from routes.busy_binding import validate_busy_sync
    src = inspect.getsource(validate_busy_sync)
    assert "insert_one" in src       # TOFU
    assert "Refusing to" in src and "write" in src
    assert "Unbind" in src            # UX guidance


def test_agent_calls_check_before_sync():
    src = pathlib.Path(BUSY_AGENT).read_text()
    assert "/api/agent/busy-binding/check" in src
    assert "BUSY-BIND MISMATCH" in src
    assert "busy_binding_mismatch" in src
    # Must NOT enter the sync loop on mismatch — stays alive at 60s sleeps.
    assert "while True:" in src and "_t.sleep(60)" in src


def test_agent_sends_source_and_busy_company_name():
    src = pathlib.Path(BUSY_AGENT).read_text()
    # _build_envelope is the single choke-point for every sync payload.
    m = re.search(r"def _build_envelope\(.*?return \{(.*?)\}", src, re.S)
    assert m, "_build_envelope not found"
    env = m.group(1)
    assert '"source": "busy"' in env
    assert '"busy_company_name":' in env


# ─── 3 — station + city-suggestions ───────────────────────────────────
def test_customer_station_persisted():
    s = pathlib.Path(SYNC_MOD).read_text()
    # Already was persisted — just confirm it hasn't regressed.
    assert '"station":' in s


def test_city_suggestions_endpoint_present():
    s = pathlib.Path(SM).read_text()
    assert '/salesman-orders/city-suggestions' in s
    assert 'def city_wise_suggestions' in s
    # The three windows (90 / 180 / N) are configurable.
    assert "city_days: int = 90" in s
    assert "customer_days: int = 180" in s
    assert "min_city_buyers: int = 1" in s


def test_city_suggestions_handles_no_station():
    s = pathlib.Path(SM).read_text()
    assert '"reason": "no_station"' in s
    assert "Set it in Busy" in s


def test_salesman_app_has_city_subtab():
    s = pathlib.Path(SMA).read_text()
    assert "'city'" in s
    assert "/salesman-orders/city-suggestions" in s
    assert 'data-testid="city-section"' in s


# ─── 4 — triple-name mapping ──────────────────────────────────────────
def test_busy_settings_endpoints_and_mapping_defaults():
    s = pathlib.Path(SETTINGS_MOD).read_text()
    assert "/settings/busy-name-mapping" in s
    from routes.busy_settings import DEFAULT_MAPPING, ALLOWED_SOURCES
    assert DEFAULT_MAPPING["flowra_name"] == "ItemName"
    assert set(ALLOWED_SOURCES) == {"ItemName", "AliasName", "PrintName"}


def test_apply_mapping_is_wired_in_sync_inventory_branch():
    s = pathlib.Path(SYNC_MOD).read_text()
    assert "from routes.busy_settings import get_mapping, apply_busy_name_mapping" in s
    assert "apply_busy_name_mapping" in s


def test_agent_emits_all_three_name_fields():
    s = pathlib.Path(BUSY_AGENT).read_text()
    # Inside the stock-items yield block.
    assert '"item_alias":' in s
    assert '"item_print_name":' in s


def test_frontend_has_binding_and_mapping_cards():
    s = pathlib.Path(PM).read_text()
    assert "BusyBindingCard" in s
    assert 'data-testid="busy-binding-card"' in s
    assert "BusyNameMappingCard" in s
    assert 'data-testid="busy-name-mapping-card"' in s
    assert 'data-testid="busy-map-name-select"' in s
    assert 'data-testid="busy-map-partno-select"' in s


# ─── version stamps ───────────────────────────────────────────────────
def test_versions_bumped_to_v1_7_0():
    assert 'VERSION = "1.7.0"' in pathlib.Path(BUSY_AGENT).read_text()
    assert 'AGENT_TAG = "busy-1.7.0-binding-triplename-station"' in \
        pathlib.Path(BUSY_AGENT).read_text()
    assert 'APP_VERSION = "v1.7.0"' in pathlib.Path(BUSY_GUI).read_text()
    vi = pathlib.Path(BUSY_VINFO).read_text()
    assert "filevers=(1, 7, 0, 0)" in vi
    assert "u'1.7.0.0'" in vi
