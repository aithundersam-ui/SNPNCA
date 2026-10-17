import uuid

from django.db import models
from django.utils.translation import gettext_lazy as _

from core.models import BilingualMixin


def photo_path(instance, filename):
    return f"destinations/{uuid.uuid4().hex}.jpg"


class Destination(BilingualMixin, models.Model):
    """A city the airline flies to, shown to members with its top activities."""

    name_fr = models.CharField(_("name (French)"), max_length=100)
    name_en = models.CharField(_("name (English)"), max_length=100, blank=True)
    name_ar = models.CharField(_("name (Arabic)"), max_length=100, blank=True)
    photo = models.ImageField(
        _("photo"), upload_to=photo_path, blank=True,
        help_text=_("A landscape photo works best. It is resized and cropped automatically."),
    )
    position = models.PositiveSmallIntegerField(_("order"), default=0, help_text=_("Lower numbers come first."))
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["position", "name_fr"]

    def __str__(self):
        return self.name_fr or self.name_en

    def delete(self, *args, **kwargs):
        storage, name = self.photo.storage, self.photo.name
        super().delete(*args, **kwargs)
        if name:
            storage.delete(name)


class Activity(BilingualMixin, models.Model):
    destination = models.ForeignKey(Destination, on_delete=models.CASCADE, related_name="activities")
    text_fr = models.CharField(max_length=200, blank=True)
    text_en = models.CharField(max_length=200, blank=True)
    text_ar = models.CharField(max_length=200, blank=True)
    position = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["position", "pk"]

    def __str__(self):
        return self.text_fr or self.text_en
