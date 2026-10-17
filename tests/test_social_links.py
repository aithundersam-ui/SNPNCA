from django.test import TestCase
from django.urls import reverse
from django.utils import translation

from accounts.models import AuditLog, Role
from core.models import SiteContent

from .helpers import make_user


class SocialLinksTests(TestCase):
    def setUp(self):
        translation.activate("fr")

    def test_seeded_links_in_footer_of_every_page(self):
        for url in ("/fr/", "/en/account/login/", "/ar/team/"):
            response = self.client.get(url)
            self.assertContains(response, 'href="https://www.facebook.com/share/1CbdB3dM1j/" target="_blank" rel="noopener noreferrer"')
            self.assertContains(response, 'href="https://www.instagram.com/snpnca/"')
            self.assertContains(response, 'class="footer-copy"')

    def test_empty_link_hides_its_button_and_both_hide_the_section(self):
        SiteContent.objects.filter(pk=1).update(facebook_url="")
        response = self.client.get("/fr/")
        self.assertNotContains(response, "social-btn facebook")
        self.assertContains(response, "social-btn instagram")
        SiteContent.objects.filter(pk=1).update(instagram_url="")
        self.assertNotContains(self.client.get("/fr/"), "footer-social")

    def test_master_admin_changes_links(self):
        self.client.force_login(make_user("master@example.com", Role.MASTER))
        self.assertContains(self.client.get(reverse("panel:home_content")), 'name="instagram_url"')
        response = self.client.post(reverse("panel:social_links"), {
            "facebook_url": "https://www.facebook.com/snpnca.dz", "instagram_url": "https://www.instagram.com/snpnca_dz/",
        })
        self.assertRedirects(response, reverse("panel:home_content"))
        content = SiteContent.load()
        self.assertEqual((content.facebook_url, content.instagram_url), ("https://www.facebook.com/snpnca.dz", "https://www.instagram.com/snpnca_dz/"))
        self.assertTrue(AuditLog.objects.filter(action="home.social_links").exists())

    def test_wrong_sites_rejected(self):
        self.client.force_login(make_user("master@example.com", Role.MASTER))
        for fb, ig in [("https://evil.example/fb", ""), ("", "https://www.facebook.com/x"), ("http://www.facebook.com/x", ""),
                       ("javascript:alert(1)", ""), ("https://www.facebook.com.evil.example/", "")]:
            response = self.client.post(reverse("panel:social_links"), {"facebook_url": fb, "instagram_url": ig})
            self.assertEqual(response.status_code, 200, (fb, ig))
        self.assertEqual(SiteContent.load().facebook_url, "https://www.facebook.com/share/1CbdB3dM1j/")

    def test_only_master_admin(self):
        self.client.force_login(make_user("admin@example.com", Role.ADMIN))
        self.assertNotContains(self.client.get(reverse("panel:home_content")), 'name="instagram_url"')
        response = self.client.post(reverse("panel:social_links"), {"facebook_url": "", "instagram_url": ""})
        self.assertEqual(response.status_code, 403)
