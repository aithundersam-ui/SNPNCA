from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _

from accounts.audit import log_action
from accounts.permissions import master_required

from .forms import TeamMemberForm
from .models import TeamMember


@master_required
def team_list(request):
    return render(request, "team/panel_list.html", {"people": TeamMember.objects.all()})


@master_required
def team_edit(request, pk=None):
    person = get_object_or_404(TeamMember, pk=pk) if pk else None
    form = TeamMemberForm(request.POST or None, request.FILES or None, instance=person)
    if request.method == "POST" and form.is_valid():
        person = form.save()
        log_action(request, "team.update" if pk else "team.create", person.full_name)
        messages.success(request, _("Team page updated."))
        return redirect("panel:team")
    return render(request, "team/panel_form.html", {"form": form, "person": person})


@master_required
def team_delete(request, pk):
    person = get_object_or_404(TeamMember, pk=pk)
    if request.method == "POST":
        log_action(request, "team.delete", person.full_name)
        person.delete()
        messages.success(request, _("Removed from the team page."))
        return redirect("panel:team")
    return render(request, "panel/confirm_delete.html", {"object_label": person.full_name, "cancel_url": "panel:team"})
