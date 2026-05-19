"""Tests for iteration 100 — global admin CC + FLOWRA Insights branding.

We monkey-patch ``resend.Emails.send`` so no real email is sent. The tests
verify:
  • Lead-signup notification sends to support@flowralive.in with the
    jodidarindiaoffice@gmail.com CC and an "FLOWRA Insights ·" subject.
  • Subscription-renewed / expiry / employee-added admin emails carry
    the global CC and Insights subject.
  • Credential emails (welcome + employee credentials) do NOT carry the
    global CC (sensitive content).
"""
import asyncio
import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services import email_service  # noqa: E402


class _CapturingSender:
    """Drop-in replacement for ``resend.Emails.send`` that records the
    payload instead of dispatching a real email."""

    def __init__(self):
        self.calls = []

    def __call__(self, params):
        self.calls.append(params)
        return {"id": f"test-{len(self.calls)}"}


@pytest.fixture
def capture(monkeypatch):
    cap = _CapturingSender()
    # Force the API-key gate open so send_email proceeds.
    monkeypatch.setattr(email_service, "RESEND_API_KEY", "test-key")
    monkeypatch.setattr(email_service.resend.Emails, "send", cap)
    return cap


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro) if False else asyncio.run(coro)


def test_lead_signup_notification_has_cc_and_insights_subject(capture):
    prospect = {
        "prospect_id": "PRO-ABCDEF12",
        "company_name": "Acme Trading",
        "contact_person": "Rajesh A.",
        "email": "rajesh@acme.test",
        "phone": "+91-98765-43210",
        "gst_number": "22AAAAA0000A1Z5",
        "address": "Mumbai",
        "selected_plan": "professional",
        "message": "Need <CRM> & inventory",
        "referral_code": "REF-XYZ",
        "ip_address": "1.2.3.4",
        "returning_user": False,
    }
    _run(email_service.send_lead_signup_notification(prospect))
    assert len(capture.calls) == 1
    p = capture.calls[0]
    assert p["to"] == ["support@flowralive.in"]
    assert p["cc"] == ["jodidarindiaoffice@gmail.com"]
    assert p["subject"].startswith("FLOWRA Insights · New Lead")
    assert "Acme Trading" in p["subject"]
    # HTML must contain the FLOWRA Insights band.
    assert "FLOWRA INSIGHTS" in p["html"]
    # Message must be HTML-escaped.
    assert "&lt;CRM&gt;" in p["html"]


def test_demo_request_notification(capture):
    _run(email_service.send_lead_demo_requested_notification({
        "prospect_id": "PRO-1", "company_name": "Beta Co", "email": "x@y.test",
    }))
    p = capture.calls[0]
    assert p["to"] == ["support@flowralive.in"]
    assert p["cc"] == ["jodidarindiaoffice@gmail.com"]
    assert "Demo Requested" in p["subject"]


def test_requirements_notification(capture):
    _run(email_service.send_lead_requirements_notification(
        {"prospect_id": "PRO-2", "company_name": "Gamma", "email": "g@g.test"},
        ["CRM", "Inventory", "Beat Plan"],
        "Need integration with Tally Prime",
    ))
    p = capture.calls[0]
    assert p["cc"] == ["jodidarindiaoffice@gmail.com"]
    assert "Requirements Submitted" in p["subject"]
    for feat in ("CRM", "Inventory", "Beat Plan"):
        assert feat in p["html"]


def test_subscription_renewed_has_global_cc(capture):
    _run(email_service.send_subscription_renewed(
        "user@biz.test", "Biz Owner", "enterprise", 12, "20 May 2027"))
    p = capture.calls[0]
    assert p["to"] == ["user@biz.test"]
    assert p["cc"] == ["jodidarindiaoffice@gmail.com"]
    assert p["subject"].startswith("FLOWRA Insights · Subscription Renewed")


def test_expiry_warning_has_global_cc(capture):
    _run(email_service.send_subscription_expiry_warning(
        "user@biz.test", "Biz", 5, "25 May 2026"))
    p = capture.calls[0]
    assert p["cc"] == ["jodidarindiaoffice@gmail.com"]
    assert "FLOWRA Insights" in p["subject"]
    assert "URGENT" in p["subject"]


def test_employee_admin_email_has_global_cc(capture):
    _run(email_service.send_employee_created_to_admin(
        "admin@biz.test", "Admin", "Emp One", "emp@biz.test", "employee"))
    p = capture.calls[0]
    assert p["cc"] == ["jodidarindiaoffice@gmail.com"]
    assert "FLOWRA Insights" in p["subject"]


def test_subscription_started_has_no_cc(capture):
    """Welcome email carries a password — must not CC anyone."""
    _run(email_service.send_subscription_started(
        "new@biz.test", "New Co", "starter", 12, "20 May 2027", password="SuperSecret"))
    p = capture.calls[0]
    assert "cc" not in p


def test_employee_credentials_email_has_no_cc(capture):
    """Employee credentials email carries a password — must not CC anyone."""
    _run(email_service.send_employee_created_to_employee(
        "emp@biz.test", "Emp One", "TempPass123", "Biz Co"))
    p = capture.calls[0]
    assert "cc" not in p


def test_cc_never_duplicates_to(capture, monkeypatch):
    """If TO already equals GLOBAL_ADMIN_CC, the CC is dropped to avoid dupes."""
    _run(email_service.send_email(
        email_service.GLOBAL_ADMIN_CC,
        "Test",
        "<p>x</p>",
        cc="auto",
    ))
    p = capture.calls[0]
    assert "cc" not in p  # de-duplicated to empty -> omitted
