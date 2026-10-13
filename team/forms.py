from django import forms
from django.core.exceptions import ValidationError

from accounts.models import normalize_whatsapp

from .models import TeamMember


class TeamMemberForm(forms.ModelForm):
    class Meta:
        model = TeamMember
        fields = ["full_name", "role", "position", "photo", "whatsapp_number"]

    def clean_photo(self):
        from panel.forms import validate_image

        photo = self.cleaned_data.get("photo")
        if photo and photo is not self.instance.photo:
            validate_image(photo)
        return photo

    def clean_whatsapp_number(self):
        value = self.cleaned_data["whatsapp_number"].strip()
        if not value:
            return ""
        try:
            return normalize_whatsapp(value)
        except ValidationError as exc:
            raise forms.ValidationError(exc.messages) from exc

    def save(self, commit=True):
        old = TeamMember.objects.filter(pk=self.instance.pk).values_list("photo", flat=True).first() if self.instance.pk else None
        obj = super().save(commit)
        if commit and old and old != obj.photo.name:
            obj.photo.storage.delete(old)
        return obj
