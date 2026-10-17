import json
from unittest import mock

from django.test import TestCase
from django.urls import reverse
from django.utils import translation

from accounts.models import Role
from alerts.models import Alert
from destinations.models import Destination
from news.models import Article
from polls.models import Poll
from qa.llm import LLMError

from .helpers import make_user

WORDS = {
    "Grève le 1er mai": {"en": "Strike on 1 May", "ar": "إضراب يوم 1 ماي"},
    "Préavis de grève": {"en": "Strike notice", "ar": "إشعار بالإضراب"},
    "Rome": {"en": "Rome", "ar": "روما"},
    "Oui\nNon": {"en": "Yes\nNo", "ar": "نعم\nلا"},
    "إضراب؟": {"fr": "Grève ?", "en": "Strike?"},
}


class FakeLLM:
    def __init__(self):
        self.calls = []

    def translate(self, system, content, schema):
        items = json.loads(content)
        self.calls.append(items)
        out = {}
        for key, item in items.items():
            text = next(iter(item["source"].values()))
            out[key] = {lang: WORDS.get(text, {}).get(lang, f"[{lang}] {text}") for lang in item["translate_to"]}
        return out


class BrokenLLM:
    def translate(self, *args):
        raise LLMError("no key")


class AutoTranslateTests(TestCase):
    def setUp(self):
        translation.activate("fr")
        self.llm = FakeLLM()
        patcher = mock.patch("core.translation.get_llm", return_value=self.llm)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.client.force_login(make_user("master@example.com", Role.MASTER))

    def test_alert_written_in_french_only_is_translated(self):
        response = self.client.post(reverse("panel:alert_create"), {
            "title_fr": "Préavis de grève", "body_fr": "Grève le 1er mai", "show_days": "7",
        }, follow=True)
        alert = Alert.objects.get()
        self.assertEqual((alert.title_en, alert.title_ar), ("Strike notice", "إشعار بالإضراب"))
        self.assertEqual((alert.body_en, alert.body_ar), ("Strike on 1 May", "إضراب يوم 1 ماي"))
        self.assertEqual(len(self.llm.calls), 1)  # one request for the whole form
        self.assertContains(response, "traduites automatiquement")

    def test_filled_languages_are_never_overwritten(self):
        self.client.post(reverse("panel:news_create"), {
            "title_fr": "Assemblée générale", "title_en": "My own title", "body_fr": "", "body_en": "", "body_ar": "",
            "published_at": "2026-10-17T10:00", "is_published": "on", "video_urls": "",
        })
        article = Article.objects.get()
        self.assertEqual(article.title_en, "My own title")
        self.assertEqual(article.title_ar, "[ar] Assemblée générale")
        self.assertEqual(self.llm.calls[0], {"title": {"source": {"fr": "Assemblée générale", "en": "My own title"}, "translate_to": ["ar"]}})

    def test_arabic_only_vote_gets_french_and_english(self):
        response = self.client.post(reverse("panel:poll_create"), {
            "category": Poll.Category.STRIKE, "title_ar": "إضراب؟", "choices_fr": "Oui\nNon",
            "opens_at": "2026-10-17T10:00", "closes_at": "2026-10-20T10:00",
        })
        self.assertEqual(response.status_code, 302)
        poll = Poll.objects.get()
        self.assertEqual((poll.title_fr, poll.title_en), ("Grève ?", "Strike?"))
        self.assertEqual([(c.text_fr, c.text_en, c.text_ar) for c in poll.choices.all()], [("Oui", "Yes", "نعم"), ("Non", "No", "لا")])

    def test_destination_and_activity_in_one_language(self):
        response = self.client.post(reverse("panel:destination_create"), {
            "name_fr": "Rome", "position": "1",
            "act-TOTAL_FORMS": "1", "act-INITIAL_FORMS": "0", "act-MIN_NUM_FORMS": "0", "act-MAX_NUM_FORMS": "15",
            "act-0-title_en": "Colosseum", "act-0-description_en": "Ancient arena.", "act-0-position": "0",
        })
        self.assertEqual(response.status_code, 302)
        rome = Destination.objects.get(name_fr="Rome")
        self.assertEqual(rome.name_ar, "روما")
        activity = rome.activities.get()
        self.assertEqual((activity.title_fr, activity.title_ar), ("[fr] Colosseum", "[ar] Colosseum"))
        self.assertEqual(activity.description_fr, "[fr] Ancient arena.")

    def test_nothing_to_translate_makes_no_request(self):
        self.client.post(reverse("panel:alert_create"), {
            "title_fr": "A", "title_en": "B", "title_ar": "ج", "body_fr": "A", "body_en": "B", "body_ar": "ج", "show_days": "7",
        })
        self.assertEqual(Alert.objects.count(), 1)
        self.assertEqual(self.llm.calls, [])

    def test_invalid_form_is_not_translated(self):
        response = self.client.post(reverse("panel:poll_create"), {
            "category": Poll.Category.STRIKE, "title_fr": "Grève ?", "choices_fr": "Oui\nNon",
            "opens_at": "not a date", "closes_at": "2026-10-16T10:00",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.llm.calls, [])

    def test_empty_everywhere_is_refused(self):
        response = self.client.post(reverse("panel:alert_create"), {"title_fr": "", "body_fr": "Texte", "show_days": "7"})
        self.assertContains(response, "Remplissez au moins une langue")
        self.assertFalse(Alert.objects.exists())


class TranslationUnavailableTests(TestCase):
    def setUp(self):
        translation.activate("fr")
        patcher = mock.patch("core.translation.get_llm", return_value=BrokenLLM())
        patcher.start()
        self.addCleanup(patcher.stop)
        self.client.force_login(make_user("master@example.com", Role.MASTER))

    def test_saves_without_translation_when_french_is_there(self):
        self.client.post(reverse("panel:alert_create"), {"title_fr": "Préavis", "body_fr": "Texte", "show_days": "7"})
        alert = Alert.objects.get()
        self.assertEqual((alert.title_en, alert.title_ar), ("", ""))

    def test_arabic_only_asks_for_french(self):
        response = self.client.post(reverse("panel:alert_create"), {"title_ar": "عنوان", "body_ar": "نص", "show_days": "7"})
        self.assertContains(response, "Veuillez aussi remplir le français")
        self.assertFalse(Alert.objects.exists())
