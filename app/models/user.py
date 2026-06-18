"""
There are no real user accounts in this app -- nobody signs up or logs in
to take photos. Instead, every browser/device that opens the camera page
is handed a random, anonymous "camera" identity (stored in a cookie) the
first time it visits. That identity is what this model tracks: a single
disposable camera's roll of up to MAX_PHOTOS_PER_CAMERA shots.

(The file is still named user.py to match the project's planned structure,
but conceptually this is "one disposable camera per visitor", not a user
account system.)
"""

import uuid
from datetime import datetime, timezone

from app.models import db


class CameraSession(db.Model):
    __tablename__ = "camera_sessions"

    id = db.Column(db.String(32), primary_key=True, default=lambda: uuid.uuid4().hex)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    photo_count = db.Column(db.Integer, default=0, nullable=False)
    finished_at = db.Column(db.DateTime, nullable=True)

    # The app is reachable from the WAN (port-forwarded), so we keep the
    # requester's IP for security/audit purposes -- e.g. spotting abuse of
    # the public upload endpoint. This is metadata only: it is NOT used to
    # enforce the 24-photo limit, since guests on the same Wi-Fi/NAT often
    # share one public IP and would otherwise get lumped into a single roll.
    created_ip = db.Column(db.String(45), nullable=True)  # 45 chars fits IPv6
    last_ip = db.Column(db.String(45), nullable=True)

    # When the last shot was taken -- used to enforce a short cooldown
    # between shots (see can_take_photo / seconds_until_ready below).
    last_photo_at = db.Column(db.DateTime, nullable=True)

    def remaining(self, max_photos):
        return max(0, max_photos - self.photo_count)

    def seconds_until_ready(self, cooldown_seconds):
        """How many seconds until this camera is allowed to take another
        shot ('winding the film'). 0 means it's ready now."""
        if self.last_photo_at is None or cooldown_seconds <= 0:
            return 0
        last_photo_at = self.last_photo_at
        if last_photo_at.tzinfo is None:
            last_photo_at = last_photo_at.replace(tzinfo=timezone.utc)
        elapsed = (datetime.now(timezone.utc) - last_photo_at).total_seconds()
        return max(0.0, cooldown_seconds - elapsed)

    def can_take_photo(self, max_photos, cooldown_seconds=0):
        if self.photo_count >= max_photos:
            return False
        return self.seconds_until_ready(cooldown_seconds) <= 0

    def record_photo_taken(self, max_photos):
        """Increment the shot counter and mark the roll finished if it's now full."""
        self.photo_count += 1
        self.last_photo_at = datetime.now(timezone.utc)
        if self.photo_count >= max_photos and self.finished_at is None:
            self.finished_at = datetime.now(timezone.utc)

    @property
    def is_finished(self):
        return self.finished_at is not None

    def to_dict(self, max_photos):
        return {
            "id": self.id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "photo_count": self.photo_count,
            "remaining": self.remaining(max_photos),
            "finished": self.is_finished,
        }

    def __repr__(self):
        return f"<CameraSession {self.id} ({self.photo_count} shots)>"


class Photo(db.Model):
    """One captured shot. Kept separate from CameraSession so the admin
    gallery can show per-photo detail (filename, timestamp, IP) when a
    roll is 'developed'."""

    __tablename__ = "photos"

    id = db.Column(db.Integer, primary_key=True)
    camera_id = db.Column(db.String(32), db.ForeignKey("camera_sessions.id"), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    taken_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    ip_address = db.Column(db.String(45), nullable=True)

    camera = db.relationship("CameraSession", backref=db.backref("photos", lazy="dynamic"))

    def __repr__(self):
        return f"<Photo {self.filename} camera={self.camera_id}>"
