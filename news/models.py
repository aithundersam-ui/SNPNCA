import re
import uuid
from pathlib import Path

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from core.models import BilingualMixin

YOUTUBE_RE = re.compile(r"^https?://(?:www\.|m\.)?(?:youtube\.com/(?:watch\?(?:.*&)?v=|embed/|shorts/)|youtu\.be/)([A-Za-z0-9_-]{11})")
VIMEO_RE = re.compile(r"^https?://(?:www\.|player\.)?vimeo\.com/(?:video/)?(\d{5,12})")


def embed_url(url):
    """Return a safe embed URL for a YouTube or Vimeo link, or None if it isn't one."""
    url = (url or "").strip()
    m = YOUTUBE_RE.match(url)
    if m:
        return f"https://www.youtube-nocookie.com/embed/{m.group(1)}"
    m = VIMEO_RE.match(url)
    if m:
        return f"https://player.vimeo.com/video/{m.group(1)}"
    return None


def image_path(instance, filename):
    ext = Path(filename).suffix.lower()
    return f"news/{timezone.now():%Y/%m}/{uuid.uuid4().hex}{ext}"


class Article(BilingualMixin, models.Model):
    title_fr = models.CharField(_("title (French)"), max_length=200, blank=True)
    title_en = models.CharField(_("title (English)"), max_length=200, blank=True)
    body_fr = models.TextField(_("text (French)"), blank=True)
    body_en = models.TextField(_("text (English)"), blank=True)
    published_at = models.DateTimeField(_("publication date"), default=timezone.now, db_index=True)
    is_published = models.BooleanField(_("published"), default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-published_at", "-pk"]

    def __str__(self):
        return self.title_fr or self.title_en


class ArticleImage(models.Model):
    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to=image_path)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["position", "pk"]

    def delete(self, *args, **kwargs):
        storage, name = self.image.storage, self.image.name
        super().delete(*args, **kwargs)
        if name:
            storage.delete(name)


class ArticleVideo(models.Model):
    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name="videos")
    url = models.URLField(_("YouTube or Vimeo link"))
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["position", "pk"]

    @property
    def embed(self):
        return embed_url(self.url)
