from django import forms
from django.contrib.auth.forms import PasswordResetForm
from django.utils.translation import gettext_lazy as _

from .models import Language, Role, User, normalize_whatsapp


class LoginForm(forms.Form):
    email = forms.EmailField(label=_("Email"), widget=forms.EmailInput(attrs={"autocomplete": "email", "autofocus": True}))
    password = forms.CharField(label=_("Password"), widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}))


class MemberPasswordResetForm(PasswordResetForm):
    """Also lets members who never set a password (invited accounts) request a link."""

    def get_users(self, email):
        return User.objects.filter(email__iexact=email.strip(), is_active=True)

    def send_mail(self, subject_template_name, email_template_name, context, from_email, to_email, html_email_template_name=None):
        from .emails import send_templated, set_password_url

        user = context["user"]
        send_templated(
            to_email,
            "password_reset",
            {"user": user, "url": set_password_url(user, user.preferred_language)},
            user.preferred_language,
        )


class AccountSettingsForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["full_name", "whatsapp_number", "preferred_language"]
        widgets = {"whatsapp_number": forms.TextInput(attrs={"autocomplete": "tel", "inputmode": "tel", "placeholder": "+213 5XX XX XX XX"})}

    def clean_whatsapp_number(self):
        return normalize_whatsapp(self.cleaned_data["whatsapp_number"])


class UserForm(forms.ModelForm):
    """Create/edit a member from the admin panel. Role is only offered to the Master Admin."""

    class Meta:
        model = User
        fields = ["full_name", "email", "whatsapp_number", "preferred_language", "role", "is_active"]
        widgets = {"whatsapp_number": forms.TextInput(attrs={"inputmode": "tel", "placeholder": "+213 5XX XX XX XX"})}

    def __init__(self, *args, actor=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.actor = actor
        # Required for new accounts; older accounts may not have one yet.
        self.fields["whatsapp_number"].required = not self.instance.pk
        self.fields["whatsapp_number"].help_text = _("Used by admins to call the member on WhatsApp for one-on-one meetings.")
        self.fields["preferred_language"].choices = Language.choices
        if not (actor and actor.is_master):
            del self.fields["role"]

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        qs = User.objects.filter(email__iexact=email)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError(_("An account with this email already exists."))
        return email

    def clean_whatsapp_number(self):
        return normalize_whatsapp(self.cleaned_data["whatsapp_number"])

    def clean_role(self):
        role = self.cleaned_data.get("role", Role.USER)
        if role not in Role.values:
            raise forms.ValidationError(_("Invalid role."))
        return role


class CsvUploadForm(forms.Form):
    file = forms.FileField(label=_("CSV file (UTF-8)"))

    def clean_file(self):
        f = self.cleaned_data["file"]
        if not f.name.lower().endswith(".csv"):
            raise forms.ValidationError(_("Please upload a .csv file."))
        if f.size > 1024 * 1024:
            raise forms.ValidationError(_("The file is larger than 1 MB."))
        return f

