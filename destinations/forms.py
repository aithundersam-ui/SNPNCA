import io

from django import forms
from django.core.files.base import ContentFile
from django.utils.translation import gettext_lazy as _
from PIL import Image, ImageOps

from core.forms import ArabicFieldsMixin
from core.translation import AutoTranslateMixin

from .models import Activity, Destination

MAX_ACTIVITIES = 15
PHOTO_SIZE = (1200, 900)  # 4:3, like the cards


def card_photo(fileobj):
    """Turn any upload into a 1200x900 JPEG cropped around the centre."""
    with Image.open(fileobj) as img:
        img = ImageOps.exif_transpose(img).convert("RGB")
        img = ImageOps.fit(img, PHOTO_SIZE, method=Image.Resampling.LANCZOS, centering=(0.5, 0.45))
        out = io.BytesIO()
        img.save(out, "JPEG", quality=85, optimize=True, progressive=True)
    return out.getvalue()


class PhotoFormMixin:
    """Validates the photo, stores it resized and removes the file it replaces."""

    def clean_photo(self):
        from panel.forms import validate_image

        photo = self.cleaned_data.get("photo")
        if photo and photo is not self.instance.photo:
            validate_image(photo)
        return photo

    def save(self, commit=True):
        model = type(self.instance)
        old = model.objects.filter(pk=self.instance.pk).values_list("photo", flat=True).first() if self.instance.pk else None
        new_upload = "photo" in self.changed_data and self.cleaned_data.get("photo")
        if new_upload:
            self.instance.photo.save("photo.jpg", ContentFile(card_photo(new_upload)), save=False)
        obj = super().save(commit=commit)
        if commit and old and old != obj.photo.name:
            obj.photo.storage.delete(old)
        return obj


class DestinationForm(AutoTranslateMixin, PhotoFormMixin, ArabicFieldsMixin, forms.ModelForm):
    class Meta:
        model = Destination
        fields = ["name_fr", "name_en", "name_ar", "photo", "position"]


class ActivityForm(AutoTranslateMixin, PhotoFormMixin, ArabicFieldsMixin, forms.ModelForm):
    class Meta:
        model = Activity
        fields = [
            "title_fr", "title_en", "title_ar",
            "description_fr", "description_en", "description_ar",
            "photo", "maps_url", "position",
        ]
        widgets = {f"description_{c}": forms.Textarea(attrs={"rows": 3}) for c in ("fr", "en", "ar")}
        help_texts = {
            "maps_url": _("In Google Maps, open the place, tap Share and then Copy link."),
            "photo": _("A landscape photo works best. It is resized and cropped automatically."),
        }


ActivityFormSet = forms.inlineformset_factory(
    Destination, Activity, form=ActivityForm, extra=1, can_delete=True,
    max_num=MAX_ACTIVITIES, validate_max=True,
)
