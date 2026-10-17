import io

from django import forms
from django.core.files.base import ContentFile
from django.utils.translation import gettext_lazy as _
from PIL import Image, ImageOps

from core.forms import ArabicFieldsMixin

from .models import Destination

MAX_ACTIVITIES = 15
PHOTO_SIZE = (1200, 900)  # 4:3, like the cards


def _lines(text):
    return [line.strip() for line in (text or "").splitlines() if line.strip()]


def card_photo(fileobj):
    """Turn any upload into a 1200x900 JPEG cropped around the centre."""
    with Image.open(fileobj) as img:
        img = ImageOps.exif_transpose(img).convert("RGB")
        img = ImageOps.fit(img, PHOTO_SIZE, method=Image.Resampling.LANCZOS, centering=(0.5, 0.45))
        out = io.BytesIO()
        img.save(out, "JPEG", quality=85, optimize=True, progressive=True)
    return out.getvalue()


class DestinationForm(ArabicFieldsMixin, forms.ModelForm):
    activities_fr = forms.CharField(
        label=_("Top activities (French), one per line"), required=False,
        widget=forms.Textarea(attrs={"rows": 6}),
        help_text=_("For example: Visit the Eiffel Tower. They are shown in this order."),
    )
    activities_en = forms.CharField(
        label=_("Top activities (English), one per line"), required=False,
        widget=forms.Textarea(attrs={"rows": 6}),
        help_text=_("Optional. Same order and number of lines as in French."),
    )
    activities_ar = forms.CharField(
        label=_("Top activities (Arabic), one per line"), required=False,
        widget=forms.Textarea(attrs={"rows": 6}),
        help_text=_("Optional. Same order and number of lines as in French."),
    )

    class Meta:
        model = Destination
        fields = ["name_fr", "name_en", "name_ar", "photo", "position"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            activities = list(self.instance.activities.all())
            for code in ("fr", "en", "ar"):
                self.initial.setdefault(f"activities_{code}", "\n".join(getattr(a, f"text_{code}") for a in activities))

    def clean_photo(self):
        from panel.forms import validate_image

        photo = self.cleaned_data.get("photo")
        if photo and photo is not self.instance.photo:
            validate_image(photo)
        return photo

    def clean(self):
        data = super().clean()
        fr, en, ar = (_lines(data.get(f"activities_{c}")) for c in ("fr", "en", "ar"))
        main = fr or en or ar
        if len(main) > MAX_ACTIVITIES:
            self.add_error("activities_fr", _("Give at most %(n)s activities.") % {"n": MAX_ACTIVITIES})
        for name, lines in (("activities_en", en), ("activities_ar", ar)):
            if fr and lines and len(lines) != len(fr):
                self.add_error(name, _("Give the same number of lines as in French."))
        n = len(main)
        data["activities"] = list(zip(fr or [""] * n, en or [""] * n, ar or [""] * n))
        return data

    def save(self, commit=True):
        old = Destination.objects.filter(pk=self.instance.pk).values_list("photo", flat=True).first() if self.instance.pk else None
        new_upload = "photo" in self.changed_data and self.cleaned_data.get("photo")
        if new_upload:
            self.instance.photo.save("card.jpg", ContentFile(card_photo(new_upload)), save=False)
        destination = super().save(commit=commit)
        if commit:
            if old and old != destination.photo.name:
                destination.photo.storage.delete(old)
            destination.activities.all().delete()
            for i, (text_fr, text_en, text_ar) in enumerate(self.cleaned_data["activities"]):
                destination.activities.create(text_fr=text_fr, text_en=text_en, text_ar=text_ar, position=i)
        return destination
