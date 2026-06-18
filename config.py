"""
Configuration for the Disposable Camera app.

Everything here is read from environment variables (with sensible
defaults for local development) so that on the Raspberry Pi you only
need to set a couple of values in a `.env` file -- see docs/raspberry-pi-setup.md.
"""

import os
from werkzeug.security import generate_password_hash

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    # --- Core Flask ---
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")

    # --- Database ---
    DATA_DIR = os.path.join(BASE_DIR, "data")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", f"sqlite:///{os.path.join(DATA_DIR, 'app.db')}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # --- Photo storage ---
    # Defaults to a folder on the SD card, but can be pointed at a mounted
    # USB drive instead (see docs/raspberry-pi-setup.md, Part H2) so photos
    # can be physically unplugged and read on any computer.
    PHOTOS_DIR = os.environ.get("PHOTOS_DIR", os.path.join(DATA_DIR, "photos"))
    MAX_PHOTOS_PER_CAMERA = int(os.environ.get("MAX_PHOTOS_PER_CAMERA", 24))
    ALLOWED_PHOTO_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}

    # Quality philosophy: prefer the camera's original bytes untouched
    # (true lossless) whenever possible -- see app/utils/photo_handler.py.
    # These two settings are only used on the rare fallback path where a
    # re-encode is unavoidable (non-JPEG input, or an EXIF orientation that
    # needs baking in). 95 is visually indistinguishable from the source
    # for a photograph while staying far smaller/faster than PNG.
    MAX_PHOTO_DIMENSION = int(os.environ.get("MAX_PHOTO_DIMENSION", 4096))
    JPEG_QUALITY = int(os.environ.get("JPEG_QUALITY", 95))

    # Modern phone cameras can produce large JPEGs (10-25MB on high-end
    # sensors). 25MB comfortably covers that without leaving the upload
    # endpoint wide open to abuse.
    MAX_CONTENT_LENGTH = int(os.environ.get("MAX_CONTENT_LENGTH", 25 * 1024 * 1024))

    # Minimum seconds between shots from the same camera -- both an
    # authentic "winding the film" beat and a built-in throttle so the
    # Pi never has to handle a burst of large uploads from one phone at
    # once, even with ~70 guests using it intermittently.
    COOLDOWN_SECONDS = float(os.environ.get("COOLDOWN_SECONDS", 3))

    # --- "Camera" identity cookie (anonymous, no login for guests) ---
    CAMERA_COOKIE_NAME = "camera_id"
    CAMERA_COOKIE_MAX_AGE = 60 * 60 * 24 * 365 * 5  # 5 years, outlives any event

    # --- Admin (the only real "login" in this app) ---
    # Set ADMIN_PASSWORD in your environment / .env file on the Pi.
    # Never store the plaintext password anywhere -- only the hash lives in memory.
    ADMIN_PASSWORD_HASH = generate_password_hash(
        os.environ.get("ADMIN_PASSWORD", "changeme")
    )


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "0") == "1"


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"


config_by_name = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
}
