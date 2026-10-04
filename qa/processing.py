"""PDF text extraction (direct text layer, OCR fallback), chunking and indexing."""

import logging
import re

import pymupdf
import pytesseract
from django.conf import settings
from django.db import connection, transaction
from django.utils import timezone
from PIL import Image

from .models import Chunk, Document

logger = logging.getLogger(__name__)

# A page with less text than this is treated as scanned and sent to OCR.
MIN_TEXT_CHARS = 40
CHUNK_CHARS = 1200
CHUNK_OVERLAP = 200
OCR_DPI = 300


class InvalidPdf(Exception):
    pass


def validate_pdf_bytes(head: bytes, data_stream) -> int:
    """Server-side file type check. Returns the page count or raises InvalidPdf."""
    if not head.startswith(b"%PDF-"):
        raise InvalidPdf("not a PDF")
    try:
        data_stream.seek(0)
        with pymupdf.open(stream=data_stream.read(), filetype="pdf") as pdf:
            if pdf.needs_pass:
                raise InvalidPdf("password protected")
            if pdf.page_count == 0:
                raise InvalidPdf("no pages")
            return pdf.page_count
    except InvalidPdf:
        raise
    except Exception as exc:
        raise InvalidPdf("unreadable") from exc
    finally:
        data_stream.seek(0)


def normalize(text: str) -> str:
    text = text.replace("­", "")  # soft hyphens
    text = re.sub(r"-\n(?=\w)", "", text)  # words hyphenated across lines
    text = re.sub(r"[ \t\f\v]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def ocr_page(page) -> str:
    pix = page.get_pixmap(dpi=OCR_DPI)
    image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    return pytesseract.image_to_string(image, lang=settings.OCR_LANGUAGES)


def extract_pages(path):
    """Yield (page_number, text, used_ocr) for every page."""
    with pymupdf.open(path) as pdf:
        for number, page in enumerate(pdf, start=1):
            text = normalize(page.get_text("text"))
            used_ocr = False
            if len(text) < MIN_TEXT_CHARS:
                ocr_text = normalize(ocr_page(page))
                if len(ocr_text) > len(text):
                    text, used_ocr = ocr_text, True
            yield number, text, used_ocr


def split_text(text, size=CHUNK_CHARS, overlap=CHUNK_OVERLAP):
    """Split into overlapping windows, preferring paragraph or sentence breaks."""
    if len(text) <= size:
        return [text] if text else []
    chunks, start = [], 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            window = text[start:end]
            cut = max(window.rfind("\n\n"), window.rfind(". "), window.rfind("\n"))
            if cut > size // 2:
                end = start + cut + 1
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
        # Start the next window on a word boundary.
        while start < len(text) and not text[start - 1].isspace():
            start += 1
    return chunks


def index_document(document):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE qa_chunk SET
              vec_fr = to_tsvector('snpnca_fr', text),
              vec_en = to_tsvector('snpnca_en', text),
              vec_simple = to_tsvector('snpnca_simple', text)
            WHERE document_id = %s
            """,
            [document.pk],
        )


def process_document(document: Document):
    path = document.file.path
    chunks, ocr_pages, pages = [], 0, 0
    for page_number, text, used_ocr in extract_pages(path):
        pages += 1
        ocr_pages += int(used_ocr)
        for piece in split_text(text):
            chunks.append(Chunk(document=document, page=page_number, index=len(chunks), text=piece))

    with transaction.atomic():
        Chunk.objects.filter(document=document).delete()
        Chunk.objects.bulk_create(chunks, batch_size=500)
        index_document(document)
        document.page_count = pages
        document.ocr_page_count = ocr_pages
        document.processed_at = timezone.now()
        if chunks:
            document.status = Document.Status.READY
            document.error = ""
        else:
            document.status = Document.Status.FAILED
            document.error = "No text could be extracted from this PDF."
        document.save()
    return len(chunks)


def claim_next_document():
    """Atomically pick one waiting document, so several workers never collide."""
    stale = timezone.now() - timezone.timedelta(hours=1)
    Document.objects.filter(status=Document.Status.PROCESSING, processing_started_at__lt=stale).update(status=Document.Status.PENDING)
    with transaction.atomic():
        doc = Document.objects.select_for_update(skip_locked=True).filter(status=Document.Status.PENDING).order_by("created_at").first()
        if doc is None:
            return None
        doc.status = Document.Status.PROCESSING
        doc.processing_started_at = timezone.now()
        doc.save(update_fields=["status", "processing_started_at"])
        return doc


def run_once():
    doc = claim_next_document()
    if doc is None:
        return False
    try:
        count = process_document(doc)
        logger.info("Processed %s: %s chunks", doc, count)
    except Exception as exc:
        logger.exception("Failed to process %s", doc)
        Document.objects.filter(pk=doc.pk).update(status=Document.Status.FAILED, error=str(exc)[:1000])
    return True
