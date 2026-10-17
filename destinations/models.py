import uuid
from urllib.parse import urlsplit

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from core.models import BilingualMixin


def photo_path(instance, filename):
    return f"destinations/{uuid.uuid4().hex}.jpg"


def validate_maps_url(value):
    """Only Google Maps links, so members are never sent somewhere unexpected."""
    parts = urlsplit(value)
    host = (parts.hostname or "").lower()
    ok = parts.scheme == "https" and (
        host in ("maps.app.goo.gl", "maps.google.com")
        or (host == "goo.gl" and parts.path.startswith("/maps"))
        or ((host == "google.com" or (host.startswith("www.google.") or host.startswith("google."))) and parts.path.startswith("/maps"))
    )
    if not ok:
        raise ValidationError(_("Paste a Google Maps link (from Share → Copy link in Google Maps)."))


class Destination(BilingualMixin, models.Model):
    """A city the airline flies to, with its own page of top activities."""

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

    def get_absolute_url(self):
        return reverse("destinations:detail", args=[self.pk])


class Activity(BilingualMixin, models.Model):
    destination = models.ForeignKey(Destination, on_delete=models.CASCADE, related_name="activities")
    title_fr = models.CharField(_("activity (French)"), max_length=200)
    title_en = models.CharField(_("activity (English)"), max_length=200, blank=True)
    title_ar = models.CharField(_("activity (Arabic)"), max_length=200, blank=True)
    description_fr = models.TextField(_("description (French)"), blank=True)
    description_en = models.TextField(_("description (English)"), blank=True)
    description_ar = models.TextField(_("description (Arabic)"), blank=True)
    photo = models.ImageField(_("photo"), upload_to=photo_path, blank=True)
    maps_url = models.URLField(_("Google Maps link"), max_length=500, blank=True, validators=[validate_maps_url])
    position = models.PositiveSmallIntegerField(_("order"), default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["position", "pk"]

    def __str__(self):
        return self.title_fr or self.title_en


@receiver(post_delete, sender=Destination)
@receiver(post_delete, sender=Activity)
def _delete_photo(sender, instance, **kwargs):
    # Also runs for activities removed together with their destination.
    if instance.photo:
        instance.photo.storage.delete(instance.photo.name)
