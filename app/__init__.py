import os

from flask import Flask, g, request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from config import config_by_name
from app.models import db, CameraSession

limiter = Limiter(key_func=get_remote_address)


def create_app(config_name=None):
    config_name = config_name or os.environ.get("FLASK_ENV", "development")
    app = Flask(__name__)
    app.config.from_object(config_by_name[config_name])

    # Make sure the folders that hold the db and photos actually exist
    # before anything tries to write to them.
    os.makedirs(app.config["DATA_DIR"], exist_ok=True)
    os.makedirs(app.config["PHOTOS_DIR"], exist_ok=True)

    db.init_app(app)
    limiter.init_app(app)

    with app.app_context():
        db.create_all()

    from app.routes.camera import camera_bp
    from app.routes.auth import auth_bp

    app.register_blueprint(camera_bp)
    app.register_blueprint(auth_bp)

    register_camera_identity_hooks(app)

    return app


def register_camera_identity_hooks(app):
    """
    Every visitor to a guest-facing page (anything outside /admin and
    /static) is anonymously identified by a long-lived cookie -- no login,
    no QR code. The first time a browser shows up without that cookie, we
    create a new CameraSession (a fresh roll of MAX_PHOTOS_PER_CAMERA shots)
    and hand the cookie back in the response.

    We still record the request IP on the session as metadata (see
    CameraSession.created_ip / last_ip) since the app is reachable from the
    WAN -- but the IP is never used to identify *which* camera a guest owns,
    only for audit/abuse visibility, since many guests can share one public
    IP behind the same router.
    """

    @app.before_request
    def load_camera_session():
        if request.path.startswith("/admin") or request.path.startswith("/static"):
            g.camera = None
            return

        cookie_name = app.config["CAMERA_COOKIE_NAME"]
        camera_id = request.cookies.get(cookie_name)
        camera = db.session.get(CameraSession, camera_id) if camera_id else None

        if camera is None:
            camera = CameraSession(created_ip=request.remote_addr)
            db.session.add(camera)
            db.session.commit()
            g.new_camera_id = camera.id

        camera.last_ip = request.remote_addr
        db.session.commit()
        g.camera = camera

    @app.after_request
    def set_camera_cookie(response):
        new_id = getattr(g, "new_camera_id", None)
        if new_id:
            response.set_cookie(
                app.config["CAMERA_COOKIE_NAME"],
                new_id,
                max_age=app.config["CAMERA_COOKIE_MAX_AGE"],
                httponly=True,
                samesite="Lax",
            )
        return response
