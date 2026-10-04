from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse, reverse_lazy, translate_url
from django.utils import translation
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from . import lockout
from .audit import client_ip
from .forms import AccountSettingsForm, LoginForm, MemberPasswordResetForm


def _safe_next(request, fallback):
    nxt = request.POST.get("next") or request.GET.get("next")
    if nxt and url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return nxt
    return fallback


def _set_language_cookie(response, language):
    response.set_cookie(
        settings.LANGUAGE_COOKIE_NAME,
        language,
        max_age=settings.LANGUAGE_COOKIE_AGE,
        samesite="Lax",
        secure=getattr(settings, "LANGUAGE_COOKIE_SECURE", False),
    )
    return response


def login_view(request):
    if request.user.is_authenticated:
        return redirect("core:home")
    form = LoginForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        email = form.cleaned_data["email"].strip().lower()
        ip = client_ip(request)
        if lockout.is_locked(email, ip):
            form.add_error(None, _("Too many failed attempts. Please wait 15 minutes and try again."))
        else:
            user = authenticate(request, email=email, password=form.cleaned_data["password"])
            if user is None:
                lockout.record_failure(email, ip)
                form.add_error(None, _("Incorrect email or password."))
            else:
                lockout.clear(email)
                login(request, user)
                lang = user.preferred_language
                translation.activate(lang)
                target = translate_url(_safe_next(request, reverse("core:home")), lang)
                return _set_language_cookie(redirect(target), lang)
    return render(request, "accounts/login.html", {"form": form, "next": request.GET.get("next", "")})


@require_POST
def logout_view(request):
    logout(request)
    return redirect("core:home")


@require_POST
def set_language(request):
    language = request.POST.get("language")
    if language not in dict(settings.LANGUAGES):
        language = settings.LANGUAGE_CODE
    if request.user.is_authenticated and request.user.preferred_language != language:
        request.user.preferred_language = language
        request.user.save(update_fields=["preferred_language"])
    target = translate_url(_safe_next(request, "/"), language)
    return _set_language_cookie(redirect(target), language)


@login_required
def account_settings(request):
    form = AccountSettingsForm(request.POST or None, instance=request.user)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        messages.success(request, _("Your settings were saved."))
        response = redirect(translate_url(reverse("accounts:settings"), user.preferred_language))
        return _set_language_cookie(response, user.preferred_language)
    return render(request, "accounts/settings.html", {"form": form})


class PasswordResetView(auth_views.PasswordResetView):
    form_class = MemberPasswordResetForm
    template_name = "accounts/password_reset.html"
    success_url = reverse_lazy("accounts:password_reset_done")

    def form_valid(self, form):
        ip = client_ip(self.request)
        # Quietly cap reset emails per IP so the form can't be used to spam inboxes.
        if lockout.hit_rate_limit(f"pwreset:{ip}", 5, 3600):
            return redirect(self.success_url)
        return super().form_valid(form)


class PasswordResetDoneView(auth_views.PasswordResetDoneView):
    template_name = "accounts/password_reset_done.html"


class PasswordResetConfirmView(auth_views.PasswordResetConfirmView):
    template_name = "accounts/password_reset_confirm.html"
    success_url = reverse_lazy("accounts:password_reset_complete")
    post_reset_login = False


class PasswordResetCompleteView(auth_views.PasswordResetCompleteView):
    template_name = "accounts/password_reset_complete.html"


class PasswordChangeView(auth_views.PasswordChangeView):
    template_name = "accounts/password_change.html"
    success_url = reverse_lazy("accounts:settings")

    def form_valid(self, form):
        messages.success(self.request, _("Your password was changed."))
        return super().form_valid(form)
