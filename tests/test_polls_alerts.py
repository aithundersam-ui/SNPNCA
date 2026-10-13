from datetime import timedelta
from urllib.parse import unquote

from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone, translation

from accounts.models import AuditLog, Role
from alerts.models import Alert
from polls.models import Ballot, Choice, Poll

from .helpers import make_user


def make_poll(**extra):
    now = timezone.now()
    data = {"title_fr": "Grève le 1er mai ?", "title_en": "Strike on May 1st?", "category": Poll.Category.STRIKE,
            "opens_at": now - timedelta(hours=1), "closes_at": now + timedelta(days=2)}
    data.update(extra)
    poll = Poll.objects.create(**data)
    for i, (fr, en) in enumerate([("Oui", "Yes"), ("Non", "No")]):
        poll.choices.create(text_fr=fr, text_en=en, position=i)
    return poll


class VotingTests(TestCase):
    def setUp(self):
        translation.activate("fr")
        self.member = make_user("member@example.com")
        self.poll = make_poll()
        self.yes = self.poll.choices.get(text_fr="Oui")

    def vote(self, choice, user=None):
        self.client.force_login(user or self.member)
        return self.client.post(reverse("polls:detail", args=[self.poll.pk]), {"choice": choice.pk})

    def test_member_votes_once_and_ballot_is_secret(self):
        self.vote(self.yes)
        self.vote(self.poll.choices.get(text_fr="Non"))
        self.yes.refresh_from_db()
        self.assertEqual(self.yes.votes, 1)
        self.assertEqual(Choice.objects.get(text_fr="Non").votes, 0)
        self.assertEqual(Ballot.objects.filter(poll=self.poll).count(), 1)
        self.assertNotIn("choice", [f.name for f in Ballot._meta.get_fields()])

    def test_results_hidden_from_members_until_closed(self):
        self.vote(self.yes)
        page = self.client.get(reverse("polls:detail", args=[self.poll.pk]))
        self.assertContains(page, "Vous avez voté")
        self.assertNotContains(page, "poll-results")
        self.poll.closed_early_at = timezone.now()
        self.poll.save()
        page = self.client.get(reverse("polls:detail", args=[self.poll.pk]))
        self.assertContains(page, "poll-results")
        self.assertContains(page, "100%")

    def test_results_stay_hidden_when_admin_chose_not_to_publish(self):
        self.poll.show_results = False
        self.poll.closed_early_at = timezone.now()
        self.poll.save()
        self.client.force_login(self.member)
        self.assertNotContains(self.client.get(reverse("polls:detail", args=[self.poll.pk])), "poll-results")

    def test_cannot_vote_on_closed_or_upcoming_polls(self):
        self.poll.closed_early_at = timezone.now()
        self.poll.save()
        self.vote(self.yes)
        self.assertEqual(Ballot.objects.count(), 0)
        upcoming = make_poll(opens_at=timezone.now() + timedelta(days=1), closes_at=timezone.now() + timedelta(days=2))
        self.client.force_login(self.member)
        self.assertEqual(self.client.get(reverse("polls:detail", args=[upcoming.pk])).status_code, 404)

    def test_choice_from_another_poll_is_rejected(self):
        other = make_poll()
        self.vote(other.choices.first())
        self.assertEqual(Ballot.objects.count(), 0)

    def test_votes_need_login(self):
        self.assertEqual(self.client.get(reverse("polls:list")).status_code, 302)


class PollAdminTests(TestCase):
    def setUp(self):
        translation.activate("fr")
        self.admin = make_user("admin@example.com", Role.ADMIN)
        self.member = make_user("member@example.com")

    def test_admin_creates_poll_with_answers_and_sees_live_results(self):
        self.client.force_login(self.admin)
        now = timezone.localtime()
        response = self.client.post(reverse("panel:poll_create"), {
            "category": "assembly", "title_fr": "Approuvez-vous le rapport ?", "title_en": "",
            "description_fr": "", "description_en": "",
            "opens_at": (now - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M"),
            "closes_at": (now + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M"),
            "show_results": "on", "choices_fr": "Oui\nNon\nAbstention", "choices_en": "",
        })
        poll = Poll.objects.get()
        self.assertRedirects(response, reverse("panel:poll_results", args=[poll.pk]))
        self.assertEqual(poll.choices.count(), 3)
        self.assertTrue(poll.is_open)
        self.assertTrue(AuditLog.objects.filter(action="poll.create").exists())
        self.assertContains(self.client.get(reverse("panel:poll_results", args=[poll.pk])), "Abstention")

    def test_answers_are_validated(self):
        self.client.force_login(self.admin)
        now = timezone.localtime()
        base = {"category": "survey", "title_fr": "Q", "opens_at": now.strftime("%Y-%m-%dT%H:%M"),
                "closes_at": (now + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M")}
        self.client.post(reverse("panel:poll_create"), {**base, "choices_fr": "Seulement une"})
        self.client.post(reverse("panel:poll_create"), {**base, "choices_fr": "A\nB", "choices_en": "A"})
        self.client.post(reverse("panel:poll_create"), {**base, "choices_fr": "A\nB", "closes_at": base["opens_at"]})
        self.assertEqual(Poll.objects.count(), 0)

    def test_answers_locked_after_first_vote_and_close_now(self):
        poll = make_poll()
        Ballot.objects.create(poll=poll, user=self.member)
        self.client.force_login(self.admin)
        later = (timezone.localtime() + timedelta(days=5)).strftime("%Y-%m-%dT%H:%M")
        self.client.post(reverse("panel:poll_edit", args=[poll.pk]), {
            "title_fr": "Changed", "description_fr": "Plus de détails", "closes_at": later, "choices_fr": "X\nY",
        })
        poll.refresh_from_db()
        self.assertEqual(poll.title_fr, "Grève le 1er mai ?")
        self.assertEqual(poll.description_fr, "Plus de détails")
        self.assertEqual(list(poll.choices.values_list("text_fr", flat=True)), ["Oui", "Non"])
        self.client.post(reverse("panel:poll_close", args=[poll.pk]))
        poll.refresh_from_db()
        self.assertTrue(poll.is_closed)

    def test_only_master_deletes_a_poll_with_votes(self):
        poll = make_poll()
        Ballot.objects.create(poll=poll, user=self.member)
        self.client.force_login(self.admin)
        self.client.post(reverse("panel:poll_delete", args=[poll.pk]))
        self.assertTrue(Poll.objects.filter(pk=poll.pk).exists())
        self.client.force_login(make_user("master@example.com", Role.MASTER))
        self.client.post(reverse("panel:poll_delete", args=[poll.pk]))
        self.assertFalse(Poll.objects.filter(pk=poll.pk).exists())

    def test_members_cannot_open_the_poll_panel(self):
        self.client.force_login(self.member)
        self.assertEqual(self.client.get(reverse("panel:polls")).status_code, 403)
        self.assertEqual(self.client.get(reverse("panel:poll_create")).status_code, 403)


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class AlertTests(TestCase):
    def setUp(self):
        translation.activate("fr")
        self.admin = make_user("admin@example.com", Role.ADMIN)
        self.fr_member = make_user("fr@example.com", whatsapp_number="+213550000001")
        self.en_member = make_user("en@example.com", preferred_language="en")
        make_user("gone@example.com", is_active=False)

    def publish(self, **extra):
        self.client.force_login(self.admin)
        data = {"title_fr": "Préavis de grève", "title_en": "Strike notice", "body_fr": "Grève le 1er mai.",
                "body_en": "Strike on May 1st.", "show_days": "7", "send_email": "on"}
        data.update(extra)
        return self.client.post(reverse("panel:alert_create"), data)

    def test_alert_is_emailed_to_active_members_in_their_language(self):
        response = self.publish()
        alert = Alert.objects.get()
        self.assertRedirects(response, reverse("panel:alert_detail", args=[alert.pk]))
        recipients = {m.to[0]: m for m in mail.outbox}
        self.assertEqual(set(recipients), {"admin@example.com", "fr@example.com", "en@example.com"})
        self.assertIn("Préavis de grève", recipients["fr@example.com"].subject)
        self.assertIn("Strike notice", recipients["en@example.com"].subject)
        self.assertIn("/en/alerts/", recipients["en@example.com"].body)
        alert.refresh_from_db()
        self.assertEqual((alert.emails_sent, alert.emails_failed), (3, 0))

    def test_alert_without_email(self):
        self.publish(send_email="")
        self.assertEqual(len(mail.outbox), 0)
        self.assertIsNone(Alert.objects.get().emailed_at)

    def test_banner_shown_to_members_only_while_active(self):
        self.publish(send_email="")
        alert = Alert.objects.get()
        self.client.force_login(self.fr_member)
        self.assertContains(self.client.get(reverse("news:list")), "data-alert-banner")
        self.client.logout()
        self.assertNotContains(self.client.get("/fr/"), "data-alert-banner")
        alert.show_until = timezone.now() - timedelta(minutes=1)
        alert.save()
        self.client.force_login(self.fr_member)
        self.assertNotContains(self.client.get(reverse("news:list")), "data-alert-banner")
        self.assertContains(self.client.get(reverse("alerts:list")), "Préavis de grève")

    def test_whatsapp_links_carry_the_message(self):
        self.publish(send_email="")
        alert = Alert.objects.get()
        page = self.client.get(reverse("panel:alert_detail", args=[alert.pk]))
        self.assertContains(page, "https://wa.me/?text=")
        self.assertContains(page, "https://wa.me/213550000001?text=")
        self.assertIn("Grève le 1er mai.", unquote(alert.whatsapp_link_for(self.fr_member)))
        self.assertEqual(alert.whatsapp_link_for(self.en_member), "")

    def test_members_cannot_publish_alerts(self):
        self.client.force_login(self.fr_member)
        self.assertEqual(self.client.post(reverse("panel:alert_create"), {"title_fr": "x", "body_fr": "y", "show_days": "1"}).status_code, 403)
        self.assertEqual(Alert.objects.count(), 0)
