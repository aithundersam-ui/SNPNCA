"""Square portrait crops centred on the face, done locally with OpenCV (no external service)."""

import io
import logging

from PIL import Image, ImageOps

logger = logging.getLogger(__name__)

OUTPUT_SIZE = 600
FACE_SHARE = 0.5  # the face's height as a share of the final square
FACE_CENTER_Y = 0.48  # where the face centre sits, from the top of the square


def find_face(image):
    """Return (x, y, w, h) of the largest face in a PIL image, or None."""
    try:
        import cv2
        import numpy as np
    except ImportError:  # OpenCV missing: fall back to a plain crop
        logger.warning("OpenCV is not installed; team photos are cropped without face detection")
        return None
    gray = np.array(image.convert("L"))
    # Detect on a reduced copy: faster and just as accurate for portraits.
    scale = min(1.0, 1000 / max(gray.shape))
    small = cv2.resize(gray, None, fx=scale, fy=scale) if scale < 1 else gray
    small = cv2.equalizeHist(small)
    cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    min_side = max(24, int(min(small.shape) * 0.06))
    faces = cascade.detectMultiScale(small, scaleFactor=1.1, minNeighbors=6, minSize=(min_side, min_side))
    if len(faces) == 0:
        return None
    x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
    return tuple(int(v / scale) for v in (x, y, w, h))


def square_box(width, height, face):
    """The square (left, top, side) to cut from a width x height image."""
    if face:
        x, y, w, h = face
        side = min(int(h / FACE_SHARE), width, height)
        cx, cy = x + w / 2, y + h / 2
        left, top = cx - side / 2, cy - side * FACE_CENTER_Y
    else:
        # No face found: keep the upper middle, where heads usually are.
        side = min(width, height)
        left, top = (width - side) / 2, 0 if height > width else (height - side) / 2
    left = int(max(0, min(left, width - side)))
    top = int(max(0, min(top, height - side)))
    return left, top, side


def crop_portrait(fileobj):
    """Read an uploaded image and return (JPEG bytes of the square crop, face_found)."""
    fileobj.seek(0)
    with Image.open(fileobj) as img:
        img = ImageOps.exif_transpose(img).convert("RGB")
    face = find_face(img)
    left, top, side = square_box(img.width, img.height, face)
    out = img.crop((left, top, left + side, top + side))
    if side > OUTPUT_SIZE:
        out = out.resize((OUTPUT_SIZE, OUTPUT_SIZE), Image.LANCZOS)
    buf = io.BytesIO()
    out.save(buf, "JPEG", quality=88, optimize=True)
    fileobj.seek(0)
    return buf.getvalue(), face is not None
