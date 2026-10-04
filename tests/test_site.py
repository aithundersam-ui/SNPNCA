from django.core import mail
from django.core.cache import cache
from django.core.files.base import ContentFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import translation

from accounts import csv_import
from accounts.models import Role, User
from core.forms import ContactForm
from core.models import ContactMessage, SiteContent
from news.models import Article, embed_url

from .helpers import make_user, media_settings


class LanguageTests(TestCase):
    def test_root_defaults_to_french_even_for_english_browsers(self):
        response = self.client.get("/", HTTP_ACCEPT_LANGUAGE="en-US,en")
        self.assertEqual(response["Location"], "/fr/")

    def test_language_urls_and_switcher_remember_choice_per_user(self):
        user = make_user("m@example.com")
        self.client.force_login(user)
        response = self.client.post("/fr/account/language/", {"language": "en", "next": "/fr/news/"})
        self.assertEqual(response["Location"], "/en/news/")
        user.refresh_from_db()
        self.assertEqual(user.preferred_language, "en")
        self.assertContains(self.client.get("/en/news/"), 'lang="en"')

    def test_bilingual_content_falls_back_to_other_language(self):
        content = SiteContent.load()
        content.description_fr = "Description en français"
        content.description_en = ""
        content.save()
        with translation.override("en"):
            self.assertEqual(content.localized("description"), "Description en français")
        self.assertContains(self.client.get("/en/"), "Description en français")


class AuthTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = make_user("member@example.com", preferred_language="en")

    def test_login_redirects_to_preferred_language(self):
        response = self.client.post("/fr/account/login/", {"email": "member@example.com", "password": "Correct-horse-42"})
        self.assertEqual(response["Location"], "/en/")

    def test_lockout_after_repeated_failures(self):
        for _ in range(5):
            self.client.post("/fr/account/login/", {"email": "member@example.com", "password": "wrong"})
        response = self.client.post("/fr/account/login/", {"email": "member@example.com", "password": "Correct-horse-42"})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_passwords_are_hashed_with_argon2(self):
        self.assertTrue(self.user.password.startswith("argon2"))

    def test_invitation_link_lets_new_member_set_password(self):
        admin = make_user("admin@example.com", Role.ADMIN)
        self.client.force_login(admin)
        self.client.post(reverse("panel:user_create"), {"full_name": "Yasmine", "email": "y@example.com", "preferred_language": "fr", "is_active": "on"})
        self.client.logout()
        self.assertEqual(len(mail.outbox), 1)
        body = mail.outbox[0].body
        self.assertNotIn("password:", body.lower())
        link = next(line for line in body.splitlines() if "/set-password/" in line).strip()
        path = link.split("http://localhost:8000", 1)[-1]
        response = self.client.get(path, follow=True)
        form_url = response.redirect_chain[-1][0]
        self.client.post(form_url, {"new_password1": "Une-phrase-solide-91", "new_password2": "Une-phrase-solide-91"})
        self.assertTrue(User.objects.get(email="y@example.com").check_password("Une-phrase-solide-91"))

    def test_password_reset_email_for_invited_member(self):
        User.objects.create_user(email="pending@example.com", full_name="Pending")
        self.client.post("/en/account/password-reset/", {"email": "pending@example.com"})
        self.assertEqual(len(mail.outbox), 1)


@override_settings(CONTACT_NOTIFY_EMAIL="office@example.com")
class ContactTests(TestCase):
    def setUp(self):
        cache.clear()

    def _data(self, **extra):
        form = ContactForm()
        data = {"full_name": "Karim", "email": "k@example.com", "phone": "+213 555 12 34 56", "message": "Bonjour, je voudrais adhérer.", "ts": form.initial["ts"], "website": ""}
        data.update(extra)
        return data

    def test_valid_message_is_saved_and_emailed(self):
        from unittest import mock

        with mock.patch("core.forms.MIN_FILL_SECONDS", 0):
            response = self.client.post("/fr/", self._data())
        self.assertEqual(response.status_code, 302)
        self.assertEqual(ContactMessage.objects.count(), 1)
        self.assertEqual(mail.outbox[0].to, ["office@example.com"])

    def test_honeypot_submissions_are_dropped(self):
        from unittest import mock

        with mock.patch("core.forms.MIN_FILL_SECONDS", 0):
            self.client.post("/fr/", self._data(website="http://spam"))
        self.assertEqual(ContactMessage.objects.count(), 0)

    def test_all_fields_are_required(self):
        response = self.client.post("/fr/", {"ts": self._data()["ts"]})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["form"].errors), 4)

    def test_admin_reply_is_emailed_and_marks_replied(self):
        msg = ContactMessage.objects.create(full_name="K", email="k@example.com", phone="0555123456", message="Question")
        self.client.force_login(make_user("admin@example.com", Role.ADMIN))
        self.client.post(reverse("panel:message_detail", args=[msg.pk]), {"body": "Merci pour votre message."})
        msg.refresh_from_db()
        self.assertEqual(msg.status, ContactMessage.Status.REPLIED)
        self.assertEqual(mail.outbox[-1].to, ["k@example.com"])


class CsvImportTests(TestCase):
    def test_preview_rules(self):
        admin = make_user("admin@example.com", Role.ADMIN)
        make_user("exists@example.com")
        text = (
            "full_name,email,language,role\n"
            "Amélie Ünal,amelie@example.com,fr,admin\n"
            "Existing,exists@example.com,fr,\n"
            ",bad-email,de,\n"
            "Dup,amelie@example.com,en,\n"
        )
        rows = csv_import.parse(text, admin)
        self.assertTrue(rows[0].ok)
        self.assertEqual(rows[0].role, "user")  # role ignored for a normal admin
        self.assertTrue(rows[0].warnings)
        self.assertTrue(rows[1].skip)
        self.assertEqual(len(rows[2].errors), 3)
        self.assertTrue(rows[3].errors)

    def test_master_import_honours_role_and_keeps_accents(self):
        master = make_user("master@example.com", Role.MASTER)
        raw = "full_name,email,role\nAmélie Ünal,amelie@example.com,admin\n".encode("utf-8-sig")
        rows = csv_import.parse(csv_import.decode(raw), master)
        created = csv_import.apply([r.as_dict() for r in rows if r.ok], master)
        self.assertEqual(created[0].full_name, "Amélie Ünal")
        self.assertEqual(created[0].role, Role.ADMIN)

    def test_non_utf8_file_is_rejected(self):
        with self.assertRaises(csv_import.CsvFormatError):
            csv_import.decode("full_name,email\nAmélie,a@example.com".encode("latin-1"))

    def test_full_flow_through_panel_sends_invitations(self):
        self.client.force_login(make_user("admin@example.com", Role.ADMIN))
        csv_file = ContentFile("full_name,email\nA One,a1@example.com\nB Two,b2@example.com\n".encode(), name="m.csv")
        response = self.client.post(reverse("panel:csv_upload"), {"file": csv_file})
        self.assertContains(response, "a1@example.com")
        self.client.post(reverse("panel:csv_apply"))
        self.assertEqual(User.objects.filter(email__in=["a1@example.com", "b2@example.com"]).count(), 2)
        self.assertEqual(len(mail.outbox), 2)


@media_settings()
class NewsTests(TestCase):
    def test_video_links_are_restricted_to_youtube_and_vimeo(self):
        self.assertEqual(embed_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ"), "https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ")
        self.assertEqual(embed_url("https://vimeo.com/123456789"), "https://player.vimeo.com/video/123456789")
        self.assertIsNone(embed_url("https://evil.example.com/video"))

    def test_article_with_only_english_shows_on_french_site(self):
        article = Article.objects.create(title_en="Only English", body_en="Body")
        self.client.force_login(make_user("m@example.com"))
        self.assertContains(self.client.get(f"/fr/news/{article.pk}/"), "Only English")

    def test_news_images_are_not_public(self):
        import io

        from PIL import Image

        admin = make_user("admin@example.com", Role.ADMIN)
        self.client.force_login(admin)
        buf = io.BytesIO()
        Image.new("RGB", (20, 20), "navy").save(buf, "PNG")
        img = ContentFile(buf.getvalue(), name="p.png")
        self.client.post(reverse("panel:news_create"), {"title_fr": "Titre", "body_fr": "Texte", "published_at": "2026-01-01T10:00", "is_published": "on", "new_images": [img], "video_urls": ""})
        image = Article.objects.get().images.get()
        url = reverse("core:media", args=[image.image.name])
        self.client.logout()
        self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(make_user("m@example.com"))
        self.assertEqual(self.client.get(url).status_code, 200)


class RedesignPageTests(TestCase):
    def test_home_shows_reference_text_in_both_languages(self):
        fr = self.client.get("/fr/")
        self.assertContains(fr, "Notre Mission")
        self.assertContains(fr, "défend les droits")
        self.assertContains(fr, "Envoyer le Message")
        en = self.client.get("/en/")
        self.assertContains(en, "Our Mission")
        self.assertContains(en, "Algerian flight attendants")

    def test_documents_page_lists_only_ready_documents_for_members(self):
        from qa.models import Document

        self.assertEqual(self.client.get("/fr/qa/documents/").status_code, 302)
        Document.objects.create(title="Convention collective", file="docs/a.pdf", original_filename="a.pdf", status=Document.Status.READY)
        Document.objects.create(title="Brouillon", file="docs/b.pdf", original_filename="b.pdf", status=Document.Status.PENDING)
        self.client.force_login(make_user("m@example.com"))
        response = self.client.get("/fr/qa/documents/")
        self.assertContains(response, "Convention collective")
        self.assertNotContains(response, "Brouillon")
