from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from core.models import BilingualMixin


class Poll(BilingualMixin, models.Model):
    """A vote. Ballots are secret: we record who voted, never what they chose."""

    class Category(models.TextChoices):
        ASSEMBLY = "assembly", _("General assembly")
        STRIKE = "strike", _("Strike consultation")
        SURVEY = "survey", _("Survey")

    class Status:
        UPCOMING = "upcoming"
        OPEN = "open"
        CLOSED = "closed"

    title_fr = models.CharField(_("question (French)"), max_length=200, blank=True)
    title_en = models.CharField(_("question (English)"), max_length=200, blank=True)
    description_fr = models.TextField(_("explanation (French)"), blank=True)
    description_en = models.TextField(_("explanation (English)"), blank=True)
    title_ar = models.CharField(_("question (Arabic)"), max_length=200, blank=True)
    description_ar = models.TextField(_("explanation (Arabic)"), blank=True)
    category = models.CharField(_("type"), max_length=10, choices=Category.choices, default=Category.SURVEY)
    opens_at = models.DateTimeField(_("voting opens"), default=timezone.now)
    closes_at = models.DateTimeField(_("voting closes"))
    closed_early_at = models.DateTimeField(null=True, blank=True)
    show_results = models.BooleanField(
        _("show results to members once the vote is closed"),
        default=True,
        help_text=_("Admins always see the results, even while the vote is open."),
    )
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-opens_at", "-pk"]

    def __str__(self):
        return self.title_fr or self.title_en

    @property
    def ends_at(self):
        return self.closed_early_at or self.closes_at

    @property
    def status(self):
        now = timezone.now()
        if now < self.opens_at:
            return self.Status.UPCOMING
        if now >= self.ends_at:
            return self.Status.CLOSED
        return self.Status.OPEN

    @property
    def is_open(self):
        return self.status == self.Status.OPEN

    @property
    def is_closed(self):
        return self.status == self.Status.CLOSED

    def has_voted(self, user):
        return self.ballots.filter(user=user).exists()

    def results(self):
        """Choices with their vote count and share, most votes first kept in display order."""
        choices = list(self.choices.all())
        total = sum(c.votes for c in choices)
        for c in choices:
            c.percent = round(100 * c.votes / total) if total else 0
        return choices, total


class Choice(BilingualMixin, models.Model):
    poll = models.ForeignKey(Poll, on_delete=models.CASCADE, related_name="choices")
    text_fr = models.CharField(max_length=200, blank=True)
    text_en = models.CharField(max_length=200, blank=True)
    text_ar = models.CharField(max_length=200, blank=True)
    position = models.PositiveIntegerField(default=0)
    # A plain counter so no row links a member to their choice.
    votes = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["position", "pk"]

    def __str__(self):
        return self.text_fr or self.text_en


class Ballot(models.Model):
    """Proof that a member voted, so they can only vote once. It does not say for what."""

    poll = models.ForeignKey(Poll, on_delete=models.CASCADE, related_name="ballots")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="ballots")
    voted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["poll", "user"], name="one_ballot_per_member")]
