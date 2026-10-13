import logging

from django.conf import settings
from django.core.mail import EmailMessage, get_connection
from django.template.loader import render_to_string
from django.utils import timezone, translation

from accounts.models import User

logger = logging.getLogger(__name__)


def email_alert(alert):
    """Email the alert to every active member in their language. Returns (sent, failed)."""
    rendered = {}
    for language in ("fr", "en", "ar"):
        title, body = alert.text_in(language)
        context = {"alert": alert, "title": title, "body": body, "url": alert.url(language), "site_url": settings.SITE_URL}
        with translation.override(language):
            rendered[language] = (
                render_to_string("emails/alert_subject.txt", context).strip(),
                render_to_string("emails/alert_body.txt", context),
            )
    recipients = User.objects.filter(is_active=True).exclude(email="").only("email", "preferred_language")
    emails = []
    for user in recipients:
        subject, body = rendered.get(user.preferred_language, rendered["fr"])
        emails.append(EmailMessage(subject, body, settings.DEFAULT_FROM_EMAIL, [user.email]))
    sent = failed = 0
    if emails:
        try:
            sent = get_connection().send_messages(emails) or 0
            failed = len(emails) - sent
        except Exception:
            logger.exception("Could not email alert %s", alert.pk)
            failed = len(emails) - sent
    alert.emailed_at = timezone.now()
    alert.emails_sent = sent
    alert.emails_failed = failed
    alert.save(update_fields=["emailed_at", "emails_sent", "emails_failed"])
    return sent, failed
