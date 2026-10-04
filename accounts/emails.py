from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import translation
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode


def set_password_url(user, language):
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    with translation.override(language):
        path = reverse("accounts:password_reset_confirm", kwargs={"uidb64": uid, "token": token})
    return settings.SITE_URL + path


def send_templated(to, template, context, language):
    """Render `emails/<template>_subject.txt` and `_body.txt` in `language` and send."""
    with translation.override(language):
        subject = render_to_string(f"emails/{template}_subject.txt", context).strip()
        body = render_to_string(f"emails/{template}_body.txt", context)
    send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [to] if isinstance(to, str) else to)


def send_invitation(user):
    language = user.preferred_language
    send_templated(
        user.email,
        "invite",
        {"user": user, "url": set_password_url(user, language), "site_url": settings.SITE_URL},
        language,
    )
