from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from core.middleware import SecurityHeadersMiddleware as SecurityHeaders

from . import daily
from .forms import BookingForm
from .models import MeetingDay, MeetingRequest


@login_required
def index(request):
    active = (
        MeetingRequest.objects.filter(user=request.user, status__in=MeetingRequest.ACTIVE)
        .select_related("day")
        .first()
    )
    form = BookingForm(request.POST or None)
    if request.method == "POST":
        if active:
            messages.error(request, _("You already have a meeting request. Cancel it before booking another one."))
            return redirect("meetings:index")
        if form.is_valid():
            with transaction.atomic():
                # Lock the day so two members can't both take its last place.
                day = MeetingDay.objects.select_for_update().get(pk=form.cleaned_data["day"].pk)
                if day.is_full():
                    form.add_error("day", _("This day is full. Please choose another day."))
                else:
                    booking = MeetingRequest.objects.create(day=day, user=request.user, subject=form.cleaned_data["subject"])
                    messages.success(request, _("Your request is registered with number #%(number)s.") % {"number": booking.number})
                    return redirect("meetings:index")

    history = MeetingRequest.objects.filter(user=request.user).exclude(status__in=MeetingRequest.ACTIVE).select_related("day")[:10]
    days = MeetingDay.upcoming()
    context = {
        "form": form,
        "active": active,
        "history": history,
        "days": days,
        "now_serving": active.day.now_serving() if active else None,
        "auto_refresh": bool(active and active.day.date == timezone.localdate()),
    }
    return render(request, "meetings/index.html", context)


@login_required
@require_POST
def cancel(request, pk):
    booking = get_object_or_404(MeetingRequest, pk=pk, user=request.user, status=MeetingRequest.Status.WAITING)
    booking.status = MeetingRequest.Status.CANCELLED
    booking.finished_at = timezone.now()
    booking.save(update_fields=["status", "finished_at"])
    messages.success(request, _("Your request #%(number)s has been cancelled.") % {"number": booking.number})
    return redirect("meetings:index")


@login_required
def room(request, pk):
    """The video call, inside the site. Only the member who booked (while the
    meeting is running) and admins get a token to enter the private room."""
    booking = get_object_or_404(MeetingRequest.objects.select_related("day", "user"), pk=pk)
    is_admin = request.user.is_admin
    if not is_admin and booking.user_id != request.user.pk:
        raise PermissionDenied
    if booking.status != MeetingRequest.Status.IN_PROGRESS or not booking.room_url:
        messages.info(request, _("This meeting is not in progress."))
        return redirect("panel:meeting_queue", pk=booking.day_id) if is_admin else redirect("meetings:index")
    try:
        token = daily.meeting_token(booking.room_name, request.user.full_name or request.user.email, is_owner=is_admin)
    except daily.DailyError:
        messages.error(request, _("The video call is unavailable right now. Please try again in a moment."))
        return redirect("panel:meeting_queue", pk=booking.day_id) if is_admin else redirect("meetings:index")
    response = render(request, "meetings/room.html", {
        "booking": booking,
        "frame_url": f"{booking.room_url}?t={token}",
        "is_admin": is_admin,
    })
    # Let this page (and only this page) frame the Daily room and use the camera and microphone.
    host = daily.origin(booking.room_url)
    response["Content-Security-Policy"] = SecurityHeaders.CSP.replace("frame-src ", f"frame-src {host} ")
    allow = f'(self "{host}")'
    response["Permissions-Policy"] = f"camera={allow}, microphone={allow}, display-capture={allow}, fullscreen={allow}, geolocation=()"
    response["Cache-Control"] = "no-store"
    return response
