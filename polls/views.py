from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.db.models import F
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _

from .forms import VoteForm
from .models import Ballot, Choice, Poll


@login_required
def poll_list(request):
    now = timezone.now()
    polls = list(Poll.objects.filter(opens_at__lte=now).prefetch_related("choices"))
    voted = set(Ballot.objects.filter(user=request.user, poll__in=polls).values_list("poll_id", flat=True))
    for poll in polls:
        poll.voted = poll.pk in voted
    return render(
        request,
        "polls/list.html",
        {
            "open_polls": [p for p in polls if p.is_open],
            "closed_polls": [p for p in polls if p.is_closed],
            "upcoming": Poll.objects.filter(opens_at__gt=now).order_by("opens_at"),
        },
    )


@login_required
def poll_detail(request, pk):
    poll = get_object_or_404(Poll.objects.filter(opens_at__lte=timezone.now()), pk=pk)
    voted = poll.has_voted(request.user)
    form = VoteForm(poll, request.POST or None)
    if request.method == "POST":
        if not poll.is_open:
            messages.error(request, _("This vote is closed."))
            return redirect("polls:detail", pk=poll.pk)
        if voted:
            messages.error(request, _("You have already voted. Each member votes only once."))
            return redirect("polls:detail", pk=poll.pk)
        if form.is_valid():
            try:
                with transaction.atomic():
                    Ballot.objects.create(poll=poll, user=request.user)
                    Choice.objects.filter(pk=form.cleaned_data["choice"].pk, poll=poll).update(votes=F("votes") + 1)
            except IntegrityError:
                messages.error(request, _("You have already voted. Each member votes only once."))
            else:
                messages.success(request, _("Thank you, your vote has been counted. It is secret: nobody can see what you chose."))
            return redirect("polls:detail", pk=poll.pk)
    results = total = None
    if poll.is_closed and (poll.show_results or request.user.is_admin):
        results, total = poll.results()
    return render(request, "polls/detail.html", {"poll": poll, "form": form, "voted": voted, "results": results, "total": total})
