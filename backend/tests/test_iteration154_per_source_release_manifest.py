"""Iteration 154 — Per-source agent release manifests + Setup label
polish.

Locks:
  1. `/api/agent/latest-version` accepts `?source=tally|busy` and
     returns the corresponding manifest (v9.8.x for Tally, v1.5.x for
     Busy). Backwards-compat: no `source` param → Tally.
  2. Both manifest files exist on disk.
  3. The frontend Setup page reads `agent_release_busy.json` for Busy
     tenants — verified by re-fetching after `sync-status` populates
     the agent source.
  4. CreditorGroupsPanel label reads "Tally/Busy parent groups".
"""
import os
import sys
import json
from pathlib import Path

import requests

for _line in Path("/app/backend/.env").read_text().splitlines():
    if "=" in _line and not _line.strip().startswith("#"):
        _k, _v = _line.split("=", 1)
        os.environ.setdefault(_k.strip(), _v.strip())

sys.path.insert(0, "/app/backend")

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    for line in Path("/app/frontend/.env").read_text().splitlines():
        if line.startswith("REACT_APP_BACKEND_URL="):
            BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
            break


def test_release_manifests_on_disk():
    tally_path = Path("/app/backend/agent_release.json")
    busy_path = Path("/app/backend/agent_release_busy.json")
    assert tally_path.exists()
    assert busy_path.exists()
    tally = json.loads(tally_path.read_text())
    busy = json.loads(busy_path.read_text())
    assert tally["version"].startswith("9.")
    assert busy["version"].startswith("1.5.")
    assert "Tally" in tally.get("download_url", "")
    assert "Busy" in busy.get("download_url", "")


def test_endpoint_routes_by_source():
    r_default = requests.get(f"{BASE_URL}/api/agent/latest-version", timeout=15)
    assert r_default.status_code == 200
    d_default = r_default.json()["data"]

    r_tally = requests.get(f"{BASE_URL}/api/agent/latest-version",
                           params={"source": "tally"}, timeout=15)
    d_tally = r_tally.json()["data"]

    r_busy = requests.get(f"{BASE_URL}/api/agent/latest-version",
                          params={"source": "busy"}, timeout=15)
    d_busy = r_busy.json()["data"]

    # Backwards-compat: no source → Tally
    assert d_default["version"] == d_tally["version"]
    # Busy version must be v1.5.x and Tally must be v9.x — never the
    # other way round.
    assert d_busy["version"].startswith("1.5."), d_busy
    assert d_tally["version"].startswith("9."), d_tally
    # Download URLs must match their agent
    assert "Busy" in d_busy["download_url"]
    assert "Tally" in d_tally["download_url"]


def test_check_update_routes_by_source():
    r = requests.get(f"{BASE_URL}/api/agent/check-update",
                     params={"current": "1.5.0", "source": "busy"}, timeout=15)
    d = r.json()["data"]
    assert d["update_available"] is True
    assert d["latest"].startswith("1.5.")
    # Tally with old version — should also flag update against Tally's
    # manifest, not accidentally Busy's.
    r2 = requests.get(f"{BASE_URL}/api/agent/check-update",
                      params={"current": "9.0.0", "source": "tally"}, timeout=15)
    d2 = r2.json()["data"]
    assert d2["latest"].startswith("9.")


def test_creditor_panel_label_says_tally_slash_busy():
    src = Path("/app/frontend/src/components/CreditorGroupsPanel.js").read_text()
    assert "Tally/Busy" in src, (
        "CreditorGroupsPanel must read 'Tally/Busy parent groups'"
    )


def test_setup_page_removed_pure_python_blurbs():
    src = Path("/app/frontend/src/pages/TallySetup.js").read_text()
    # The two blurbs the user explicitly asked us to remove.
    assert "pure-Python access_parser" not in src, (
        "Setup page still contains the 'pure-Python access_parser' blurb"
    )
    assert "no OLE DB provider install" not in src, (
        "Setup page still mentions OLE DB details"
    )
    assert "no file password" not in src, (
        "Setup page still mentions the file password"
    )


def test_setup_page_refetches_release_when_agent_source_arrives():
    """Guard: the useEffect that re-fetches the release manifest when
    the sync-status agent_version arrives — the first-paint fix so
    Busy tenants don't briefly see v9.8.x."""
    src = Path("/app/frontend/src/pages/TallySetup.js").read_text()
    assert "[syncStatus?.agent_version]" in src, (
        "TallySetup must depend on syncStatus.agent_version so the "
        "release manifest re-fetches once the source is known."
    )
