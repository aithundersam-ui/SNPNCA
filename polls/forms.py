from django import forms
from django.utils.translation import gettext_lazy as _

from core.forms import ArabicFieldsMixin
from core.translation import AutoTranslateMixin

from .models import Poll

MAX_CHOICES = 10


def _lines(text):
    return [line.strip() for line in (text or "").splitlines() if line.strip()]


class PollForm(AutoTranslateMixin, ArabicFieldsMixin, forms.ModelForm):
    required_translations = ("title",)
    choices_fr = forms.CharField(
        label=_("Answers (French), one per line"),
        widget=forms.Textarea(attrs={"rows": 4}),
        required=False,
        help_text=_("For example: Oui / Non / Abstention."),
    )
    choices_en = forms.CharField(
        label=_("Answers (English), one per line"),
        widget=forms.Textarea(attrs={"rows": 4}),
        required=False,
        help_text=_("Optional. Same order and number of lines as the French answers."),
    )
    choices_ar = forms.CharField(
        label=_("Answers (Arabic), one per line"),
        widget=forms.Textarea(attrs={"rows": 4}),
        required=False,
        help_text=_("Optional. Same order and number of lines as the French answers."),
    )

    class Meta:
        model = Poll
        fields = ["category", "title_fr", "title_en", "title_ar", "description_fr", "description_en", "description_ar", "opens_at", "closes_at", "show_results"]
        widgets = {
            "opens_at": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
            "closes_at": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
            "description_fr": forms.Textarea(attrs={"rows": 3}),
            "description_en": forms.Textarea(attrs={"rows": 3}),
            "description_ar": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.locked = bool(self.instance.pk and self.instance.ballots.exists())
        if self.instance.pk:
            choices = list(self.instance.choices.all())
            self.initial.setdefault("choices_fr", "\n".join(c.text_fr for c in choices))
            self.initial.setdefault("choices_en", "\n".join(c.text_en for c in choices))
            self.initial.setdefault("choices_ar", "\n".join(c.text_ar for c in choices))
        if self.locked:
            # Once someone has voted, the question and answers can no longer change.
            for name in ["category", "title_fr", "title_en", "title_ar", "choices_fr", "choices_en", "choices_ar", "opens_at"]:
                self.fields[name].disabled = True

    def clean(self):
        data = super().clean()
        opens, closes = data.get("opens_at"), data.get("closes_at")
        if opens and closes and closes <= opens:
            self.add_error("closes_at", _("The vote must close after it opens."))
        if self.locked:
            return data
        fr, en = _lines(data.get("choices_fr")), _lines(data.get("choices_en"))
        main = fr or en
        if len(main) < 2:
            self.add_error("choices_fr", _("Give at least two answers."))
        elif len(main) > MAX_CHOICES:
            self.add_error("choices_fr", _("Give at most %(n)s answers.") % {"n": MAX_CHOICES})
        elif fr and en and len(fr) != len(en):
            self.add_error("choices_en", _("Give the same number of answers in French and English."))
        ar = _lines(data.get("choices_ar"))
        if ar and main and len(ar) != len(main):
            self.add_error("choices_ar", _("Give the same number of answers in Arabic as in French."))
        n = len(main)
        data["answers"] = list(zip(fr or [""] * n, en or [""] * n, ar or [""] * n))
        return data

    def save(self, commit=True):
        poll = super().save(commit=commit)
        if commit and not self.locked:
            poll.choices.all().delete()
            for i, (text_fr, text_en, text_ar) in enumerate(self.cleaned_data["answers"]):
                poll.choices.create(text_fr=text_fr, text_en=text_en, text_ar=text_ar, position=i)
        return poll


class VoteForm(forms.Form):
    choice = forms.ModelChoiceField(queryset=None, widget=forms.RadioSelect, empty_label=None, label=_("Your answer"))

    def __init__(self, poll, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["choice"].queryset = poll.choices.all()
        self.fields["choice"].label_from_instance = lambda c: c.localized("text")
