"""Backend tests for Blog Rich Text Editor + Image Upload feature (Emergent Object Storage)."""
import base64
import io
import os
import uuid

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL"):
                BASE_URL = line.split("=", 1)[1].strip().strip('"').rstrip("/")

# 1x1 PNG
PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGNgYGD4DwABBAEAfbLI3wAAAABJRU5ErkJggg=="
)


@pytest.fixture(scope="module")
def sa_client():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"username": "superadmin", "password": "superadmin123"})
    assert r.status_code == 200, f"login failed: {r.text}"
    body = r.json()
    token = (body.get("data") or {}).get("token") or body.get("token")
    assert token, f"no token in login response: {body}"
    s.headers.update({"Authorization": f"Bearer {token}"})
    return s


@pytest.fixture(scope="module")
def uploaded_image(sa_client):
    files = {"file": (f"test_{uuid.uuid4().hex[:6]}.png", PNG_BYTES, "image/png")}
    r = sa_client.post(f"{BASE_URL}/api/super-admin/blog/upload-image", files=files)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j.get("success") is True, j
    data = j["data"]
    assert "url" in data and "path" in data
    assert data["url"].startswith("/api/public/blog-image/flowra/blog/")
    return data


class TestImageUpload:
    def test_upload_png_success(self, uploaded_image):
        assert uploaded_image["path"].startswith("flowra/blog/")

    def test_reject_non_image_extension(self, sa_client):
        files = {"file": ("bad.txt", b"hello world", "text/plain")}
        r = sa_client.post(f"{BASE_URL}/api/super-admin/blog/upload-image", files=files)
        assert r.status_code == 200
        j = r.json()
        assert j.get("success") is False
        assert "JPG" in (j.get("error") or "") or "allowed" in (j.get("error") or "").lower()

    def test_reject_oversize(self, sa_client):
        big = b"\x00" * (5 * 1024 * 1024 + 100)
        files = {"file": ("big.png", big, "image/png")}
        r = sa_client.post(f"{BASE_URL}/api/super-admin/blog/upload-image", files=files)
        assert r.status_code == 200
        j = r.json()
        assert j.get("success") is False
        assert "5 MB" in (j.get("error") or "") or "exceed" in (j.get("error") or "").lower()

    def test_public_get_image(self, uploaded_image):
        url = f"{BASE_URL}{uploaded_image['url']}"
        # Use a fresh session (no auth) to verify public access
        r = requests.get(url)
        assert r.status_code == 200, f"got {r.status_code}: {r.text[:200]}"
        assert r.headers.get("content-type", "").startswith("image/")
        assert "cache-control" in {k.lower() for k in r.headers.keys()}
        assert len(r.content) > 0


class TestBlogBodyHtml:
    def test_create_update_get_body_html(self, sa_client):
        payload = {
            "title": f"TEST_ RTE Post {uuid.uuid4().hex[:6]}",
            "excerpt": "Test",
            "body_html": "<p><strong>Hi</strong></p>",
            "body_md": "**Hi**",
            "published": False,
        }
        r = sa_client.post(f"{BASE_URL}/api/super-admin/blog", json=payload)
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["success"] is True
        post_id = j["data"]["post_id"]
        slug = j["data"]["slug"]

        # GET verifies persistence
        r2 = sa_client.get(f"{BASE_URL}/api/super-admin/blog/{post_id}")
        assert r2.status_code == 200
        got = r2.json()["data"]
        assert got["body_html"] == "<p><strong>Hi</strong></p>"

        # PUT updates body_html
        new_html = "<h2>Updated</h2><p>New</p>"
        r3 = sa_client.put(f"{BASE_URL}/api/super-admin/blog/{post_id}", json={"body_html": new_html, "published": True})
        assert r3.status_code == 200, r3.text
        assert r3.json()["success"] is True

        r4 = sa_client.get(f"{BASE_URL}/api/super-admin/blog/{post_id}")
        assert r4.json()["data"]["body_html"] == new_html
        assert r4.json()["data"]["published"] is True

        # Public GET after publish returns body_html
        r5 = requests.get(f"{BASE_URL}/api/public/blog/{slug}")
        assert r5.status_code == 200
        pubdata = r5.json()["data"]
        assert pubdata["body_html"] == new_html

        # Cleanup
        sa_client.delete(f"{BASE_URL}/api/super-admin/blog/{post_id}")
