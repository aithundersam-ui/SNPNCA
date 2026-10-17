from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from accounts.audit import log_action
from core.translation import notify as notify_translated
from accounts.models import User
from accounts.permissions import admin_required

from .forms import AlertForm
from .models import Alert
from .sending import email_alert


@admin_required
def alert_list(request):
    return render(request, "alerts/panel_list.html", {"alerts": Alert.objects.all()})


@admin_required
def alert_create(request):
    form = AlertForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.instance.created_by = request.user
        alert = form.save()
        notify_translated(request, form)
        log_action(request, "alert.create", str(alert))
        if form.cleaned_data["send_email"]:
            sent, failed = email_alert(alert)
            log_action(request, "alert.email", str(alert), sent=sent, failed=failed)
            if failed:
                messages.error(request, _("The alert is on the site, but %(failed)s emails could not be sent. Check the email settings.") % {"failed": failed})
            else:
                messages.success(request, _("Alert published and emailed to %(sent)s members.") % {"sent": sent})
        else:
            messages.success(request, _("Alert published on the site."))
        return redirect("panel:alert_detail", pk=alert.pk)
    return render(request, "alerts/panel_form.html", {"form": form})


@admin_required
def alert_detail(request, pk):
    alert = get_object_or_404(Alert, pk=pk)
    members = User.objects.filter(is_active=True).order_by("full_name", "email")
    with_number = [(m, alert.whatsapp_link_for(m)) for m in members if m.whatsapp_number]
    return render(
        request,
        "alerts/panel_detail.html",
        {
            "alert": alert,
            "share_fr": alert.whatsapp_share_link("fr"),
            "share_en": alert.whatsapp_share_link("en") if (alert.title_en or alert.body_en) else "",
            "with_number": with_number,
            "without_number": members.filter(whatsapp_number="").count(),
            "is_active": alert.show_until > timezone.now(),
        },
    )


@admin_required
@require_POST
def alert_email(request, pk):
    alert = get_object_or_404(Alert, pk=pk)
    sent, failed = email_alert(alert)
    log_action(request, "alert.email", str(alert), sent=sent, failed=failed)
    if failed:
        messages.error(request, _("%(failed)s emails could not be sent. Check the email settings.") % {"failed": failed})
    else:
        messages.success(request, _("Alert emailed to %(sent)s members.") % {"sent": sent})
    return redirect("panel:alert_detail", pk=alert.pk)


@admin_required
def alert_delete(request, pk):
    alert = get_object_or_404(Alert, pk=pk)
    if request.method == "POST":
        log_action(request, "alert.delete", str(alert))
        alert.delete()
        messages.success(request, _("Alert deleted."))
        return redirect("panel:alerts")
    return render(request, "panel/confirm_delete.html", {"object_label": str(alert), "cancel_url": "panel:alerts"})
