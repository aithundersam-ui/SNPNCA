import logging
import mimetypes
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404, HttpResponse, HttpResponseRedirect
from django.shortcuts import redirect, render
from django.utils import translation
from django.utils.translation import gettext as _

from accounts.audit import client_ip
from accounts.emails import send_templated
from accounts.lockout import hit_rate_limit

from .forms import ContactForm
from .models import SiteContent

logger = logging.getLogger(__name__)


def root_redirect(request):
    if request.user.is_authenticated:
        lang = request.user.preferred_language
    else:
        lang = request.COOKIES.get(settings.LANGUAGE_COOKIE_NAME)
    if lang not in dict(settings.LANGUAGES):
        lang = settings.LANGUAGE_CODE
    return HttpResponseRedirect(f"/{lang}/")


def healthz(request):
    return HttpResponse("ok", content_type="text/plain")


def home(request):
    content = SiteContent.load()
    form = ContactForm(request.POST or None)
    if request.method == "POST":
        if form.is_valid():
            if form.is_spam() or hit_rate_limit(f"contact:{client_ip(request)}", 5, 3600):
                # Pretend it worked so bots learn nothing.
                messages.success(request, _("Message sent successfully! We will get back to you soon."))
                return redirect("core:home")
            contact = form.save(commit=False)
            contact.language = translation.get_language()[:2]
            contact.save()
            _notify_admins(contact)
            messages.success(request, _("Message sent successfully! We will get back to you soon."))
            return redirect(f"{request.path}#contact")
    return render(request, "core/home.html", {"content": content, "form": form})


def _notify_admins(contact):
    if not settings.CONTACT_NOTIFY_EMAIL:
        return
    try:
        send_templated(
            settings.CONTACT_NOTIFY_EMAIL,
            "contact_notification",
            {"contact": contact, "site_url": settings.SITE_URL},
            settings.LANGUAGE_CODE,
        )
    except Exception:  # the message is saved in the panel either way
        logger.exception("Could not email contact notification")


@login_required
def private_media(request, path):
    """Serve uploaded news images only to logged-in members."""
    if not path.startswith("news/"):
        raise Http404
    root = Path(settings.MEDIA_ROOT).resolve()
    full = (root / path).resolve()
    if root not in full.parents or not full.is_file():
        raise Http404
    content_type, _enc = mimetypes.guess_type(full.name)
    response = FileResponse(full.open("rb"), content_type=content_type or "application/octet-stream")
    response["Cache-Control"] = "private, max-age=3600"
    return response


def error_403(request, exception=None):
    return render(request, "core/error.html", {"code": 403, "title": _("Access denied"), "text": _("You do not have permission to view this page.")}, status=403)


def error_404(request, exception=None):
    return render(request, "core/error.html", {"code": 404, "title": _("Page Not Found"), "text": _("The page you're looking for doesn't exist or may have been moved.")}, status=404)


def error_500(request):
    return render(request, "core/error.html", {"code": 500, "title": _("Server error"), "text": _("Something went wrong. Please try again later.")}, status=500)
