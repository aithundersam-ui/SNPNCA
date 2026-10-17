import uuid
from pathlib import Path

from django.conf import settings
from django.db import models
from django.utils.translation import get_language
from django.utils.translation import gettext_lazy as _


class BilingualMixin:
    """`obj.localized("title")` returns title_fr, title_en or title_ar for the active
    language. An empty field falls back to French, then English (Arabic is optional)."""

    def localized(self, field):
        lang = (get_language() or "fr")[:2]
        for code in dict.fromkeys([lang, "fr", "en"]):
            value = getattr(self, f"{field}_{code}", "")
            if value:
                return value
        return ""


def hero_image_path(instance, filename):
    return f"site/hero-{uuid.uuid4().hex}{Path(filename).suffix.lower()}"


class SiteContent(BilingualMixin, models.Model):
    """Single row holding the editable text of the public home page."""

    description_fr = models.TextField(_("organisation description (French)"), blank=True)
    description_en = models.TextField(_("organisation description (English)"), blank=True)
    mission_fr = models.TextField(_("our mission (French)"), blank=True)
    mission_en = models.TextField(_("our mission (English)"), blank=True)
    description_ar = models.TextField(_("organisation description (Arabic)"), blank=True)
    mission_ar = models.TextField(_("our mission (Arabic)"), blank=True)
    hero_image = models.ImageField(
        _("home page background photo"),
        upload_to=hero_image_path,
        blank=True,
        help_text=_("Shown behind the title at the top of the home page. A wide photo (at least 1600 pixels across) works best. Leave empty to use the default background."),
    )
    signup_form_url = models.URLField(
        _("membership sign-up form (Google Form link)"),
        blank=True,
        help_text=_("Visitors who aren't logged in see a pop-up on the home page that opens this form. Leave empty to hide the pop-up."),
    )
    facebook_url = models.URLField(_("Facebook page link"), blank=True)
    instagram_url = models.URLField(_("Instagram page link"), blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    @classmethod
    def load(cls):
        obj, _created = cls.objects.get_or_create(pk=1)
        return obj

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)


class KeyFigure(BilingualMixin, models.Model):
    """A big number shown on the home page above Our mission, e.g. 700+ affiliated cabin crew."""

    class Icon(models.TextChoices):
        CREW = "users", _("People")
        CITY = "map-pin", _("Map pin")
        PLANE = "plane", _("Plane")
        GLOBE = "globe", _("Globe")
        CALENDAR = "calendar", _("Calendar")
        SHIELD = "shield", _("Shield")

    icon = models.CharField(_("icon"), max_length=20, choices=Icon.choices, default=Icon.CREW)
    value = models.PositiveIntegerField(_("number"))
    suffix = models.CharField(_("after the number"), max_length=3, blank=True, help_text=_("For example + or %."))
    label_fr = models.CharField(_("label (French)"), max_length=60)
    label_en = models.CharField(_("label (English)"), max_length=60, blank=True)
    label_ar = models.CharField(_("label (Arabic)"), max_length=60, blank=True)
    position = models.PositiveSmallIntegerField(_("order"), default=0)

    class Meta:
        ordering = ["position", "pk"]

    def __str__(self):
        return f"{self.value}{self.suffix} {self.label_fr}"


class ContactMessage(models.Model):
    class Status(models.TextChoices):
        NEW = "new", _("New")
        REPLIED = "replied", _("Replied")

    full_name = models.CharField(_("full name"), max_length=150)
    email = models.EmailField(_("email"))
    phone = models.CharField(_("phone number"), max_length=30)
    message = models.TextField(_("message"), max_length=5000)
    recipient = models.ForeignKey(
        "team.TeamMember", null=True, blank=True, on_delete=models.SET_NULL, related_name="+", verbose_name=_("addressed to")
    )
    language = models.CharField(max_length=2, default="fr")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.NEW, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.full_name} ({self.created_at:%Y-%m-%d})"


class ContactReply(models.Model):
    contact = models.ForeignKey(ContactMessage, on_delete=models.CASCADE, related_name="replies")
    body = models.TextField(max_length=10000)
    sent_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["sent_at"]
