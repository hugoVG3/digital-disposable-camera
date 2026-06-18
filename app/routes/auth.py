"""
The only real "login" in this app belongs to the admin (you) -- guests
never authenticate. This blueprint covers:
  - /admin/login, /admin/logout
  - the password-gated gallery: list rolls, "develop" (reveal) one roll's
    photos all at once, serve the actual image bytes, and delete photos
    or whole rolls.

Per the project's planned structure there's only one gallery template
(app/templates/gallery.html); the login form and the roll views are all
rendered through it, switched by the `view` they're given.
"""

from functools import wraps

from flask import (
    Blueprint,
    abort,
    current_app,
    redirect,
    render_template,
    request,
    send_file,
    send_from_directory,
    session,
    url_for,
)
from werkzeug.security import check_password_hash

from app import limiter
from app.models import CameraSession, db
from app.utils import photo_handler

auth_bp = Blueprint("auth", __name__, url_prefix="/admin")


def admin_required(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if not session.get("is_admin"):
            return redirect(url_for("auth.login"))
        return view_func(*args, **kwargs)

    return wrapped


@auth_bp.route("/login", methods=["GET", "POST"])
@limiter.limit("10 per minute")
def login():
    if session.get("is_admin"):
        return redirect(url_for("auth.gallery"))

    error = None
    if request.method == "POST":
        password = request.form.get("password", "")
        if check_password_hash(current_app.config["ADMIN_PASSWORD_HASH"], password):
            session["is_admin"] = True
            return redirect(url_for("auth.gallery"))
        error = "Incorrect password."

    return render_template("gallery.html", view="login", error=error)


@auth_bp.route("/logout")
def logout():
    session.pop("is_admin", None)
    return redirect(url_for("auth.login"))


@auth_bp.route("/gallery")
@admin_required
def gallery():
    max_photos = current_app.config["MAX_PHOTOS_PER_CAMERA"]
    rolls = (
        CameraSession.query.order_by(CameraSession.created_at.desc()).all()
    )
    return render_template("gallery.html", view="list", rolls=rolls, max_photos=max_photos)


@auth_bp.route("/gallery/download-all")
@admin_required
def download_all_rolls():
    buf = photo_handler.build_all_rolls_zip(current_app.config["PHOTOS_DIR"])
    return send_file(
        buf,
        mimetype="application/zip",
        as_attachment=True,
        download_name="all-rolls.zip",
    )


@auth_bp.route("/gallery/<camera_id>")
@admin_required
def view_roll(camera_id):
    camera = CameraSession.query.get_or_404(camera_id)
    filenames = photo_handler.list_photos(current_app.config["PHOTOS_DIR"], camera_id)
    return render_template("gallery.html", view="detail", camera=camera, filenames=filenames)


@auth_bp.route("/gallery/<camera_id>/download")
@admin_required
def download_roll(camera_id):
    buf = photo_handler.build_roll_zip(current_app.config["PHOTOS_DIR"], camera_id)
    return send_file(
        buf,
        mimetype="application/zip",
        as_attachment=True,
        download_name=f"roll-{camera_id[:8]}.zip",
    )


@auth_bp.route("/photo/<camera_id>/<filename>")
@admin_required
def serve_photo(camera_id, filename):
    roll_dir = photo_handler.get_roll_dir(current_app.config["PHOTOS_DIR"], camera_id, create=False)
    return send_from_directory(roll_dir, filename)


@auth_bp.route("/gallery/<camera_id>/photo/<filename>/delete", methods=["POST"])
@admin_required
def delete_photo(camera_id, filename):
    from app.models import Photo

    photo_handler.delete_photo(current_app.config["PHOTOS_DIR"], camera_id, filename)
    Photo.query.filter_by(camera_id=camera_id, filename=filename).delete()
    db.session.commit()
    return redirect(url_for("auth.view_roll", camera_id=camera_id))


@auth_bp.route("/gallery/<camera_id>/delete", methods=["POST"])
@admin_required
def delete_roll(camera_id):
    from app.models import Photo

    photo_handler.delete_roll(current_app.config["PHOTOS_DIR"], camera_id)
    Photo.query.filter_by(camera_id=camera_id).delete()
    CameraSession.query.filter_by(id=camera_id).delete()
    db.session.commit()
    return redirect(url_for("auth.gallery"))
