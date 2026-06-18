import io
import os
import shutil
import tempfile

import piexif
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
    flask_app.config["COOLDOWN_SECONDS"] = 0  # don't make the test suite wait around
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


def fake_image_bytes_with_gps():
    buf = io.BytesIO()
    gps_ifd = {
        piexif.GPSIFD.GPSLatitude: ((40, 1), (0, 1), (0, 1)),
        piexif.GPSIFD.GPSLatitudeRef: b"N",
    }
    exif_bytes = piexif.dump({"GPS": gps_ifd})
    Image.new("RGB", (60, 60), color="blue").save(buf, format="JPEG", exif=exif_bytes)
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


def test_cooldown_blocks_rapid_shots(client, app):
    app.config["COOLDOWN_SECONDS"] = 5  # re-enable it just for this test
    client.get("/")

    first = client.post(
        "/capture",
        data={"photo": (fake_image_bytes(), "photo.jpg")},
        content_type="multipart/form-data",
    )
    assert first.get_json()["success"] is True

    second = client.post(
        "/capture",
        data={"photo": (fake_image_bytes(), "photo.jpg")},
        content_type="multipart/form-data",
    )
    assert second.status_code == 429
    assert second.get_json()["success"] is False


def test_photo_saved_losslessly_and_gps_stripped(client, app):
    client.get("/")
    response = client.post(
        "/capture",
        data={"photo": (fake_image_bytes_with_gps(), "photo.jpg")},
        content_type="multipart/form-data",
    )
    assert response.get_json()["success"] is True

    roll_dirs = os.listdir(app.config["PHOTOS_DIR"])
    assert len(roll_dirs) == 1
    saved_path = os.path.join(app.config["PHOTOS_DIR"], roll_dirs[0], "shot_01.jpg")
    with open(saved_path, "rb") as f:
        saved_bytes = f.read()

    exif_dict = piexif.load(saved_bytes)
    assert not exif_dict.get("GPS")  # GPS data removed

    # Pixel data must be byte-for-byte the same image content (lossless).
    original = Image.open(fake_image_bytes_with_gps()).convert("RGB")
    saved = Image.open(io.BytesIO(saved_bytes)).convert("RGB")
    assert list(original.getdata()) == list(saved.getdata())


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


def test_admin_can_download_roll_zip(client, app):
    from werkzeug.security import generate_password_hash

    app.config["ADMIN_PASSWORD_HASH"] = generate_password_hash("testpass")

    client.get("/")  # create a camera/roll
    client.post(
        "/capture",
        data={"photo": (fake_image_bytes(), "photo.jpg")},
        content_type="multipart/form-data",
    )

    from app.models import CameraSession

    with app.app_context():
        camera_id = CameraSession.query.first().id

    client.post("/admin/login", data={"password": "testpass"})
    response = client.get(f"/admin/gallery/{camera_id}/download")
    assert response.status_code == 200
    assert response.mimetype == "application/zip"


def test_starting_from_an_older_database_schema_self_heals(tmp_path, monkeypatch):
    """
    Regression test for the exact crash a stale data/app.db caused after
    CameraSession gained new columns (e.g. last_photo_at for the cooldown
    feature): booting the app against a database built with an *older*
    version of the schema should auto-add the missing column instead of
    raising sqlalchemy.exc.OperationalError, and must not lose existing
    rows in the process.
    """
    import sqlite3

    from config import DevelopmentConfig

    db_path = tmp_path / "old.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE camera_sessions (
            id VARCHAR(32) PRIMARY KEY,
            created_at DATETIME,
            photo_count INTEGER NOT NULL,
            finished_at DATETIME,
            created_ip VARCHAR(45),
            last_ip VARCHAR(45)
        )
        """
    )
    conn.execute(
        "INSERT INTO camera_sessions VALUES ('abc123', '2026-06-01 00:00:00', 5, NULL, '1.2.3.4', '1.2.3.4')"
    )
    conn.commit()
    conn.close()

    # config.py reads DATABASE_URL from the environment once at import
    # time, so by this point in the test session it's too late for an
    # os.environ change to matter -- patch the resolved class attribute
    # that create_app() actually reads instead.
    monkeypatch.setattr(DevelopmentConfig, "SQLALCHEMY_DATABASE_URI", f"sqlite:///{db_path}")

    flask_app = create_app("development")
    flask_app.config["PHOTOS_DIR"] = str(tmp_path / "photos")
    os.makedirs(flask_app.config["PHOTOS_DIR"], exist_ok=True)

    test_client = flask_app.test_client()
    test_client.set_cookie("camera_id", "abc123")
    response = test_client.get("/")
    assert response.status_code == 200

    with flask_app.app_context():
        from app.models import CameraSession

        camera = db.session.get(CameraSession, "abc123")
        assert camera.photo_count == 5  # pre-existing data preserved
        assert camera.created_ip == "1.2.3.4"  # pre-existing data preserved
        assert camera.last_photo_at is None  # new column, backfilled as NULL
