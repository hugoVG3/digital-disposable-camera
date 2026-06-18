"""
Everything to do with photo *files* on disk lives here, kept separate from
the routes so app/routes/camera.py just orchestrates (validate -> save ->
update DB) without worrying about filesystem/image details.

Each camera (anonymous "roll") gets its own folder:

    data/photos/<camera_id>/shot_01.jpg
    data/photos/<camera_id>/shot_02.jpg
    ...

Quality philosophy: keep the camera's original bytes whenever possible.
A real re-encode (even at high quality) throws away some detail and costs
CPU time on a Pi Zero 2W serving ~70 guests, so the default path is a true
byte-level pass-through -- the only edit made is stripping GPS data out of
the EXIF block directly (via piexif), which never touches the compressed
pixel data at all. Re-encoding only happens for the rare non-JPEG input
(e.g. a PNG snapshot from the live in-browser viewfoder).
"""

import io
import os
import shutil
import zipfile

import piexif
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


def _strip_gps_lossless(raw_bytes):
    """
    Remove GPS tags from a JPEG's EXIF block by editing the metadata
    segment directly -- the compressed image data is never touched, so
    this is 100% lossless. Falls back to returning the original bytes
    untouched if there's no GPS data (the common case) or no EXIF at all.
    """
    exif_dict = piexif.load(raw_bytes)
    if not exif_dict.get("GPS"):
        return raw_bytes

    exif_dict["GPS"] = {}
    new_exif_bytes = piexif.dump(exif_dict)
    out = io.BytesIO()
    piexif.insert(new_exif_bytes, raw_bytes, out)
    return out.getvalue()


def save_photo(file_storage, photos_dir, camera_id, shot_number, max_dimension, jpeg_quality):
    """
    Save an uploaded photo for `camera_id` as the next sequential shot.
    Returns the filename that was written, or raises ValueError on a
    file that isn't a readable image.
    """
    roll_dir = get_roll_dir(photos_dir, camera_id)
    filename = f"shot_{shot_number:02d}.jpg"
    destination = os.path.join(roll_dir, filename)

    raw_bytes = file_storage.read()
    if not raw_bytes:
        raise ValueError("No photo data was received.")

    try:
        with Image.open(io.BytesIO(raw_bytes)) as probe:
            probe.verify()
            image_format = probe.format
    except (UnidentifiedImageError, OSError, ValueError):
        raise ValueError("That file doesn't look like a photo.")

    if image_format == "JPEG":
        try:
            cleaned_bytes = _strip_gps_lossless(raw_bytes)
            with open(destination, "wb") as f:
                f.write(cleaned_bytes)
            return filename
        except Exception:
            # Whatever went wrong with the lossless path, don't risk
            # writing a file that might still contain GPS data -- fall
            # through to the safe re-encode below instead, which is
            # guaranteed to strip all metadata.
            pass

    # Fallback: decode + re-encode. Only reached for non-JPEG input (e.g.
    # a PNG from the live-viewfinder snapshot) or if the lossless path
    # above failed for some reason. Browsers honor EXIF orientation when
    # *displaying* an <img>, but we're dropping EXIF entirely here, so we
    # bake the correct orientation into the pixels first.
    image = Image.open(io.BytesIO(raw_bytes))
    image = ImageOps.exif_transpose(image)
    if image.mode not in ("RGB", "L"):
        image = image.convert("RGB")
    if max(image.size) > max_dimension:
        image.thumbnail((max_dimension, max_dimension), Image.LANCZOS)
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


def build_roll_zip(photos_dir, camera_id):
    """In-memory zip of one roll's photos, for the admin 'download roll' button."""
    roll_dir = get_roll_dir(photos_dir, camera_id, create=False)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as zf:
        if os.path.isdir(roll_dir):
            for name in sorted(os.listdir(roll_dir)):
                path = os.path.join(roll_dir, name)
                if os.path.isfile(path):
                    zf.write(path, arcname=name)
    buf.seek(0)
    return buf


def build_all_rolls_zip(photos_dir):
    """In-memory zip of every roll, namespaced by camera_id so filenames
    don't collide. Used by the admin 'download everything' button."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as zf:
        for camera_id in list_rolls(photos_dir):
            roll_dir = get_roll_dir(photos_dir, camera_id, create=False)
            for name in sorted(os.listdir(roll_dir)):
                path = os.path.join(roll_dir, name)
                if os.path.isfile(path):
                    zf.write(path, arcname=f"{camera_id}/{name}")
    buf.seek(0)
    return buf
