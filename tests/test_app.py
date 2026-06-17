import io
import os
import shutil
import tempfile

import pytest
from PIL import Image

from app import create_app
from app.models import db


@pytest.fixture
def app():
    test_dir = tempfile.mkdtemp()
    flask_app = create_app("testing")
    flask_app.config["PHOTOS_DIR"] = os.path.join(test_dir, "photos")
    flask_app.config["DATA_DIR"] = test_dir
    flask_app.config["MAX_PHOTOS_PER_CAMERA"] = 3  # small number, faster tests
    os.makedirs(flask_app.config["PHOTOS_DIR"], exist_ok=True)

    yield flask_app

    shutil.rmtree(test_dir, ignore_errors=True)


@pytest.fixture
def client(app):
    return app.test_client()


def fake_image_bytes():
    buf = io.BytesIO()
    Image.new("RGB", (50, 50), color="red").save(buf, format="JPEG")
    buf.seek(0)
    return buf


def test_index_sets_camera_cookie_and_shows_full_roll(client, app):
    response = client.get("/")
    assert response.status_code == 200
    assert b"3" in response.data  # MAX_PHOTOS_PER_CAMERA from fixture
    assert response.headers.get("Set-Cookie") is not None


def test_capture_increments_counter_until_finished(client):
    client.get("/")  # establish the camera_id cookie

    for expected_remaining in (2, 1, 0):
        response = client.post(
            "/capture",
            data={"photo": (fake_image_bytes(), "photo.jpg")},
            content_type="multipart/form-data",
        )
        body = response.get_json()
        assert body["success"] is True
        assert body["remaining"] == expected_remaining

    assert body["finished"] is True

    # One more shot should be rejected -- the roll is used up.
    response = client.post(
        "/capture",
        data={"photo": (fake_image_bytes(), "photo.jpg")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 409
    assert response.get_json()["success"] is False


def test_admin_gallery_requires_login(client):
    response = client.get("/admin/gallery")
    assert response.status_code == 302
    assert "/admin/login" in response.headers["Location"]


def test_admin_login_with_correct_password(client, app, monkeypatch):
    from werkzeug.security import generate_password_hash

    app.config["ADMIN_PASSWORD_HASH"] = generate_password_hash("testpass")

    response = client.post("/admin/login", data={"password": "testpass"})
    assert response.status_code == 302

    response = client.get("/admin/gallery")
    assert response.status_code == 200
