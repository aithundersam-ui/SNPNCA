import re
import time

from django import forms
from django.core import signing
from django.utils.translation import gettext_lazy as _

from .models import ContactMessage, SiteContent

PHONE_RE = re.compile(r"^\+?[0-9 ().-]{8,20}$")
MIN_FILL_SECONDS = 3
FORM_MAX_AGE = 60 * 60 * 6


class ContactForm(forms.ModelForm):
    """Contact Us form with two invisible spam checks: a honeypot field that
    people never see, and a signed timestamp that rejects instant bot submits."""

    website = forms.CharField(required=False, label=_("Leave this field empty"))
    ts = forms.CharField(widget=forms.HiddenInput)

    class Meta:
        model = ContactMessage
        fields = ["full_name", "email", "phone", "message"]
        labels = {
            "full_name": _("Full Name"),
            "email": _("Email"),
            "phone": _("Phone Number"),
            "message": _("Message"),
        }
        widgets = {
            "full_name": forms.TextInput(attrs={"autocomplete": "name", "placeholder": _("Your full name")}),
            "email": forms.EmailInput(attrs={"autocomplete": "email", "placeholder": _("your.email@example.com")}),
            "phone": forms.TextInput(attrs={"autocomplete": "tel", "inputmode": "tel", "placeholder": "+213 5XX XX XX XX"}),
            "message": forms.Textarea(attrs={"rows": 6, "placeholder": _("How can we help you?")}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.is_bound:
            self.initial["ts"] = signing.dumps(time.time(), salt="contact-ts")
        for name in self.Meta.fields:
            self.fields[name].required = True

    def clean_phone(self):
        phone = self.cleaned_data["phone"].strip()
        if not PHONE_RE.match(phone):
            raise forms.ValidationError(_("Enter a valid phone number."))
        return phone

    def clean_message(self):
        message = self.cleaned_data["message"].strip()
        if len(message) < 10:
            raise forms.ValidationError(_("Your message is too short."))
        return message

    def is_spam(self):
        if self.data.get("website"):
            return True
        try:
            started = signing.loads(self.data.get("ts", ""), salt="contact-ts", max_age=FORM_MAX_AGE)
        except signing.BadSignature:
            return True
        return time.time() - float(started) < MIN_FILL_SECONDS


class SiteContentForm(forms.ModelForm):
    class Meta:
        model = SiteContent
        fields = ["description_fr", "description_en", "mission_fr", "mission_en"]
        widgets = {f: forms.Textarea(attrs={"rows": 6}) for f in fields}


class ReplyForm(forms.Form):
    body = forms.CharField(label=_("Reply"), widget=forms.Textarea(attrs={"rows": 8}), max_length=10000)
