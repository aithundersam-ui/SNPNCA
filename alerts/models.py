from datetime import timedelta
from urllib.parse import quote

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone, translation
from django.utils.translation import gettext_lazy as _

from core.models import BilingualMixin


def default_show_until():
    return timezone.now() + timedelta(days=7)


class Alert(BilingualMixin, models.Model):
    """Urgent news: shown as a banner to members, emailed, and shared on WhatsApp by an admin."""

    title_fr = models.CharField(_("title (French)"), max_length=200, blank=True)
    title_en = models.CharField(_("title (English)"), max_length=200, blank=True)
    body_fr = models.TextField(_("message (French)"), blank=True)
    body_en = models.TextField(_("message (English)"), blank=True)
    show_until = models.DateTimeField(_("show the banner until"), default=default_show_until)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    emailed_at = models.DateTimeField(null=True, blank=True)
    emails_sent = models.PositiveIntegerField(default=0)
    emails_failed = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-created_at", "-pk"]

    def __str__(self):
        return self.title_fr or self.title_en

    @classmethod
    def active(cls):
        return cls.objects.filter(show_until__gt=timezone.now())

    def url(self, language):
        with translation.override(language):
            return settings.SITE_URL + reverse("alerts:detail", args=[self.pk])

    def text_in(self, language):
        """Title and message in `language`, falling back to the other language."""
        with translation.override(language):
            return self.localized("title"), self.localized("body")

    def whatsapp_text(self, language):
        title, body = self.text_in(language)
        return f"*SNPNCA · {title}*\n\n{body}\n\n{self.url(language)}"

    def whatsapp_share_link(self, language="fr"):
        """Opens WhatsApp with the message ready; the admin picks the group, community or broadcast list."""
        return "https://wa.me/?text=" + quote(self.whatsapp_text(language))

    def whatsapp_link_for(self, user):
        if not user.whatsapp_number:
            return ""
        language = user.preferred_language if user.preferred_language in ("fr", "en") else "fr"
        return f"{user.whatsapp_link}?text={quote(self.whatsapp_text(language))}"
