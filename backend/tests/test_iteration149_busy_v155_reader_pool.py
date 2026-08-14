"""Iteration 149 — Busy Agent v1.5.5 BusyDBReader object pool.

Locks in the pool's contract so future refactors can't silently reopen
the .bds file per helper (the ~25× overhead we shipped in v1.5.4).

Scenarios:
  1. `BusyDataExtractor._get_reader(path)` returns a `_PooledReader`
     proxy — the underlying `BusyDBReader` is opened ONCE per path
     within the same sync cycle.
  2. Repeated `_get_reader(path)` calls hand out proxies that wrap the
     SAME underlying reader (identity check on `._inner`).
  3. `_PooledReader.close()` is a no-op so legacy helper `finally:
     reader.close()` blocks stay safe.
  4. `BusyDataExtractor.close_readers()` empties the pool AND calls
     `close()` on every real reader exactly once.
  5. Version bump: VERSION == '1.5.5', AGENT_TAG starts with 'busy-1.5.5'.
  6. `run_full_sync` invokes `close_readers()` in its `finally` block
     (source anchor — cannot silently regress).
"""
import sys
from pathlib import Path

sys.path.insert(0, "/app/desktop-agent/build-kit-busy")


def test_pool_reuses_reader_for_same_path(tmp_path, monkeypatch):
    """Even for a nonexistent path (`BusyDBReader.__init__` doesn't
    open the file eagerly — that happens on first iter_rows), the pool
    must dedupe by path."""
    from flowra_busy_agent import BusyDataExtractor, BusyDBReader

    # Empty data folder — extractor still constructs successfully.
    ex = BusyDataExtractor(str(tmp_path))
    p1 = ex._get_reader("/tmp/fake-a.bds")
    p2 = ex._get_reader("/tmp/fake-a.bds")
    p3 = ex._get_reader("/tmp/fake-b.bds")

    # Proxies are DIFFERENT objects (each call returns a fresh _PooledReader)…
    assert p1 is not p2
    # …but wrap the SAME underlying BusyDBReader.
    assert p1._inner is p2._inner
    assert isinstance(p1._inner, BusyDBReader)
    # Different path → different underlying reader.
    assert p3._inner is not p1._inner
    # Pool state reflects both paths.
    assert set(ex._reader_pool.keys()) == {"/tmp/fake-a.bds", "/tmp/fake-b.bds"}


def test_pooled_reader_close_is_noop(tmp_path):
    from flowra_busy_agent import BusyDataExtractor
    ex = BusyDataExtractor(str(tmp_path))
    p = ex._get_reader("/tmp/fake.bds")

    inner_before = p._inner
    p.close()   # legacy helper `finally: reader.close()` path
    # Pool must still hold the underlying reader — close() was a no-op.
    assert "/tmp/fake.bds" in ex._reader_pool
    assert ex._reader_pool["/tmp/fake.bds"] is inner_before


def test_close_readers_empties_pool(tmp_path):
    """close_readers() must (a) call inner .close() exactly once per
    reader and (b) clear the pool so the next tick reopens fresh."""
    from flowra_busy_agent import BusyDataExtractor

    ex = BusyDataExtractor(str(tmp_path))
    p1 = ex._get_reader("/tmp/x.bds")
    p2 = ex._get_reader("/tmp/y.bds")

    close_calls = []
    p1._inner.close = lambda: close_calls.append("x")
    p2._inner.close = lambda: close_calls.append("y")

    ex.close_readers()
    assert ex._reader_pool == {}, "pool must be empty after close_readers()"
    assert sorted(close_calls) == ["x", "y"], (
        "each real reader must be closed exactly once"
    )

    # Idempotent — calling again is safe.
    ex.close_readers()
    assert ex._reader_pool == {}


def test_version_bumped_to_155():
    import importlib
    import flowra_busy_agent
    importlib.reload(flowra_busy_agent)
    assert flowra_busy_agent.VERSION == "1.5.5"
    assert flowra_busy_agent.AGENT_TAG.startswith("busy-1.5.5")


def test_gui_and_agent_versions_stay_in_sync():
    """build.bat reads APP_VERSION from flowra_busy_gui.py to name the
    output EXE (FlowraBusyAgent_v1.5.5.exe). If the GUI's APP_VERSION
    drifts from flowra_busy_agent.VERSION we ship a v1.5.5 binary named
    v1.5.3 — exactly the bug that just bit us in v1.5.4/1.5.5.
    """
    import re
    import flowra_busy_agent
    gui_src = Path("/app/desktop-agent/build-kit-busy/flowra_busy_gui.py").read_text()
    m = re.search(r'^APP_VERSION\s*=\s*"v([\d.]+)"', gui_src, re.M)
    assert m, "APP_VERSION missing from flowra_busy_gui.py"
    gui_ver = m.group(1)
    assert gui_ver == flowra_busy_agent.VERSION, (
        f"Version drift: flowra_busy_gui.py APP_VERSION='v{gui_ver}' vs "
        f"flowra_busy_agent.VERSION='{flowra_busy_agent.VERSION}'. "
        "build.bat reads APP_VERSION for the EXE filename — keep both "
        "in lockstep."
    )


def test_full_sync_calls_close_readers_source_anchor():
    """Guard against a future refactor accidentally dropping the
    `close_readers()` call from run_full_sync's `finally:` block."""
    src = Path("/app/desktop-agent/build-kit-busy/flowra_busy_agent.py").read_text()
    # Must appear at least once (full sync) plus once (quick sync).
    assert src.count("self.extractor.close_readers()") >= 2, (
        "close_readers() must be invoked from both run_full_sync and "
        "run_quick_sales_sync"
    )
    # And the class contract must exist.
    assert "def close_readers(self):" in src
    assert "def _get_reader(self, db_path" in src
    assert "class _PooledReader:" in src


def test_all_extractor_helpers_use_pool_not_raw_reader():
    """CI guard — every helper that reads a .bds file must go through
    `self._get_reader(db_path)`, never `BusyDBReader(db_path)` directly
    (that would reopen the file, defeating the pool)."""
    src = Path("/app/desktop-agent/build-kit-busy/flowra_busy_agent.py").read_text()
    # `BusyDBReader(...)` may only appear inside `_get_reader` itself.
    hits = [
        (ln + 1, line) for ln, line in enumerate(src.splitlines())
        if "BusyDBReader(" in line
    ]
    # Filter out class definition + docstring/comment references.
    body_hits = [
        (n, l) for n, l in hits
        if "class BusyDBReader" not in l
        and "BusyDBReader:" not in l
        and not l.strip().startswith("#")
        and '"BusyDBReader"' not in l
        and "'BusyDBReader'" not in l
    ]
    # Only ONE legitimate construction site: `_get_reader`.
    assert len(body_hits) == 1, (
        f"Expected exactly 1 BusyDBReader(...) construction (inside "
        f"_get_reader). Found {len(body_hits)}:\n" +
        "\n".join(f"  L{n}: {l.strip()}" for n, l in body_hits)
    )
    assert "inner = BusyDBReader(db_path)" in body_hits[0][1]
