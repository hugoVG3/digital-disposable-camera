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
    # Resize photos down to this max edge (px) before saving -- keeps storage
    # and CPU load low on a Pi Zero 2W. Disposable cameras aren't high-res anyway.
    MAX_PHOTO_DIMENSION = int(os.environ.get("MAX_PHOTO_DIMENSION", 1600))
    JPEG_QUALITY = int(os.environ.get("JPEG_QUALITY", 85))

    # Reject absurdly large uploads outright (bytes). 15 MB is generous for a phone photo.
    MAX_CONTENT_LENGTH = int(os.environ.get("MAX_CONTENT_LENGTH", 15 * 1024 * 1024))

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
