"""
The shared SQLAlchemy instance lives here (rather than in app/__init__.py)
so that both app/__init__.py and app/models/*.py can import it without a
circular import.
"""

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

# Import models so they register with SQLAlchemy's metadata as soon as
# someone imports `app.models`.
from app.models.user import CameraSession, Photo  # noqa: E402,F401
