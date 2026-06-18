"""
Guest-facing routes only: showing the camera/shutter page and accepting a
shot. No login, no gallery here -- a real disposable camera doesn't let
the person holding it review what they've shot, so neither does this.
"""

from flask import Blueprint, current_app, g, jsonify, render_template, request

from app import limiter
from app.models import db
from app.utils import photo_handler

camera_bp = Blueprint("camera", __name__)


@camera_bp.route("/")
def index():
    camera = g.camera
    max_photos = current_app.config["MAX_PHOTOS_PER_CAMERA"]
    cooldown_seconds = current_app.config["COOLDOWN_SECONDS"]
    return render_template(
        "camera.html",
        remaining=camera.remaining(max_photos),
        photo_count=camera.photo_count,
        max_photos=max_photos,
        finished=camera.is_finished,
        cooldown_seconds=cooldown_seconds,
        seconds_until_ready=camera.seconds_until_ready(cooldown_seconds),
    )


@camera_bp.route("/capture", methods=["POST"])
@limiter.limit("30 per minute")
def capture():
    camera = g.camera
    max_photos = current_app.config["MAX_PHOTOS_PER_CAMERA"]
    cooldown_seconds = current_app.config["COOLDOWN_SECONDS"]

    if camera.photo_count >= max_photos:
        return jsonify(success=False, error="This roll is finished. No shots left.", finished=True), 409

    wait = camera.seconds_until_ready(cooldown_seconds)
    if wait > 0:
        return jsonify(success=False, error="Still winding the film...", cooldown_remaining=wait), 429

    file_storage = request.files.get("photo")
    if file_storage is None or file_storage.filename == "":
        return jsonify(success=False, error="No photo was received."), 400

    if not photo_handler.allowed_file(file_storage.filename, current_app.config["ALLOWED_PHOTO_EXTENSIONS"]):
        return jsonify(success=False, error="Unsupported file type."), 400

    try:
        filename = photo_handler.save_photo(
            file_storage,
            current_app.config["PHOTOS_DIR"],
            camera.id,
            shot_number=camera.photo_count + 1,
            max_dimension=current_app.config["MAX_PHOTO_DIMENSION"],
            jpeg_quality=current_app.config["JPEG_QUALITY"],
        )
    except ValueError as exc:
        return jsonify(success=False, error=str(exc)), 400

    from app.models import Photo

    photo = Photo(camera_id=camera.id, filename=filename, ip_address=request.remote_addr)
    db.session.add(photo)
    camera.record_photo_taken(max_photos)
    db.session.commit()

    return jsonify(
        success=True,
        remaining=camera.remaining(max_photos),
        photo_count=camera.photo_count,
        max_photos=max_photos,
        finished=camera.is_finished,
        cooldown_seconds=cooldown_seconds,
    )
