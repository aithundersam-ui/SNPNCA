import io
import shutil
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import translation
from PIL import Image

from accounts.models import AuditLog, Role
from destinations.models import Destination

from .helpers import make_user


def image_upload(size=(2000, 1000)):
    buf = io.BytesIO()
    Image.new("RGB", size, (30, 90, 200)).save(buf, "PNG")
    return SimpleUploadedFile("beach.png", buf.getvalue(), content_type="image/png")


class DestinationPageTests(TestCase):
    def setUp(self):
        translation.activate("fr")
        self.member = make_user("member@example.com")

    def test_members_only(self):
        response = self.client.get(reverse("destinations:list"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response["Location"])

    def test_cards_with_activities_in_each_language(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse("destinations:list"))
        self.assertContains(response, '<details class="dest-card">', count=3)
        self.assertContains(response, "Croisière sur le Bosphore")
        self.assertContains(self.client.get("/en/destinations/"), "Take a Bosphorus cruise")
        self.assertContains(self.client.get("/ar/destinations/"), "رحلة بحرية في مضيق البوسفور")
        self.assertContains(response, 'href="/fr/destinations/"')  # menu link

    def test_arabic_falls_back_to_french(self):
        d = Destination.objects.create(name_fr="Alger", position=9)
        d.activities.create(text_fr="La Casbah")
        self.client.force_login(self.member)
        response = self.client.get("/ar/destinations/")
        self.assertContains(response, "Alger")
        self.assertContains(response, "La Casbah")


class DestinationAdminTests(TestCase):
    def setUp(self):
        translation.activate("fr")
        self.media = tempfile.mkdtemp()
        self.override = override_settings(MEDIA_ROOT=self.media)
        self.override.enable()
        self.admin = make_user("admin@example.com", Role.ADMIN)
        self.client.force_login(self.admin)

    def tearDown(self):
        self.override.disable()
        shutil.rmtree(self.media, ignore_errors=True)

    def post(self, pk=None, **data):
        url = reverse("panel:destination_edit", args=[pk]) if pk else reverse("panel:destination_create")
        base = {"name_fr": "Rome", "name_en": "", "name_ar": "روما", "position": "5",
                "activities_fr": "Le Colisée\nLa fontaine de Trevi", "activities_en": "", "activities_ar": "الكولوسيوم\nنافورة تريفي"}
        base.update(data)
        return self.client.post(url, base)

    def test_admin_adds_destination_with_photo_and_activities(self):
        response = self.post(photo=image_upload())
        self.assertRedirects(response, reverse("panel:destinations"))
        rome = Destination.objects.get(name_fr="Rome")
        self.assertEqual([(a.text_fr, a.text_ar) for a in rome.activities.all()], [("Le Colisée", "الكولوسيوم"), ("La fontaine de Trevi", "نافورة تريفي")])
        with rome.photo.open("rb") as f, Image.open(f) as img:
            self.assertEqual((img.format, img.size), ("JPEG", (1200, 900)))
        self.assertTrue(AuditLog.objects.filter(action="destination.create").exists())
        member = make_user("member@example.com")
        self.client.force_login(member)
        self.assertEqual(self.client.get(reverse("destinations:photo", args=[rome.pk])).status_code, 200)

    def test_editing_replaces_activities_and_old_photo(self):
        self.post(photo=image_upload())
        rome = Destination.objects.get(name_fr="Rome")
        old = rome.photo.name
        self.post(pk=rome.pk, photo=image_upload((800, 1600)), activities_fr="Le Vatican", activities_ar="")
        rome.refresh_from_db()
        self.assertEqual([a.text_fr for a in rome.activities.all()], ["Le Vatican"])
        self.assertNotEqual(rome.photo.name, old)
        self.assertFalse(rome.photo.storage.exists(old))

    def test_line_counts_must_match(self):
        response = self.post(activities_ar="الكولوسيوم")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Destination.objects.filter(name_fr="Rome").exists())

    def test_delete_removes_photo(self):
        self.post(photo=image_upload())
        rome = Destination.objects.get(name_fr="Rome")
        name = rome.photo.name
        self.client.post(reverse("panel:destination_delete", args=[rome.pk]))
        self.assertFalse(Destination.objects.filter(pk=rome.pk).exists())
        self.assertFalse(rome.photo.storage.exists(name))

    def test_members_cannot_manage(self):
        self.client.force_login(make_user("member@example.com"))
        self.assertEqual(self.client.get(reverse("panel:destinations")).status_code, 403)
        self.assertEqual(self.post().status_code, 403)
