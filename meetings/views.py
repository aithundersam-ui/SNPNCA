from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from .forms import BookingForm
from .models import MeetingDay, MeetingRequest


@login_required
def index(request):
    active = (
        MeetingRequest.objects.filter(user=request.user, status__in=MeetingRequest.ACTIVE)
        .select_related("day")
        .first()
    )
    form = BookingForm(request.POST or None, initial={"whatsapp_number": request.user.whatsapp_number})
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
                    if request.user.whatsapp_number != form.cleaned_data["whatsapp_number"]:
                        request.user.whatsapp_number = form.cleaned_data["whatsapp_number"]
                        request.user.save(update_fields=["whatsapp_number"])
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

