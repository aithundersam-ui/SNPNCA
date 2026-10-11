from django import forms
from django.utils import formats, timezone
from django.utils.translation import gettext_lazy as _

from .models import MeetingDay, MeetingRequest


class MeetingDayForm(forms.ModelForm):
    class Meta:
        model = MeetingDay
        fields = ["date", "start_time", "slot_minutes", "capacity"]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "start_time": forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
        }

    def clean_date(self):
        date = self.cleaned_data["date"]
        if date < timezone.localdate() and (not self.instance.pk or date != self.instance.date):
            raise forms.ValidationError(_("Choose a date that is not in the past."))
        return date

    def clean_slot_minutes(self):
        value = self.cleaned_data["slot_minutes"]
        if not 5 <= value <= 180:
            raise forms.ValidationError(_("Choose between 5 and 180 minutes."))
        return value

    def clean_capacity(self):
        value = self.cleaned_data["capacity"]
        if not 1 <= value <= 200:
            raise forms.ValidationError(_("Choose between 1 and 200."))
        return value


class BookingForm(forms.ModelForm):
    class Meta:
        model = MeetingRequest
        fields = ["day", "subject"]
        widgets = {"subject": forms.TextInput(attrs={"placeholder": _("What would you like to discuss?")})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["day"].queryset = MeetingDay.upcoming()
        self.fields["day"].empty_label = None
        self.fields["day"].label_from_instance = lambda d: formats.date_format(d.date, "DATE_FORMAT")

    def clean_day(self):
        day = self.cleaned_data["day"]
        if day.is_past:
            raise forms.ValidationError(_("This day has passed."))
        if day.is_full():
            raise forms.ValidationError(_("This day is full. Please choose another day."))
        return day
