import uuid
from pathlib import Path

from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils.translation import pgettext_lazy

from accounts.models import normalize_whatsapp


def photo_path(instance, filename):
    return f"team/{uuid.uuid4().hex}{Path(filename).suffix.lower()}"


class TeamMember(models.Model):
    """A member of the union's bureau, shown on the public team page."""

    class Role(models.TextChoices):
        # Declared in hierarchy order; RANK below follows it.
        PRESIDENT = "president", _("President")
        SECRETARY_GENERAL = "secretary_general", _("General Secretary")
        TREASURER = "treasurer", _("Treasurer")
        MEMBER = "member", pgettext_lazy("bureau role", "Member")

    RANK = {role: i for i, role in enumerate(Role.values)}

    full_name = models.CharField(_("full name"), max_length=150)
    role = models.CharField(_("role"), max_length=20, choices=Role.choices, default=Role.MEMBER)
    rank = models.PositiveSmallIntegerField(default=3, editable=False, db_index=True)
    position = models.PositiveSmallIntegerField(
        _("order within the same role"), default=0, help_text=_("Lower numbers come first, for example among the members.")
    )
    photo = models.ImageField(_("photo"), upload_to=photo_path, blank=True, help_text=_("A square portrait works best."))
    whatsapp_number = models.CharField(
        _("WhatsApp number (optional)"),
        max_length=20,
        blank=True,
        help_text=_("If filled in, visitors see a WhatsApp button on this card. Leave empty to keep it private."),
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["rank", "position", "full_name"]

    def __str__(self):
        return f"{self.full_name} ({self.get_role_display()})"

    def save(self, *args, **kwargs):
        self.rank = self.RANK.get(self.role, len(self.RANK))
        if self.whatsapp_number:
            self.whatsapp_number = normalize_whatsapp(self.whatsapp_number)
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        storage, name = self.photo.storage, self.photo.name
        super().delete(*args, **kwargs)
        if name:
            storage.delete(name)

    @property
    def initials(self):
        parts = [p for p in self.full_name.replace("-", " ").split() if p[:1].isalpha()]
        return "".join(p[0].upper() for p in parts[:2]) or "?"

    @property
    def whatsapp_link(self):
        return f"https://wa.me/{self.whatsapp_number.lstrip('+')}" if self.whatsapp_number else ""
