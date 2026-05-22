"""Iteration 108 — AI Insights page must render structured LLM output
gracefully, not as raw JSON blobs.

Customer report: opening an AI Insights query like "Show items with low
stock that need immediate reordering" displayed lines like:

    1  {"insight":"Zero immediate reorder triggers","detail":"Across all
       35 inventory items, quantity >= reorder_level.","risk":"..."}
    2  {"insight":"Closest-to-reorder SKUs exist (monitor list)", ...}

…because the LLM put structured objects inside the `key_insights` /
`recommendations` arrays, and the React UI used `JSON.stringify()` as a
safety net for non-string entries.

Fix (frontend-only): a new helper module `AIInsightRenderers.jsx`
detects the common LLM-shape objects (`{insight, detail, risk}`,
`{priority, action, expected_impact}`, arrays of records, etc.) and
renders them as human-readable blocks. This Python test asserts the
shape contract by reading the JSX source and verifying:

  • the helper file exists and exports the expected renderers
  • both `EnhancedAIReports.js` and `AIQueryBuilder.js` import + use them
  • no page still calls `JSON.stringify(insight)` or
    `JSON.stringify(rec)` as a last-resort fallback
"""
import os
import re

ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
RENDERERS = os.path.join(ROOT, "frontend", "src", "components", "AIInsightRenderers.jsx")
ENH = os.path.join(ROOT, "frontend", "src", "pages", "EnhancedAIReports.js")
QB = os.path.join(ROOT, "frontend", "src", "pages", "AIQueryBuilder.js")


def _read(p):
    with open(p, "r", encoding="utf-8") as f:
        return f.read()


def test_renderers_file_exists_with_expected_exports():
    assert os.path.exists(RENDERERS), "AIInsightRenderers.jsx must exist"
    src = _read(RENDERERS)
    for fn in (
        "renderStructuredInsight",
        "renderStructuredRecommendation",
        "renderMetricValue",
        "renderDetailedAnalysis",
    ):
        assert f"export function {fn}" in src, f"missing export {fn}"


def test_renderers_handle_structured_insight_object_shape():
    """The {insight, detail, risk} object shape (the one the customer saw
    dumped as raw JSON) must be specifically destructured."""
    src = _read(RENDERERS)
    assert "{ insight: title, detail, risk, ...rest }" in src, (
        "renderStructuredInsight must destructure the {insight, detail, risk} shape"
    )


def test_renderers_handle_structured_recommendation_object_shape():
    src = _read(RENDERERS)
    assert "{ priority, action, expected_impact, impact, ...rest }" in src, (
        "renderStructuredRecommendation must destructure the {priority, action, expected_impact} shape"
    )


def test_enhanced_ai_reports_uses_renderers():
    src = _read(ENH)
    assert "from '../components/AIInsightRenderers'" in src
    for fn in (
        "renderStructuredInsight",
        "renderStructuredRecommendation",
        "renderMetricValue",
        "renderDetailedAnalysis",
    ):
        assert fn in src, f"EnhancedAIReports must call {fn}"


def test_ai_query_builder_uses_renderers():
    src = _read(QB)
    assert "from '../components/AIInsightRenderers'" in src
    for fn in (
        "renderStructuredInsight",
        "renderStructuredRecommendation",
        "renderMetricValue",
    ):
        assert fn in src, f"AIQueryBuilder must call {fn}"


def test_no_page_still_falls_back_to_stringify():
    """The old regression-prone pattern was:
       `typeof insight === 'object' ? JSON.stringify(insight) : insight`
       We must never see that anywhere in the AI Insights surface again."""
    bad_pattern = re.compile(
        r"JSON\.stringify\(\s*(insight|rec|recommendation)\s*\)",
        flags=re.IGNORECASE,
    )
    for p in (ENH, QB):
        src = _read(p)
        m = bad_pattern.search(src)
        assert m is None, (
            f"Found legacy JSON.stringify fallback in {p}: {m.group(0)!r}. "
            "Use the renderers in AIInsightRenderers.jsx instead."
        )
