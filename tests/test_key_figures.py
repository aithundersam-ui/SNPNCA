from django.test import TestCase
from django.urls import reverse
from django.utils import translation

from accounts.models import AuditLog, Role
from core.models import KeyFigure

from .helpers import make_user


def formset_data(rows, initial=0):
    data = {"fig-TOTAL_FORMS": str(len(rows)), "fig-INITIAL_FORMS": str(initial), "fig-MIN_NUM_FORMS": "0", "fig-MAX_NUM_FORMS": "4"}
    for i, row in enumerate(rows):
        data.update({f"fig-{i}-{k}": v for k, v in row.items()})
    return data


class KeyFiguresTests(TestCase):
    def setUp(self):
        translation.activate("fr")

    def test_seeded_figures_on_home_page_above_mission(self):
        html = self.client.get("/fr/").content.decode()
        self.assertIn('data-count="700" data-suffix="+"', html)
        self.assertIn("PNC affiliés", html)
        self.assertIn("Villes", html)
        self.assertLess(html.index("key-figures"), html.index('id="mission"'))
        self.assertIn("Affiliated cabin crew", self.client.get("/en/").content.decode())
        self.assertIn("مدن", self.client.get("/ar/").content.decode())

    def test_no_section_without_figures(self):
        KeyFigure.objects.all().delete()
        self.assertNotContains(self.client.get("/fr/"), "key-figures")

    def test_master_edits_figures(self):
        master = make_user("master@example.com", Role.MASTER)
        self.client.force_login(master)
        self.assertContains(self.client.get(reverse("panel:home_content")), "Chiffres clés")
        crew, cities = KeyFigure.objects.order_by("position")
        rows = [
            {"id": str(crew.pk), "icon": "users", "value": "750", "suffix": "+", "label_fr": "PNC affiliés", "label_en": "", "label_ar": "", "position": "0"},
            {"id": str(cities.pk), "icon": "map-pin", "value": "5", "suffix": "", "label_fr": "Villes", "label_en": "", "label_ar": "", "position": "1", "DELETE": "on"},
            {"icon": "plane", "value": "12", "suffix": "", "label_fr": "Escales", "label_en": "", "label_ar": "", "position": "2"},
        ]
        response = self.client.post(reverse("panel:key_figures"), formset_data(rows, initial=2))
        self.assertRedirects(response, reverse("panel:home_content"))
        self.assertEqual([str(f) for f in KeyFigure.objects.all()], ["750+ PNC affiliés", "12 Escales"])
        self.assertTrue(AuditLog.objects.filter(action="home.key_figures").exists())

    def test_regular_admin_cannot_edit_figures(self):
        admin = make_user("admin@example.com", Role.ADMIN)
        self.client.force_login(admin)
        self.assertNotContains(self.client.get(reverse("panel:home_content")), "Chiffres clés")
        response = self.client.post(reverse("panel:key_figures"), formset_data([]))
        self.assertEqual(response.status_code, 403)


class FooterTests(TestCase):
    def test_copyright_on_every_kind_of_page(self):
        for url, words in [("/fr/", "Tous droits réservés"), ("/en/account/login/", "All rights reserved"), ("/ar/team/", "جميع الحقوق محفوظة")]:
            self.assertContains(self.client.get(url), f"{words} - <bdi>Copyright © 2026 - SNPNCA 🇩🇿</bdi>")
        self.client.force_login(make_user("master@example.com", Role.MASTER))
        self.assertContains(self.client.get(reverse("panel:home_content")), "Copyright © 2026 - SNPNCA")
