import io
import shutil
import tempfile

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import translation
from PIL import Image

from accounts.models import AuditLog, Role
from destinations.models import Activity, Destination, validate_maps_url

from .helpers import make_user

MAPS = "https://maps.app.goo.gl/abc123"


def image_upload(size=(2000, 1000)):
    buf = io.BytesIO()
    Image.new("RGB", size, (30, 90, 200)).save(buf, "PNG")
    return SimpleUploadedFile("beach.png", buf.getvalue(), content_type="image/png")


class MapsLinkTests(SimpleTestCase):
    def test_google_maps_links_accepted(self):
        for url in (MAPS, "https://www.google.com/maps/place/Colosseum", "https://www.google.fr/maps/@41.89,12.49,15z",
                    "https://maps.google.com/?q=Rome", "https://goo.gl/maps/xyz"):
            validate_maps_url(url)

    def test_other_links_rejected(self):
        for url in ("http://maps.app.goo.gl/abc", "https://evil.example/maps", "https://www.google.com/search?q=x",
                    "https://maps.app.goo.gl.evil.example/x", "javascript:alert(1)"):
            with self.assertRaises(ValidationError, msg=url):
                validate_maps_url(url)


class DestinationPageTests(TestCase):
    def setUp(self):
        translation.activate("fr")
        self.member = make_user("member@example.com")

    def test_members_only(self):
        istanbul = Destination.objects.get(name_fr="Istanbul")
        for url in (reverse("destinations:list"), istanbul.get_absolute_url()):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 302)
            self.assertIn(reverse("accounts:login"), response["Location"])

    def test_cards_link_to_their_page(self):
        self.client.force_login(self.member)
        istanbul = Destination.objects.get(name_fr="Istanbul")
        response = self.client.get(reverse("destinations:list"))
        self.assertContains(response, 'class="dest-card"', count=3)
        self.assertContains(response, f'href="/fr/destinations/{istanbul.pk}/"')
        self.assertNotContains(response, "<details")
        self.assertContains(response, 'href="/fr/destinations/"')  # menu link

    def test_detail_page_in_each_language(self):
        self.client.force_login(self.member)
        istanbul = Destination.objects.get(name_fr="Istanbul")
        cruise = istanbul.activities.get(title_fr="Croisière sur le Bosphore")
        response = self.client.get(istanbul.get_absolute_url())
        self.assertContains(response, "Croisière sur le Bosphore")
        self.assertContains(response, cruise.description_fr[:30])
        self.assertContains(response, 'target="_blank" rel="noopener noreferrer"')
        self.assertContains(response, "https://www.google.com/maps/search/")
        self.assertContains(self.client.get(f"/en/destinations/{istanbul.pk}/"), "Take a Bosphorus cruise")
        self.assertContains(self.client.get(f"/ar/destinations/{istanbul.pk}/"), "رحلة بحرية في مضيق البوسفور")

    def test_arabic_falls_back_to_french(self):
        d = Destination.objects.create(name_fr="Alger", position=9)
        d.activities.create(title_fr="La Casbah", description_fr="Ruelles historiques.")
        self.client.force_login(self.member)
        response = self.client.get(f"/ar/destinations/{d.pk}/")
        self.assertContains(response, "Alger")
        self.assertContains(response, "Ruelles historiques.")
        self.assertNotContains(response, "act-map")  # no link given, no button

    def test_unknown_destination(self):
        self.client.force_login(self.member)
        self.assertEqual(self.client.get(reverse("destinations:detail", args=[999])).status_code, 404)


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

    def post(self, pk=None, activities=(), initial=0, **data):
        url = reverse("panel:destination_edit", args=[pk]) if pk else reverse("panel:destination_create")
        base = {"name_fr": "Rome", "name_en": "", "name_ar": "روما", "position": "5",
                "act-TOTAL_FORMS": str(len(activities)), "act-INITIAL_FORMS": str(initial),
                "act-MIN_NUM_FORMS": "0", "act-MAX_NUM_FORMS": "15"}
        for i, act in enumerate(activities):
            fields = {"title_fr": "", "title_en": "", "title_ar": "", "description_fr": "", "description_en": "",
                      "description_ar": "", "maps_url": "", "position": str(i)}
            fields.update(act)
            base.update({f"act-{i}-{k}": v for k, v in fields.items()})
        base.update(data)
        return self.client.post(url, base)

    def colosseum(self, **extra):
        return {"title_fr": "Le Colisée", "title_ar": "الكولوسيوم", "description_fr": "L'amphithéâtre antique.",
                "maps_url": MAPS, "photo": image_upload(), **extra}

    def test_admin_adds_destination_with_activity_photo(self):
        response = self.post(photo=image_upload(), activities=[self.colosseum(), {"position": "0"}])  # untouched empty block
        self.assertRedirects(response, reverse("panel:destinations"))
        rome = Destination.objects.get(name_fr="Rome")
        activity = rome.activities.get()
        self.assertEqual((activity.title_ar, activity.maps_url), ("الكولوسيوم", MAPS))
        for obj in (rome, activity):
            with obj.photo.open("rb") as f, Image.open(f) as img:
                self.assertEqual((img.format, img.size), ("JPEG", (1200, 900)))
        self.assertTrue(AuditLog.objects.filter(action="destination.create").exists())
        self.client.force_login(make_user("member@example.com"))
        self.assertEqual(self.client.get(reverse("destinations:activity_photo", args=[activity.pk])).status_code, 200)
        self.assertContains(self.client.get(rome.get_absolute_url()), reverse("destinations:activity_photo", args=[activity.pk]))

    def test_form_shows_activity_blocks(self):
        response = self.client.get(reverse("panel:destination_create"))
        self.assertContains(response, 'name="act-0-maps_url"')
        self.assertContains(response, 'enctype="multipart/form-data"')

    def test_non_google_link_rejected(self):
        response = self.post(activities=[self.colosseum(maps_url="https://evil.example/maps")])
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Destination.objects.filter(name_fr="Rome").exists())

    def test_replace_and_delete_activity_photos(self):
        self.post(activities=[self.colosseum()])
        rome = Destination.objects.get(name_fr="Rome")
        activity = rome.activities.get()
        old = activity.photo.name
        self.post(pk=rome.pk, initial=1, activities=[{"id": str(activity.pk), "title_fr": "Le Colisée", "photo": image_upload((800, 1600))}])
        activity.refresh_from_db()
        self.assertNotEqual(activity.photo.name, old)
        self.assertFalse(activity.photo.storage.exists(old))
        current = activity.photo.name
        self.post(pk=rome.pk, initial=1, activities=[{"id": str(activity.pk), "title_fr": "Le Colisée", "DELETE": "on"}])
        self.assertFalse(Activity.objects.filter(pk=activity.pk).exists())
        self.assertFalse(activity.photo.storage.exists(current))

    def test_delete_destination_removes_all_photos(self):
        self.post(photo=image_upload(), activities=[self.colosseum()])
        rome = Destination.objects.get(name_fr="Rome")
        names = [rome.photo.name, rome.activities.get().photo.name]
        self.client.post(reverse("panel:destination_delete", args=[rome.pk]))
        self.assertFalse(Destination.objects.filter(pk=rome.pk).exists())
        for name in names:
            self.assertFalse(rome.photo.storage.exists(name))

    def test_members_cannot_manage(self):
        self.client.force_login(make_user("member@example.com"))
        self.assertEqual(self.client.get(reverse("panel:destinations")).status_code, 403)
        self.assertEqual(self.post().status_code, 403)
