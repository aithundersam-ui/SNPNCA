from django import forms
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from PIL import Image

from accounts.models import Role
from news.models import Article, embed_url
from qa.processing import InvalidPdf, validate_pdf_bytes

ALLOWED_IMAGE_FORMATS = {"JPEG", "PNG", "WEBP"}


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleImageField(forms.FileField):
    widget = MultipleFileInput

    def clean(self, data, initial=None):
        files = data if isinstance(data, (list, tuple)) else ([data] if data else [])
        return [validate_image(super(MultipleImageField, self).clean(f, initial)) for f in files if f]


def validate_image(f):
    if f.size > settings.MAX_IMAGE_MB * 1024 * 1024:
        raise forms.ValidationError(_("Each image must be smaller than %(mb)s MB.") % {"mb": settings.MAX_IMAGE_MB})
    try:
        with Image.open(f) as img:
            fmt = img.format
            img.verify()
    except Exception as exc:
        raise forms.ValidationError(_("One of the files is not a valid image.")) from exc
    if fmt not in ALLOWED_IMAGE_FORMATS:
        raise forms.ValidationError(_("Images must be JPEG, PNG or WebP."))
    f.seek(0)
    return f


class ArticleForm(forms.ModelForm):
    video_urls = forms.CharField(
        label=_("Videos (YouTube or Vimeo links, one per line)"),
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
    )
    new_images = MultipleImageField(label=_("Add images"), required=False)

    class Meta:
        model = Article
        fields = ["title_fr", "title_en", "body_fr", "body_en", "published_at", "is_published"]
        widgets = {
            "body_fr": forms.Textarea(attrs={"rows": 10}),
            "body_en": forms.Textarea(attrs={"rows": 10}),
            "published_at": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["published_at"].input_formats = ["%Y-%m-%dT%H:%M"]
        if self.instance.pk and not self.is_bound:
            self.initial["video_urls"] = "\n".join(v.url for v in self.instance.videos.all())

    def clean_video_urls(self):
        urls = [u.strip() for u in self.cleaned_data["video_urls"].splitlines() if u.strip()]
        bad = [u for u in urls if not embed_url(u)]
        if bad:
            raise forms.ValidationError(_("Only YouTube and Vimeo links are accepted: %(urls)s") % {"urls": ", ".join(bad)})
        return urls

    def clean(self):
        data = super().clean()
        if not (data.get("title_fr") or data.get("title_en")):
            raise forms.ValidationError(_("Enter a title in at least one language."))
        return data


class DocumentUploadForm(forms.Form):
    title = forms.CharField(label=_("Title"), max_length=255, required=False, help_text=_("Leave empty to use the file name."))
    file = forms.FileField(label=_("PDF file"))

    def clean_file(self):
        f = self.cleaned_data["file"]
        if f.size > settings.MAX_PDF_MB * 1024 * 1024:
            raise forms.ValidationError(_("The file is larger than %(mb)s MB.") % {"mb": settings.MAX_PDF_MB})
        if not f.name.lower().endswith(".pdf"):
            raise forms.ValidationError(_("Only PDF files are accepted."))
        head = f.read(5)
        try:
            self.page_count = validate_pdf_bytes(head, f)
        except InvalidPdf as exc:
            raise forms.ValidationError(_("This file is not a valid, unprotected PDF.")) from exc
        return f


class RoleForm(forms.Form):
    role = forms.ChoiceField(label=_("Role"), choices=Role.choices)
