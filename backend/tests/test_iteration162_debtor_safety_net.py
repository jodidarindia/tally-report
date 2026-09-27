"""iter-162: Server-side safety-net for Busy hierarchy misses in CRM.

Older Busy Agent builds (<= v1.5.9) had a non-walking ``_resolve_category``
that treated custom sub-groups (e.g. "SUNDRY DEBTORS - JBP") as "other"
and skipped every party under them. Only 2-ish debtors sitting directly
under group 116 landed in Mongo. This test locks in the server-side
fallback that synthesizes customer rows from sale-party names when the
synced list is suspiciously small.
"""
import asyncio
from routes.customers import _synthesize_missing_debtors_from_sales


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def test_bsa_scenario_synthesizes_missing_parties():
    synced = [{'customer_name': 'A'}, {'customer_name': 'JAIN AUTOMOBILES JANJGIR'}]
    sales = [{'party_name': f'Customer {i}'} for i in range(50)]
    sales += [{'party_name': 'A'}, {'party_name': 'JAIN AUTOMOBILES JANJGIR'}]
    out = _run(_synthesize_missing_debtors_from_sales(synced, sales, 't', 'c'))
    synth = [c for c in out if c.get('_synthesized')]
    assert len(synth) == 50
    assert all(c['ledger_group'] == 'Sundry Debtors' for c in synth)
    assert all(c['customer_id'].startswith('synthesized-') for c in synth)


def test_healthy_tenant_not_touched():
    """400 synced overlaps 380 sale parties — never trigger."""
    synced = [{'customer_name': f'Cust {i}'} for i in range(400)]
    sales = [{'party_name': f'Cust {i}'} for i in range(380)]
    out = _run(_synthesize_missing_debtors_from_sales(synced, sales, 't', 'c'))
    assert len([c for c in out if c.get('_synthesized')]) == 0
    assert len(out) == 400


def test_tiny_tenant_with_no_missing_parties_not_touched():
    synced = [{'customer_name': f'Cust {i}'} for i in range(5)]
    sales = [{'party_name': f'Cust {i}'} for i in range(5)]
    out = _run(_synthesize_missing_debtors_from_sales(synced, sales, 't', 'c'))
    assert len([c for c in out if c.get('_synthesized')]) == 0


def test_empty_sales_no_op():
    synced = [{'customer_name': 'X'}]
    out = _run(_synthesize_missing_debtors_from_sales(synced, [], 't', 'c'))
    assert out == synced


def test_synthesized_row_carries_full_schema():
    """Ensure the synthesized dict has every field the outstanding
    endpoint expects (schema-parity with a real synced_customers row).
    """
    synced = []
    sales = [{'party_name': 'Some New Party'}]
    out = _run(_synthesize_missing_debtors_from_sales(synced, sales, 'tid', 'cid'))
    assert len(out) == 1
    row = out[0]
    for key in ("customer_name", "customer_id", "ledger_group", "group_name",
                "phone", "mobile_number", "whatsapp_number", "email",
                "address", "state", "gst_number", "salesman_name",
                "outstanding_amount", "opening_balance", "closing_balance"):
        assert key in row, f"missing key: {key}"
    assert row['tenant_id'] == 'tid'
    assert row['company_id'] == 'cid'
