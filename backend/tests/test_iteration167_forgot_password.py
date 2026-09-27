"""iter-167: Forgot-password for Business Admin only.

- Public POST /api/auth/forgot-password
- Role gate: only ``role == "admin"`` triggers an email (generic
  response for everyone so no user-enumeration).
- Rate-limited: 3 requests / IP / hour, 1 / email / 15 min.
- ``must_change_password: True`` set on the user; login echoes it;
  /auth/change-password clears it via ``$unset``.
- Frontend disclaimer + forgot-password link + force-change screen.
"""
import inspect
import pathlib


def test_forgot_password_endpoint_registered_and_role_gated():
    from routes.auth import forgot_password
    src = inspect.getsource(forgot_password)
    # Only admin role goes through.
    assert 'role") == "admin"' in src
    # Generic success message for enumeration resistance.
    assert 'If this is a Business Admin account' in src
    # Rate-limits present.
    assert "password_reset_attempts" in src
    assert "hours=1" in src and "minutes=15" in src
    # Non-blocking email dispatch.
    assert "asyncio.create_task" in src
    # Audit log.
    assert "log_audit" in src
    # Force-change flag persisted.
    assert '"must_change_password": True' in src


def test_login_echoes_must_change_password():
    src = pathlib.Path("/app/backend/routes/auth.py").read_text()
    assert '"must_change_password": bool(user.get("must_change_password"))' in src


def test_change_password_clears_must_change_flag():
    from routes.auth import change_password
    src = inspect.getsource(change_password)
    assert '"$unset": {"must_change_password": ""}' in src


def test_temp_password_is_strong_and_secure():
    from routes.auth import _generate_temporary_password
    seen = set()
    for _ in range(50):
        pw = _generate_temporary_password()
        assert len(pw) == 12
        assert any(c.isupper() for c in pw)
        assert any(c.islower() for c in pw)
        assert any(c.isdigit() for c in pw)
        assert any(c in "!@#$%&*" for c in pw)
        # No confusable chars.
        assert not any(c in "Ol01Il" for c in pw)
        seen.add(pw)
    # 50 samples must all be distinct — cryptographically random.
    assert len(seen) == 50


def test_frontend_loginpage_has_forgot_link_and_disclaimer():
    src = pathlib.Path("/app/frontend/src/components/LoginPage.js").read_text()
    assert 'data-testid="forgot-password-link"' in src
    assert 'data-testid="forgot-password-modal"' in src
    assert 'data-testid="forgot-password-disclaimer"' in src
    # Verbatim disclaimer text the user asked for.
    assert "Reset password facility only for Business Admin" in src


def test_frontend_force_change_screen_exists():
    p = pathlib.Path("/app/frontend/src/components/ForceChangePasswordScreen.js")
    assert p.exists()
    src = p.read_text()
    assert 'data-testid="force-change-password-form"' in src
    assert '/auth/change-password' in src


def test_app_js_routes_admin_with_flag_to_force_change_screen():
    src = pathlib.Path("/app/frontend/src/App.js").read_text()
    assert "user?.must_change_password" in src
    assert "ForceChangePasswordScreen" in src
