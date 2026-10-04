from django.conf import settings
from django.db import models
from django.utils.translation import get_language
from django.utils.translation import gettext_lazy as _


class BilingualMixin:
    """`obj.localized("title")` returns title_fr or title_en for the active language,
    falling back to the other language when the preferred one is empty."""

    def localized(self, field):
        lang = (get_language() or "fr")[:2]
        other = "en" if lang == "fr" else "fr"
        return getattr(self, f"{field}_{lang}", "") or getattr(self, f"{field}_{other}", "")


class SiteContent(BilingualMixin, models.Model):
    """Single row holding the editable text of the public home page."""

    description_fr = models.TextField(_("organisation description (French)"), blank=True)
    description_en = models.TextField(_("organisation description (English)"), blank=True)
    mission_fr = models.TextField(_("our mission (French)"), blank=True)
    mission_en = models.TextField(_("our mission (English)"), blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    @classmethod
    def load(cls):
        obj, _created = cls.objects.get_or_create(pk=1)
        return obj

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)


class ContactMessage(models.Model):
    class Status(models.TextChoices):
        NEW = "new", _("New")
        REPLIED = "replied", _("Replied")

    full_name = models.CharField(_("full name"), max_length=150)
    email = models.EmailField(_("email"))
    phone = models.CharField(_("phone number"), max_length=30)
    message = models.TextField(_("message"), max_length=5000)
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
