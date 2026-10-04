import io
import tempfile

import pymupdf
from django.test import override_settings

from accounts.models import Role, User

TEMP_MEDIA = tempfile.mkdtemp(prefix="snpnca-test-media-")


def media_settings():
    return override_settings(MEDIA_ROOT=TEMP_MEDIA)


def make_user(email, role=Role.USER, password="Correct-horse-42", **extra):
    return User.objects.create_user(email=email, full_name=email.split("@")[0].title(), password=password, role=role, **extra)


def make_pdf(pages, scanned_pages=()):
    """Build a PDF in memory. Pages listed in `scanned_pages` (0-based) are
    rendered as images only, with no text layer, to exercise OCR."""
    doc = pymupdf.open()
    for i, text in enumerate(pages):
        page = doc.new_page()
        if i in scanned_pages:
            tmp = pymupdf.open()
            tp = tmp.new_page()
            tp.insert_textbox(pymupdf.Rect(50, 50, 550, 800), text, fontsize=16)
            pix = tp.get_pixmap(dpi=200)
            page.insert_image(page.rect, stream=pix.tobytes("png"))
        else:
            page.insert_textbox(pymupdf.Rect(50, 50, 550, 800), text, fontsize=11)
    data = doc.tobytes()
    return io.BytesIO(data)
