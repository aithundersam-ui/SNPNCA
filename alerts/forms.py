from datetime import timedelta

from django import forms
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from core.forms import ArabicFieldsMixin

from .models import Alert

DAYS = [(1, _("1 day")), (3, _("3 days")), (7, _("1 week")), (14, _("2 weeks")), (30, _("1 month"))]


class AlertForm(ArabicFieldsMixin, forms.ModelForm):
    show_days = forms.TypedChoiceField(label=_("Show the banner on the site for"), choices=DAYS, coerce=int, initial=7)
    send_email = forms.BooleanField(label=_("Also email it to all members now"), required=False, initial=True)

    class Meta:
        model = Alert
        fields = ["title_fr", "title_en", "title_ar", "body_fr", "body_en", "body_ar"]
        widgets = {f: forms.Textarea(attrs={"rows": 5}) for f in ["body_fr", "body_en", "body_ar"]}

    def clean(self):
        data = super().clean()
        if not (data.get("title_fr") or data.get("title_en")):
            raise forms.ValidationError(_("Write the title in French or English."))
        if not (data.get("body_fr") or data.get("body_en")):
            raise forms.ValidationError(_("Write the message in French or English."))
        return data

    def save(self, commit=True):
        self.instance.show_until = timezone.now() + timedelta(days=self.cleaned_data["show_days"])
        return super().save(commit)
