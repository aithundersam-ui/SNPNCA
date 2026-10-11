"""Admin panel pages for meeting days and the queue of requests."""

from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from accounts.audit import log_action
from accounts.permissions import admin_required, master_required

from .forms import MeetingDayForm
from .models import MeetingDay, MeetingRequest

Status = MeetingRequest.Status


@admin_required
def day_list(request):
    upcoming = MeetingDay.upcoming()
    past = MeetingDay.objects.filter(date__lt=timezone.localdate()).order_by("-date")[:6]
    return render(request, "meetings/panel_days.html", {"upcoming": upcoming, "past": past})


@master_required
def day_edit(request, pk=None):
    day = get_object_or_404(MeetingDay, pk=pk) if pk else None
    form = MeetingDayForm(request.POST or None, instance=day)
    if request.method == "POST" and form.is_valid():
        day = form.save(commit=False)
        if not day.pk:
            day.created_by = request.user
        day.save()
        log_action(request, "meeting_day.update" if pk else "meeting_day.create", day.date.isoformat())
        messages.success(request, _("Meeting day saved."))
        return redirect("panel:meetings")
    return render(request, "meetings/panel_day_form.html", {"form": form, "day": day})


@master_required
def day_delete(request, pk):
    day = get_object_or_404(MeetingDay, pk=pk)
    if request.method == "POST":
        log_action(request, "meeting_day.delete", day.date.isoformat(), requests=day.requests.count())
        day.delete()
        messages.success(request, _("Meeting day deleted."))
        return redirect("panel:meetings")
    return render(request, "panel/confirm_delete.html", {"object_label": day.date, "cancel_url": "panel:meetings"})


@admin_required
def day_queue(request, pk):
    day = get_object_or_404(MeetingDay, pk=pk)
    queue = day.requests.select_related("user", "handled_by")
    return render(request, "meetings/panel_queue.html", {
        "day": day,
        "queue": queue,
        "waiting": queue.filter(status=Status.WAITING).count(),
        "now_serving": day.now_serving(),
    })


@admin_required
@require_POST
def start(request, pk):
    """Mark the order as in a meeting, close the previous one, and send the
    admin to WhatsApp with the member's number."""
    with transaction.atomic():
        booking = get_object_or_404(MeetingRequest.objects.select_for_update().select_related("day", "user"), pk=pk)
        if booking.status not in MeetingRequest.ACTIVE:
            messages.error(request, _("Request #%(number)s is no longer in the queue.") % {"number": booking.number})
            return redirect("panel:meeting_queue", pk=booking.day_id)
        if not booking.user.whatsapp_number:
            messages.error(request, _("%(name)s has no WhatsApp number. Add it to their account first.") % {"name": booking.user.full_name})
            return redirect("panel:meeting_queue", pk=booking.day_id)
        now = timezone.now()
        booking.day.requests.filter(status=Status.IN_PROGRESS).exclude(pk=booking.pk).update(status=Status.DONE, finished_at=now)
        if booking.status == Status.WAITING:
            booking.status = Status.IN_PROGRESS
            booking.started_at = now
            booking.handled_by = request.user
            booking.save(update_fields=["status", "started_at", "handled_by"])
            log_action(request, "meeting.start", f"#{booking.number}", member=booking.user.email)
    return redirect(reverse("panel:meeting_call", args=[booking.pk]) + "?open=1")


@admin_required
def call(request, pk):
    """Opens WhatsApp on the admin's device with the member's chat, from where
    the admin taps the call button."""
    booking = get_object_or_404(MeetingRequest.objects.select_related("day", "user"), pk=pk)
    return render(request, "meetings/panel_call.html", {"booking": booking, "auto_open": booking.status == Status.IN_PROGRESS and request.GET.get("open") == "1"})


@admin_required
@require_POST
def set_status(request, pk):
    booking = get_object_or_404(MeetingRequest, pk=pk)
    new = request.POST.get("status")
    allowed = {Status.DONE, Status.NO_SHOW, Status.CANCELLED, Status.WAITING}
    if new in allowed and booking.status != new:
        old = booking.status
        booking.status = new
        booking.finished_at = None if new == Status.WAITING else timezone.now()
        if new == Status.WAITING:
            booking.started_at = None
        booking.save(update_fields=["status", "finished_at", "started_at"])
        log_action(request, "meeting.status", f"#{booking.number}", old=old, new=new)
    return redirect("panel:meeting_queue", pk=booking.day_id)
