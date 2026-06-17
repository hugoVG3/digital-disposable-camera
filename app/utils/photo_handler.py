"""
Everything to do with photo *files* on disk lives here, kept separate from
the routes so app/routes/camera.py just orchestrates (validate -> save ->
update DB) without worrying about filesystem/image details.

Each camera (anonymous "roll") gets its own folder:

    data/photos/<camera_id>/shot_01.jpg
    data/photos/<camera_id>/shot_02.jpg
    ...

Photos are always re-encoded as JPEG and downsized, both to keep the Pi's
SD card happy and because a disposable camera was never high-resolution
in the first place.
"""

import os
import shutil

from PIL import Image, ImageOps, UnidentifiedImageError
from werkzeug.utils import secure_filename


def allowed_file(filename, allowed_extensions):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in allowed_extensions
    )


def get_roll_dir(photos_dir, camera_id, create=True):
    roll_dir = os.path.join(photos_dir, secure_filename(camera_id))
    if create:
        os.makedirs(roll_dir, exist_ok=True)
    return roll_dir


def save_photo(file_storage, photos_dir, camera_id, shot_number, max_dimension, jpeg_quality):
    """
    Save an uploaded photo for `camera_id` as the next sequential shot.
    Returns the filename that was written, or raises ValueError on a
    file that isn't a readable image.
    """
    roll_dir = get_roll_dir(photos_dir, camera_id)

    try:
        image = Image.open(file_storage.stream)
        image.load()
    except UnidentifiedImageError:
        raise ValueError("That file doesn't look like a photo.")

    # Respect the phone's EXIF orientation, then strip EXIF (and any other
    # metadata) before saving -- keeps files small and avoids leaking
    # location/device data from guest phones.
    image = ImageOps.exif_transpose(image)
    if image.mode not in ("RGB", "L"):
        image = image.convert("RGB")

    image.thumbnail((max_dimension, max_dimension), Image.LANCZOS)

    filename = f"shot_{shot_number:02d}.jpg"
    destination = os.path.join(roll_dir, filename)
    image.save(destination, format="JPEG", quality=jpeg_quality, optimize=True)

    return filename


def list_rolls(photos_dir):
    """Return camera_ids that have a folder on disk (used by the admin view
    as a cross-check alongside the database)."""
    if not os.path.isdir(photos_dir):
        return []
    return sorted(
        name for name in os.listdir(photos_dir)
        if os.path.isdir(os.path.join(photos_dir, name))
    )


def list_photos(photos_dir, camera_id):
    roll_dir = get_roll_dir(photos_dir, camera_id, create=False)
    if not os.path.isdir(roll_dir):
        return []
    return sorted(
        name for name in os.listdir(roll_dir)
        if os.path.isfile(os.path.join(roll_dir, name))
    )


def photo_path(photos_dir, camera_id, filename):
    return os.path.join(get_roll_dir(photos_dir, camera_id, create=False), secure_filename(filename))


def delete_photo(photos_dir, camera_id, filename):
    path = photo_path(photos_dir, camera_id, filename)
    if os.path.isfile(path):
        os.remove(path)
        return True
    return False


def delete_roll(photos_dir, camera_id):
    roll_dir = get_roll_dir(photos_dir, camera_id, create=False)
    if os.path.isdir(roll_dir):
        shutil.rmtree(roll_dir)
        return True
    return False
