import uuid

from django.conf import settings
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVectorField
from django.db import models
from django.utils.translation import gettext_lazy as _


def document_path(instance, filename):
    return f"documents/{uuid.uuid4().hex}.pdf"


class Document(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", _("Waiting")
        PROCESSING = "processing", _("Processing")
        READY = "ready", _("Ready")
        FAILED = "failed", _("Failed")

    title = models.CharField(_("title"), max_length=255)
    file = models.FileField(upload_to=document_path)
    original_filename = models.CharField(max_length=255)
    size_bytes = models.PositiveBigIntegerField(default=0)
    page_count = models.PositiveIntegerField(default=0)
    ocr_page_count = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING, db_index=True)
    error = models.TextField(blank=True)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    processing_started_at = models.DateTimeField(null=True, blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["title"]

    def __str__(self):
        return self.title

    def delete(self, *args, **kwargs):
        # Chunks (extracted text + search index) go with the row via CASCADE;
        # the file itself is removed from private storage here.
        storage, name = self.file.storage, self.file.name
        result = super().delete(*args, **kwargs)
        if name:
            storage.delete(name)
        return result


class Chunk(models.Model):
    """A passage of extracted text plus its full-text search vectors.

    Three vectors are kept so retrieval works across languages: French and
    English stemmed (accent-insensitive), and a language-neutral one used for
    Arabic text, names, acronyms and numbers.
    """

    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="chunks")
    page = models.PositiveIntegerField()
    index = models.PositiveIntegerField()
    text = models.TextField()
    vec_fr = SearchVectorField(null=True)
    vec_en = SearchVectorField(null=True)
    vec_simple = SearchVectorField(null=True)

    class Meta:
        ordering = ["document_id", "index"]
        indexes = [
            GinIndex(fields=["vec_fr"], name="qa_chunk_vec_fr"),
            GinIndex(fields=["vec_en"], name="qa_chunk_vec_en"),
            GinIndex(fields=["vec_simple"], name="qa_chunk_vec_simple"),
        ]


class QAMessage(models.Model):
    class Role(models.TextChoices):
        USER = "user", "user"
        ASSISTANT = "assistant", "assistant"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="qa_messages")
    role = models.CharField(max_length=10, choices=Role.choices)
    content = models.TextField()
    # [{"document_id": 1, "title": "...", "page": 3}]
    citations = models.JSONField(default=list, blank=True)
    answered = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "pk"]
