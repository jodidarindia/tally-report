"""iter-169: Busy Agent v1.6.2 — resilience to corrupt Access memo cells.

import re
Field report (NAVDURGA AUTO SPARES JABALPUR / COMP0001 NAV 26-27):
`access_parser._parse_memo` crashes with
`TypeError: 'NoneType' object is not subscriptable` on a corrupt memo
overflow pointer. v1.6.1 propagated the exception all the way up and
aborted the entire sync at Phase 1/15 (customers). v1.6.2 adds three
layers of defence:

1. Monkey-patch `access_parser.AccessTable._parse_memo` at import time
   to swallow (TypeError / IndexError / AttributeError / KeyError /
   ValueError) and return "" instead.
2. Wrap `self._ap.parse_table(table)` in a try/except — treat an
   un-parseable table as empty rows for the current cycle so the
   remaining phases keep running.
3. Wrap each phase in `run_full_sync` in its own try/except so one
   crashing extractor cannot abort the other 14.
"""
import pathlib
import re


AGENT = "/app/desktop-agent/build-kit-busy/flowra_busy_agent.py"
GUI = "/app/desktop-agent/build-kit-busy/flowra_busy_gui.py"
VINFO = "/app/desktop-agent/build-kit-busy/version_info.txt"


def test_memo_monkey_patch_installed():
    src = pathlib.Path(AGENT).read_text()
    # Patch is installed exactly once per process via a module-level
    # sentinel so repeated AccessParser instantiations don't rewrap.
    assert "_flowra_memo_patch_installed" in src
    assert "_safe_parse_memo" in src
    # Must swallow the specific error class that bit the customer.
    assert "TypeError" in src
    # Must still log at DEBUG so a sync of 50k rows with one corrupt
    # memo doesn't flood the log.
    assert "logger.debug" in src and "corrupt memo cell" in src


def test_parse_table_has_try_except():
    """Even if the monkey-patch misses a new library-internal crash,
    parse_table() must degrade to an empty row list, not propagate."""
    src = pathlib.Path(AGENT).read_text()
    # Locate _load_table_via_ap body.
    m = re.search(
        r"def _load_table_via_ap\(.*?\n(.*?)(?=\n    def |\nclass )",
        src, re.S,
    )
    assert m, "_load_table_via_ap not found"
    body = m.group(1)
    assert "try:" in body
    assert "self._ap.parse_table(table)" in body
    assert "access_parser crashed parsing table" in body


def test_run_full_sync_isolates_each_phase():
    """One bad extractor must NOT abort the remaining 14 phases."""
    src = pathlib.Path(AGENT).read_text()
    m = re.search(
        r"for i, \(dtype, extractor_fn, id_key\) in enumerate\(sync_phases, 1\):(.*?)gc\.collect\(\)",
        src, re.S,
    )
    assert m, "sync-phases loop not found"
    body = m.group(1)
    assert "self.api.sync_generator" in body
    assert "phase_failed" in body
    assert "continuing with the next" in body or "continue" in body


def test_agent_tag_and_app_version_bumped():
    """v1.6.2 shipped the resilience; v1.7.0+ keeps it. The TAG/VERSION
    strings move forward with each release — we just need to make sure
    they haven't REGRESSED below 1.6.2."""
    agent_src = pathlib.Path(AGENT).read_text()
    gui_src = pathlib.Path(GUI).read_text()
    # Match any 1.7.x or 1.6.(>=2).
    m = re.search(r'VERSION\s*=\s*"(\d+)\.(\d+)\.(\d+)"', agent_src)
    assert m
    maj, mnr, pch = (int(x) for x in m.groups())
    assert (maj, mnr, pch) >= (1, 6, 2)
    assert "corrupt-memo-resilient" in agent_src or "binding-triplename" in agent_src
    m2 = re.search(r'APP_VERSION\s*=\s*"v(\d+)\.(\d+)\.(\d+)"', gui_src)
    assert m2
    maj2, mnr2, pch2 = (int(x) for x in m2.groups())
    assert (maj2, mnr2, pch2) >= (1, 6, 2)


def test_windows_file_metadata_bumped():
    vi = pathlib.Path(VINFO).read_text()
    m = re.search(r"filevers=\((\d+),\s*(\d+),\s*(\d+),\s*0\)", vi)
    assert m
    maj, mnr, pch = (int(x) for x in m.groups())
    assert (maj, mnr, pch) >= (1, 6, 2)
