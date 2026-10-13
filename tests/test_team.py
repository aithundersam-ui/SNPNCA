import io

from django.core.files.base import ContentFile
from django.test import TestCase
from django.urls import reverse
from django.utils import translation

from accounts.models import AuditLog, Role
from core.models import ContactMessage
from team.models import TeamMember

from .helpers import make_user, media_settings


def png(name="p.png"):
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (30, 30), "navy").save(buf, "PNG")
    return ContentFile(buf.getvalue(), name=name)


@media_settings()
class TeamPageTests(TestCase):
    def setUp(self):
        translation.activate("fr")

    def test_public_page_lists_bureau_in_hierarchy_order(self):
        response = self.client.get(reverse("team:page"))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        order = [html.index(n) for n in ["Bouzourene Fodil", "Zouane Fouad Eddine", "Driche Chakib", "Benabed Daiem Youcef", "Nachi Walid", "Aougabi Mouad Mohamed Amine"]]
        self.assertEqual(order, sorted(order))
        self.assertContains(response, "Président")
        self.assertContains(response, "BF")  # initials until a photo is uploaded
        self.assertContains(self.client.get("/fr/"), reverse("team:page"))

    def test_contact_button_addresses_the_message(self):
        president = TeamMember.objects.get(role="president")
        page = self.client.get(reverse("core:home") + f"?to={president.pk}")
        self.assertContains(page, "Bouzourene Fodil")
        self.client.post(reverse("core:home"), {
            "full_name": "Visiteur", "email": "v@example.com", "phone": "+213 550 12 34 56",
            "message": "Bonjour, je voudrais adhérer.", "recipient": president.pk,
            "ts": "x",  # flagged as spam by the timing check, so nothing is stored
        })
        self.assertEqual(ContactMessage.objects.count(), 0)
        form_ts = page.context["form"].initial["ts"]
        import time
        from unittest import mock
        with mock.patch("core.forms.time.time", return_value=time.time() + 10):
            self.client.post(reverse("core:home"), {
                "full_name": "Visiteur", "email": "v@example.com", "phone": "+213 550 12 34 56",
                "message": "Bonjour, je voudrais adhérer.", "recipient": president.pk, "ts": form_ts,
            })
        self.assertEqual(ContactMessage.objects.get().recipient, president)

    def test_whatsapp_button_only_when_number_set(self):
        self.assertNotContains(self.client.get(reverse("team:page")), "wa.me")
        p = TeamMember.objects.get(role="treasurer")
        p.whatsapp_number = "0550 12 34 56"
        p.save()
        self.assertContains(self.client.get(reverse("team:page")), "https://wa.me/213550123456")


@media_settings()
class TeamAdminTests(TestCase):
    def setUp(self):
        translation.activate("fr")
        self.master = make_user("master@example.com", Role.MASTER)
        self.admin = make_user("admin@example.com", Role.ADMIN)

    def test_only_master_admin_manages_the_team(self):
        self.client.force_login(self.admin)
        person = TeamMember.objects.first()
        self.assertEqual(self.client.get(reverse("panel:team")).status_code, 403)
        self.assertEqual(self.client.post(reverse("panel:team_create"), {"full_name": "X", "role": "member", "position": 0}).status_code, 403)
        self.assertEqual(self.client.post(reverse("panel:team_delete", args=[person.pk])).status_code, 403)
        self.assertNotContains(self.client.get(reverse("panel:dashboard")), reverse("panel:team"))
        self.assertEqual(TeamMember.objects.count(), 6)

    def test_master_adds_photo_edits_and_deletes(self):
        self.client.force_login(self.master)
        self.client.post(reverse("panel:team_create"), {"full_name": "Nouvelle Personne", "role": "member", "position": 9, "photo": png()})
        person = TeamMember.objects.get(full_name="Nouvelle Personne")
        self.assertTrue(person.photo.name.startswith("team/"))
        self.assertEqual(self.client.get(reverse("team:photo", args=[person.pk])).status_code, 200)
        old = person.photo.name
        self.client.post(reverse("panel:team_edit", args=[person.pk]), {"full_name": "Nouvelle Personne", "role": "treasurer", "position": 0, "photo": png("b.png")})
        person.refresh_from_db()
        self.assertEqual(person.rank, 2)
        self.assertFalse(person.photo.storage.exists(old))
        self.client.post(reverse("panel:team_delete", args=[person.pk]))
        self.assertFalse(TeamMember.objects.filter(pk=person.pk).exists())
        self.assertTrue(AuditLog.objects.filter(action="team.delete").exists())

    def test_bad_photo_and_number_rejected(self):
        self.client.force_login(self.master)
        self.client.post(reverse("panel:team_create"), {"full_name": "A", "role": "member", "position": 0, "photo": ContentFile(b"nope", name="x.png")})
        self.client.post(reverse("panel:team_create"), {"full_name": "B", "role": "member", "position": 0, "whatsapp_number": "123"})
        self.assertFalse(TeamMember.objects.filter(full_name__in=["A", "B"]).exists())


def crew_portrait():
    """A real face to detect: one crew member cut from the home page photo, with lots of background."""
    from django.conf import settings
    from PIL import Image

    img = Image.open(settings.BASE_DIR / "static" / "img" / "hero-crew.jpg").crop((470, 40, 910, 700))
    buf = io.BytesIO()
    img.save(buf, "JPEG")
    return ContentFile(buf.getvalue(), name="portrait.jpg")


@media_settings()
class FaceCropTests(TestCase):
    def setUp(self):
        translation.activate("fr")
        self.client.force_login(make_user("master@example.com", Role.MASTER))

    def test_uploaded_portrait_is_cropped_square_on_the_face(self):
        from PIL import Image

        from team.faces import find_face

        response = self.client.post(reverse("panel:team_create"), {"full_name": "Test Visage", "role": "member", "position": 5, "photo": crew_portrait()}, follow=True)
        person = TeamMember.objects.get(full_name="Test Visage")
        self.assertTrue(person.photo_crop)
        self.assertNotContains(response, "Aucun visage")
        with person.photo_crop.open("rb") as f:
            crop = Image.open(f)
            crop.load()
        self.assertEqual(crop.width, crop.height)
        with person.photo.open("rb") as f:
            original = Image.open(f)
            original.load()
        self.assertEqual(original.size, (440, 660))  # original kept as uploaded
        face = find_face(crop)
        self.assertIsNotNone(face)
        x, y, w, h = face
        self.assertLess(abs((x + w / 2) - crop.width / 2), crop.width * 0.15)  # face is centred
        self.assertGreater(h, crop.height * 0.25)  # and zoomed in
        served = self.client.get(reverse("team:photo", args=[person.pk]))
        self.assertEqual(served["Content-Type"], "image/jpeg")

    def test_photo_without_face_falls_back_and_warns(self):
        response = self.client.post(reverse("panel:team_create"), {"full_name": "Sans Visage", "role": "member", "position": 5, "photo": png()}, follow=True)
        self.assertContains(response, "Aucun visage")
        self.assertTrue(TeamMember.objects.get(full_name="Sans Visage").photo_crop)

    def test_replacing_or_deleting_removes_old_files(self):
        self.client.post(reverse("panel:team_create"), {"full_name": "Z", "role": "member", "position": 5, "photo": png()})
        person = TeamMember.objects.get(full_name="Z")
        storage, first = person.photo.storage, [person.photo.name, person.photo_crop.name]
        self.client.post(reverse("panel:team_edit", args=[person.pk]), {"full_name": "Z", "role": "member", "position": 5, "photo": crew_portrait()})
        person.refresh_from_db()
        self.assertFalse(any(storage.exists(n) for n in first))
        current = [person.photo.name, person.photo_crop.name]
        self.client.post(reverse("panel:team_delete", args=[person.pk]))
        self.assertFalse(any(storage.exists(n) for n in current))
