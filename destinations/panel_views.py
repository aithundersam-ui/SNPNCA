from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _

from accounts.audit import log_action
from accounts.permissions import admin_required

from .forms import ActivityFormSet, DestinationForm
from .models import Destination


@admin_required
def destination_list(request):
    destinations = Destination.objects.prefetch_related("activities")
    return render(request, "destinations/panel_list.html", {"destinations": destinations})


@admin_required
def destination_edit(request, pk=None):
    destination = get_object_or_404(Destination, pk=pk) if pk else None
    form = DestinationForm(request.POST or None, request.FILES or None, instance=destination)
    formset = ActivityFormSet(request.POST or None, request.FILES or None, instance=destination, prefix="act")
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        with transaction.atomic():
            destination = form.save()
            formset.instance = destination
            formset.save()
        log_action(request, "destination.update" if pk else "destination.create", str(destination))
        messages.success(request, _("Destination saved."))
        return redirect("panel:destinations")
    return render(request, "destinations/panel_form.html", {"form": form, "formset": formset, "destination": destination})


@admin_required
def destination_delete(request, pk):
    destination = get_object_or_404(Destination, pk=pk)
    if request.method == "POST":
        log_action(request, "destination.delete", str(destination))
        destination.delete()
        messages.success(request, _("Destination deleted."))
        return redirect("panel:destinations")
    return render(request, "panel/confirm_delete.html", {"object_label": str(destination), "cancel_url": "panel:destinations"})
