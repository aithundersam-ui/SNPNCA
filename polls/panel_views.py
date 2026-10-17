from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from accounts.audit import log_action
from core.translation import notify as notify_translated
from accounts.models import User
from accounts.permissions import admin_required

from .forms import PollForm
from .models import Poll


@admin_required
def poll_list(request):
    return render(request, "polls/panel_list.html", {"polls": Poll.objects.prefetch_related("ballots")})


@admin_required
def poll_edit(request, pk=None):
    poll = get_object_or_404(Poll, pk=pk) if pk else None
    if poll and poll.is_closed:
        messages.error(request, _("This vote is closed and can no longer be changed."))
        return redirect("panel:poll_results", pk=poll.pk)
    form = PollForm(request.POST or None, instance=poll)
    if request.method == "POST" and form.is_valid():
        creating = poll is None
        if creating:
            form.instance.created_by = request.user
        poll = form.save()
        log_action(request, "poll.create" if creating else "poll.update", str(poll))
        messages.success(request, _("Vote saved."))
        notify_translated(request, form)
        return redirect("panel:poll_results", pk=poll.pk)
    return render(request, "polls/panel_form.html", {"form": form, "poll": poll})


@admin_required
def poll_results(request, pk):
    poll = get_object_or_404(Poll, pk=pk)
    results, total = poll.results()
    voters = poll.ballots.count()
    members = User.objects.filter(is_active=True).count()
    turnout = round(100 * voters / members) if members else 0
    return render(
        request,
        "polls/panel_results.html",
        {"poll": poll, "results": results, "total": total, "voters": voters, "members": members, "turnout": turnout},
    )


@admin_required
@require_POST
def poll_close(request, pk):
    poll = get_object_or_404(Poll, pk=pk)
    if poll.is_open:
        poll.closed_early_at = timezone.now()
        poll.save(update_fields=["closed_early_at"])
        log_action(request, "poll.close", str(poll))
        messages.success(request, _("Vote closed. Members can now see the results if you chose to show them."))
    return redirect("panel:poll_results", pk=poll.pk)


@admin_required
def poll_delete(request, pk):
    poll = get_object_or_404(Poll, pk=pk)
    if request.method == "POST":
        if poll.ballots.exists() and not request.user.is_master:
            messages.error(request, _("Members have already voted. Only a Master Admin can delete this vote."))
            return redirect("panel:poll_results", pk=poll.pk)
        log_action(request, "poll.delete", str(poll))
        poll.delete()
        messages.success(request, _("Vote deleted."))
        return redirect("panel:polls")
    return render(request, "panel/confirm_delete.html", {"object_label": str(poll), "cancel_url": "panel:polls"})
