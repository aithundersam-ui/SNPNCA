from datetime import timedelta

from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone, translation

from accounts.models import Role
from alerts.models import Alert
from core.models import SiteContent
from news.models import Article
from polls.models import Poll
from qa import assistant

from .helpers import make_user


class ArabicPagesTests(TestCase):
    def test_arabic_pages_are_right_to_left(self):
        response = self.client.get("/ar/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<html lang="ar" dir="rtl">')
        self.assertContains(response, "صوت طاقم الضيافة الجزائري")

    def test_french_pages_stay_left_to_right(self):
        self.assertContains(self.client.get("/fr/"), '<html lang="fr" dir="ltr">')

    def test_language_switch_offers_arabic_and_saves_it(self):
        member = make_user("member@example.com")
        self.client.force_login(member)
        self.assertContains(self.client.get("/fr/"), 'value="ar"')
        response = self.client.post(reverse("accounts:set_language"), {"language": "ar", "next": "/fr/news/"})
        self.assertRedirects(response, "/ar/news/", fetch_redirect_response=False)
        member.refresh_from_db()
        self.assertEqual(member.preferred_language, "ar")

    def test_arabic_text_falls_back_to_french_then_english(self):
        article = Article(title_fr="Grève", title_en="Strike", title_ar="")
        with translation.override("ar"):
            self.assertEqual(article.localized("title"), "Grève")
            article.title_ar = "إضراب"
            self.assertEqual(article.localized("title"), "إضراب")
            article.title_fr = ""
            self.assertEqual(Article(title_en="Strike").localized("title"), "Strike")
        with translation.override("fr"):
            self.assertEqual(article.localized("title"), "Strike")

    def test_home_text_in_arabic(self):
        SiteContent.objects.update_or_create(pk=1, defaults={"description_fr": "Texte FR", "description_ar": "نص عربي"})
        self.assertContains(self.client.get("/ar/"), "نص عربي")
        self.assertContains(self.client.get("/fr/"), "Texte FR")


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class ArabicContentTests(TestCase):
    def setUp(self):
        translation.activate("fr")
        self.admin = make_user("admin@example.com", Role.ADMIN)
        self.ar_member = make_user("ar@example.com", preferred_language="ar", whatsapp_number="+213550000002")

    def test_alert_is_emailed_in_arabic(self):
        self.client.force_login(self.admin)
        self.client.post(reverse("panel:alert_create"), {
            "title_fr": "Préavis de grève", "title_ar": "إشعار بالإضراب", "body_fr": "Grève le 1er mai.",
            "body_ar": "إضراب يوم 1 ماي.", "show_days": "7", "send_email": "on",
        })
        alert = Alert.objects.get()
        sent = {m.to[0]: m for m in mail.outbox}
        self.assertIn("إشعار بالإضراب", sent["ar@example.com"].subject)
        self.assertIn("/ar/alerts/", sent["ar@example.com"].body)
        self.assertIn("Préavis de grève", sent["admin@example.com"].subject)
        self.assertIn("%D8%A5%D8%B4%D8%B9%D8%A7%D8%B1", alert.whatsapp_link_for(self.ar_member))

    def test_alert_without_arabic_uses_french_for_arabic_readers(self):
        alert = Alert.objects.create(title_fr="Préavis", body_fr="Texte", show_until=timezone.now() + timedelta(days=1))
        self.assertEqual(alert.text_in("ar"), ("Préavis", "Texte"))

    def test_alert_needs_french_or_english(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse("panel:alert_create"), {"title_ar": "عنوان", "body_ar": "نص", "show_days": "7"})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Alert.objects.exists())

    def test_admin_fields_for_arabic_are_right_to_left(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("panel:alert_create"))
        self.assertContains(response, 'dir="rtl"')

    def test_poll_with_arabic_answers(self):
        now = timezone.now()
        self.client.force_login(self.admin)
        base = {
            "category": Poll.Category.STRIKE, "title_fr": "Grève ?", "title_ar": "إضراب؟",
            "opens_at": (now - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M"),
            "closes_at": (now + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M"),
            "choices_fr": "Oui\nNon",
        }
        response = self.client.post(reverse("panel:poll_create"), {**base, "choices_ar": "نعم"})
        self.assertEqual(response.status_code, 200)
        self.client.post(reverse("panel:poll_create"), {**base, "choices_ar": "نعم\nلا"})
        poll = Poll.objects.get()
        self.assertEqual([c.text_ar for c in poll.choices.all()], ["نعم", "لا"])
        self.client.force_login(self.ar_member)
        response = self.client.get(reverse("polls:detail", args=[poll.pk]).replace("/fr/", "/ar/"))
        self.assertContains(response, "إضراب؟")
        self.assertContains(response, "لا")


class ArabicAssistantTests(TestCase):
    def test_arabic_question_gets_arabic_reply_language(self):
        class FakeLLM:
            def plan(self, question):
                return {"language": "ar", "keywords_fr": ["congé"], "keywords_en": ["leave"], "keywords_ar": ["إجازة"]}

        answer = assistant.ask("ما هي مدة الإجازة؟", ui_language="fr", llm=FakeLLM())
        self.assertEqual(answer.language, "ar")
