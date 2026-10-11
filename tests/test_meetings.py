"""One-on-one meeting bookings: numbered queue, two days a month, admin flow."""

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from accounts.models import AuditLog, Role
from meetings.models import MeetingDay, MeetingRequest

from .helpers import make_user

MEET = "https://meet.google.com/abc-defg-hij"


def make_day(days_ahead=7, **extra):
    return MeetingDay.objects.create(date=timezone.localdate() + timedelta(days=days_ahead), meet_link=MEET, **extra)


class BookingTests(TestCase):
    def setUp(self):
        self.day = make_day()
        self.alice = make_user("alice@example.com")
        self.bob = make_user("bob@example.com")

    def book(self, user, subject="Congés"):
        self.client.force_login(user)
        return self.client.post("/fr/meetings/", {"day": self.day.pk, "subject": subject})

    def test_members_get_increasing_numbers_and_see_their_place(self):
        self.book(self.alice)
        self.book(self.bob)
        a, b = MeetingRequest.objects.order_by("pk")
        self.assertLess(a.number, b.number)
        self.assertEqual(a.people_ahead(), 0)
        self.assertEqual(b.people_ahead(), 1)
        page = self.client.get("/fr/meetings/")  # logged in as bob
        self.assertContains(page, f"#{b.number}")
        self.assertNotContains(page, MEET)  # link only shown when it's their turn

    def test_one_active_request_per_member(self):
        self.book(self.alice)
        self.book(self.alice, "Encore")
        self.assertEqual(MeetingRequest.objects.filter(user=self.alice).count(), 1)

    def test_full_day_refuses_bookings(self):
        self.day.capacity = 1
        self.day.save()
        self.book(self.alice)
        response = self.book(self.bob)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(MeetingRequest.objects.filter(user=self.bob).exists())

    def test_member_can_cancel_own_waiting_request_only(self):
        self.book(self.alice)
        booking = MeetingRequest.objects.get(user=self.alice)
        self.client.force_login(self.bob)
        self.assertEqual(self.client.post(f"/fr/meetings/{booking.pk}/cancel/").status_code, 404)
        self.client.force_login(self.alice)
        self.client.post(f"/fr/meetings/{booking.pk}/cancel/")
        booking.refresh_from_db()
        self.assertEqual(booking.status, MeetingRequest.Status.CANCELLED)

    def test_login_required(self):
        self.assertEqual(self.client.get("/fr/meetings/").status_code, 302)


class AdminQueueTests(TestCase):
    def setUp(self):
        self.master = make_user("boss@example.com", role=Role.MASTER)
        self.admin = make_user("admin@example.com", role=Role.ADMIN)
        self.member = make_user("member@example.com")
        self.day = make_day()

    def test_only_master_admins_create_days_and_max_two_per_month(self):
        target = timezone.localdate().replace(day=1) + timedelta(days=62)  # a month with no days yet
        data = {"start_time": "09:00", "slot_minutes": 20, "capacity": 10, "meet_link": MEET}
        self.client.force_login(self.admin)
        self.assertEqual(self.client.post("/fr/panel/meetings/days/new/", {**data, "date": target}).status_code, 403)
        self.client.force_login(self.master)
        for offset in (0, 1, 2):
            self.client.post("/fr/panel/meetings/days/new/", {**data, "date": target + timedelta(days=offset)})
        self.assertEqual(MeetingDay.objects.filter(date__month=target.month, date__year=target.year).count(), 2)

    def test_meet_link_must_be_google_meet(self):
        self.client.force_login(self.master)
        response = self.client.post("/fr/panel/meetings/days/new/", {
            "date": timezone.localdate() + timedelta(days=90), "start_time": "09:00", "slot_minutes": 20,
            "capacity": 10, "meet_link": "https://evil.example.com/x",
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(MeetingDay.objects.filter(meet_link__contains="evil").exists())

    def test_start_opens_meet_moves_queue_and_member_sees_join_link(self):
        first = MeetingRequest.objects.create(day=self.day, user=self.member, subject="A")
        other = make_user("other@example.com")
        second = MeetingRequest.objects.create(day=self.day, user=other, subject="B")
        self.client.force_login(self.admin)
        response = self.client.post(f"/fr/panel/meetings/requests/{first.pk}/start/")
        self.assertEqual(response["Location"], MEET)
        first.refresh_from_db()
        self.assertEqual(first.status, MeetingRequest.Status.IN_PROGRESS)
        self.assertEqual(second.people_ahead(), 1)
        self.assertTrue(AuditLog.objects.filter(action="meeting.start").exists())
        # Starting the next one closes the previous meeting.
        self.client.post(f"/fr/panel/meetings/requests/{second.pk}/start/")
        first.refresh_from_db()
        self.assertEqual(first.status, MeetingRequest.Status.DONE)
        self.client.force_login(other)
        self.assertContains(self.client.get("/fr/meetings/"), MEET)

    def test_members_cannot_use_admin_queue(self):
        booking = MeetingRequest.objects.create(day=self.day, user=self.member, subject="A")
        self.client.force_login(self.member)
        self.assertEqual(self.client.post(f"/fr/panel/meetings/requests/{booking.pk}/start/").status_code, 403)
        self.assertEqual(self.client.get(f"/fr/panel/meetings/days/{self.day.pk}/").status_code, 403)

    def test_admin_pages_render(self):
        MeetingRequest.objects.create(day=self.day, user=self.member, subject="A")
        self.client.force_login(self.master)
        for url in ("/fr/panel/meetings/", f"/fr/panel/meetings/days/{self.day.pk}/", "/fr/panel/meetings/days/new/", f"/en/panel/meetings/days/{self.day.pk}/edit/"):
            self.assertEqual(self.client.get(url).status_code, 200, url)
