"""One-on-one meeting bookings: numbered queue, two days a month, admin flow."""

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from accounts.models import AuditLog, Role, User
from meetings.models import MeetingDay, MeetingRequest

from .helpers import make_user



def make_day(days_ahead=7, **extra):
    return MeetingDay.objects.create(date=timezone.localdate() + timedelta(days=days_ahead), **extra)


class BookingTests(TestCase):
    def setUp(self):
        self.day = make_day()
        self.alice = make_user("alice@example.com")
        self.bob = make_user("bob@example.com")

    def book(self, user, subject="Congés"):
        self.client.force_login(user)
        return self.client.post("/fr/meetings/", {"day": self.day.pk, "subject": subject, "whatsapp_number": "+213550123456"})

    def test_members_get_increasing_numbers_and_see_their_place(self):
        self.book(self.alice)
        self.book(self.bob)
        a, b = MeetingRequest.objects.order_by("pk")
        self.assertLess(a.number, b.number)
        self.assertEqual(a.people_ahead(), 0)
        self.assertEqual(b.people_ahead(), 1)
        page = self.client.get("/fr/meetings/")  # logged in as bob
        self.assertContains(page, f"#{b.number}")

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
        data = {"start_time": "09:00", "slot_minutes": 20, "capacity": 10}
        self.client.force_login(self.admin)
        self.assertEqual(self.client.post("/fr/panel/meetings/days/new/", {**data, "date": target}).status_code, 403)
        self.client.force_login(self.master)
        for offset in (0, 1, 2):
            self.client.post("/fr/panel/meetings/days/new/", {**data, "date": target + timedelta(days=offset)})
        self.assertEqual(MeetingDay.objects.filter(date__month=target.month, date__year=target.year).count(), 2)

    def test_start_marks_meeting_and_opens_whatsapp_with_member_number(self):
        self.member.whatsapp_number = "+213550123456"
        self.member.save()
        first = MeetingRequest.objects.create(day=self.day, user=self.member, subject="A")
        other = make_user("other@example.com", whatsapp_number="+213661234567")
        second = MeetingRequest.objects.create(day=self.day, user=other, subject="B")
        self.client.force_login(self.admin)
        response = self.client.post(f"/fr/panel/meetings/requests/{first.pk}/start/")
        self.assertRedirects(response, f"/fr/panel/meetings/requests/{first.pk}/call/?open=1", fetch_redirect_response=False)
        first.refresh_from_db()
        self.assertEqual(first.status, MeetingRequest.Status.IN_PROGRESS)
        self.assertEqual(second.people_ahead(), 1)
        self.assertTrue(AuditLog.objects.filter(action="meeting.start").exists())
        page = self.client.get(response["Location"])
        self.assertContains(page, 'href="https://wa.me/213550123456" data-auto-open')
        # The member is told an admin is calling them.
        self.client.force_login(self.member)
        self.assertContains(self.client.get("/fr/meetings/"), "+213550123456")
        # Starting the next one closes the previous meeting.
        self.client.force_login(self.admin)
        self.client.post(f"/fr/panel/meetings/requests/{second.pk}/start/")
        first.refresh_from_db()
        self.assertEqual(first.status, MeetingRequest.Status.DONE)

    def test_start_without_whatsapp_number_explains_and_keeps_queue(self):
        booking = MeetingRequest.objects.create(day=self.day, user=self.member, subject="A")
        self.client.force_login(self.admin)
        self.client.post(f"/fr/panel/meetings/requests/{booking.pk}/start/")
        booking.refresh_from_db()
        self.assertEqual(booking.status, MeetingRequest.Status.WAITING)

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



class WhatsAppNumberTests(TestCase):
    def test_numbers_are_normalised_to_international_form(self):
        from django.core.exceptions import ValidationError

        from accounts.models import normalize_whatsapp

        self.assertEqual(normalize_whatsapp("0550 12 34 56"), "+213550123456")
        self.assertEqual(normalize_whatsapp("00213 550-12-34-56"), "+213550123456")
        self.assertEqual(normalize_whatsapp("+33 6 12 34 56 78"), "+33612345678")
        for bad in ("12", "abc", "+0123456789"):
            with self.assertRaises(ValidationError):
                normalize_whatsapp(bad)

    def test_booking_saves_members_whatsapp_number(self):
        day = make_day()
        member = make_user("m@example.com")
        self.client.force_login(member)
        self.client.post("/fr/meetings/", {"day": day.pk, "subject": "Congés", "whatsapp_number": "0661 23 45 67"})
        member.refresh_from_db()
        self.assertEqual(member.whatsapp_number, "+213661234567")
        self.assertTrue(MeetingRequest.objects.filter(user=member).exists())

    def test_admin_must_give_whatsapp_number_when_creating_member(self):
        admin = make_user("admin@example.com", role=Role.ADMIN)
        self.client.force_login(admin)
        data = {"full_name": "Nadia", "email": "nadia@example.com", "preferred_language": "fr", "is_active": "on"}
        self.client.post("/fr/panel/users/new/", data)
        self.assertFalse(User.objects.filter(email="nadia@example.com").exists())
        self.client.post("/fr/panel/users/new/", {**data, "whatsapp_number": "0550123456"})
        self.assertEqual(User.objects.get(email="nadia@example.com").whatsapp_number, "+213550123456")

    def test_csv_import_reads_optional_whatsapp_column(self):
        from accounts import csv_import

        master = make_user("boss@example.com", role=Role.MASTER)
        rows = csv_import.parse("full_name,email,whatsapp\nA,a@example.com,0550123456\nB,b@example.com,\nC,c@example.com,12\n", master)
        self.assertEqual(rows[0].whatsapp, "+213550123456")
        self.assertTrue(rows[1].ok and rows[1].warnings)
        self.assertFalse(rows[2].ok)
        csv_import.apply([r.as_dict() for r in rows if r.ok], master)
        self.assertEqual(User.objects.get(email="a@example.com").whatsapp_number, "+213550123456")
