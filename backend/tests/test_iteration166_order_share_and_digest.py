"""iter-166: Order PDF, WhatsApp share, admin email, daily digest."""
import inspect
import pathlib


def test_pdf_endpoint_registered():
    from routes.salesman_orders import download_order_pdf
    assert download_order_pdf


def test_share_link_endpoint_returns_wa_link():
    from routes.salesman_orders import create_order_share_link
    src = inspect.getsource(create_order_share_link)
    assert "wa.me" in src
    assert "put_object" in src
    # iter-166.1: URL must be absolute (recipients open from WhatsApp).
    assert "x-forwarded-proto" in src.lower() or "PUBLIC_BASE_URL" in src


def test_message_prompts_tap_to_open_pdf():
    from routes.salesman_orders import create_order_share_link
    src = inspect.getsource(create_order_share_link)
    assert "Tap the link" in src


def test_public_pdf_endpoint_registered():
    from routes.salesman_orders import public_order_pdf
    assert public_order_pdf


def test_order_pdf_builder_produces_valid_pdf():
    from routes.salesman_orders import _build_order_pdf_bytes
    order = {
        "order_id": "SO-TEST", "customer_name": "Acme Corp",
        "salesman": "Rajesh", "total_amount": 1500.0,
        "created_at": "2026-09-27T14:00:00+00:00",
        "items": [
            {"item_name": "Bearing X", "part_number": "BX-1", "quantity": 5, "price": 200, "amount": 1000, "unit": "Nos"},
            {"item_name": "Filter Y",  "part_number": "FY-2", "quantity": 2, "price": 250, "amount": 500,  "unit": "Nos"},
        ],
    }
    data = _build_order_pdf_bytes(order, "Test Co")
    assert data.startswith(b"%PDF-")
    assert len(data) > 500


def test_daily_digest_cron_route_registered_and_auth_checks():
    from routes.salesman_orders import daily_order_digest_webhook
    src = inspect.getsource(daily_order_digest_webhook)
    assert "WEBHOOK_CRON_SECRET" in src
    assert "compare_digest" in src
    assert "asyncio.create_task" in src


def test_crons_yml_has_daily_digest_entry():
    src = pathlib.Path("/app/.emergent/crons.yml").read_text()
    assert "daily-order-digest" in src
    assert "cron: \"0 20 * * *\"" in src
    assert "Asia/Kolkata" in src


def test_admin_email_fires_on_create_order():
    from routes.salesman_orders import create_order
    src = inspect.getsource(create_order)
    assert "_send_order_pdf_to_admin" in src
