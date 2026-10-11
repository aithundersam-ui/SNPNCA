from datetime import datetime, timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

MAX_DAYS_PER_MONTH = 2


def validate_meet_link(value):
    """No longer used (meetings now run on Daily); kept because migration 0001 refers to it."""
    if not value.startswith("https://meet.google.com/"):
        raise ValidationError(_("Enter a Google Meet link starting with https://meet.google.com/"))


class MeetingDay(models.Model):
    """One of the (at most two) days per month chosen by a Master Admin for
    one-on-one meetings."""

    date = models.DateField(_("date"), unique=True)
    start_time = models.TimeField(_("start time"), default="09:00")
    slot_minutes = models.PositiveSmallIntegerField(_("minutes per meeting"), default=20)
    capacity = models.PositiveSmallIntegerField(_("maximum number of requests"), default=20)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["date"]

    def __str__(self):
        return self.date.isoformat()

    def clean(self):
        if self.date:
            same_month = MeetingDay.objects.filter(date__year=self.date.year, date__month=self.date.month).exclude(pk=self.pk)
            if same_month.count() >= MAX_DAYS_PER_MONTH:
                raise ValidationError({"date": _("There can be at most two meeting days per month.")})

    @property
    def starts_at(self):
        return timezone.make_aware(datetime.combine(self.date, self.start_time))

    @property
    def is_past(self):
        return self.date < timezone.localdate()

    def active_requests(self):
        return self.requests.filter(status__in=MeetingRequest.ACTIVE)

    def is_full(self):
        return self.requests.exclude(status=MeetingRequest.Status.CANCELLED).count() >= self.capacity

    def now_serving(self):
        """The order currently in a meeting, if any."""
        return self.requests.filter(status=MeetingRequest.Status.IN_PROGRESS).order_by("pk").first()

    @classmethod
    def upcoming(cls):
        return cls.objects.filter(date__gte=timezone.localdate())


class MeetingRequest(models.Model):
    """A member's numbered order in a meeting day's queue. The order number is
    the primary key, so it is unique and always increasing."""

    class Status(models.TextChoices):
        WAITING = "waiting", _("Waiting")
        IN_PROGRESS = "in_progress", _("In meeting")
        DONE = "done", _("Done")
        NO_SHOW = "no_show", _("Absent")
        CANCELLED = "cancelled", _("Cancelled")

    ACTIVE = (Status.WAITING, Status.IN_PROGRESS)

    day = models.ForeignKey(MeetingDay, on_delete=models.CASCADE, related_name="requests", verbose_name=_("day"))
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="meeting_requests")
    subject = models.CharField(_("subject"), max_length=200)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.WAITING, db_index=True)
    handled_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["pk"]

    def __str__(self):
        return f"#{self.number}"

    @property
    def number(self):
        return self.pk

    @property
    def is_active(self):
        return self.status in self.ACTIVE

    def people_ahead(self):
        """Orders on the same day that will be seen before this one."""
        if self.status != self.Status.WAITING:
            return 0
        return self.day.requests.filter(status__in=self.ACTIVE, pk__lt=self.pk).count()

    def estimated_start(self):
        """Rough time this order should start: the day's start (or now, once the
        day has begun) plus one slot per person ahead."""
        base = max(self.day.starts_at, timezone.now())
        return base + timedelta(minutes=self.day.slot_minutes * self.people_ahead())
