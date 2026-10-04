"""Role permissions are enforced on the server for every protected view."""

from django.test import TestCase
from django.urls import reverse

from accounts import permissions as perms
from accounts.models import AuditLog, Role, User

from .helpers import make_user


class PermissionMatrixTests(TestCase):
    def setUp(self):
        self.master = make_user("master@example.com", Role.MASTER)
        self.admin = make_user("admin@example.com", Role.ADMIN)
        self.member = make_user("member@example.com")
        self.other_admin = make_user("admin2@example.com", Role.ADMIN)

    def login(self, user):
        self.client.force_login(user)

    # --- anonymous visitors
    def test_home_is_public(self):
        self.assertEqual(self.client.get(reverse("core:home")).status_code, 200)

    def test_members_area_requires_login(self):
        for name in ("news:list", "qa:chat", "panel:dashboard", "panel:users"):
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 302, name)
            self.assertIn(reverse("accounts:login"), response["Location"])

    # --- normal members
    def test_member_can_view_news_and_qa(self):
        self.login(self.member)
        self.assertEqual(self.client.get(reverse("news:list")).status_code, 200)
        self.assertEqual(self.client.get(reverse("qa:chat")).status_code, 200)

    def test_member_is_refused_every_panel_page(self):
        self.login(self.member)
        names = ["dashboard", "users", "user_create", "csv_upload", "documents", "news", "news_create", "messages", "home_content", "audit", "admins", "admin_create"]
        for name in names:
            self.assertEqual(self.client.get(reverse(f"panel:{name}")).status_code, 403, name)
        self.assertEqual(self.client.post(reverse("panel:user_delete", args=[self.other_admin.pk])).status_code, 403)
        self.assertTrue(User.objects.filter(pk=self.other_admin.pk).exists())

    # --- admins
    def test_admin_can_manage_normal_users(self):
        self.login(self.admin)
        response = self.client.post(
            reverse("panel:user_create"),
            {"full_name": "Nadia Saïdi", "email": "nadia@example.com", "preferred_language": "fr", "is_active": "on"},
        )
        self.assertEqual(response.status_code, 302)
        created = User.objects.get(email="nadia@example.com")
        self.assertEqual(created.role, Role.USER)
        self.assertFalse(created.has_usable_password())
        self.client.post(reverse("panel:user_delete", args=[self.member.pk]))
        self.assertFalse(User.objects.filter(pk=self.member.pk).exists())
        self.assertTrue(AuditLog.objects.filter(action="user.delete", target="member@example.com").exists())

    def test_admin_cannot_create_admins_even_by_posting_a_role(self):
        self.login(self.admin)
        self.client.post(
            reverse("panel:user_create"),
            {"full_name": "Sneaky", "email": "sneaky@example.com", "preferred_language": "fr", "role": "master", "is_active": "on"},
        )
        self.assertEqual(User.objects.get(email="sneaky@example.com").role, Role.USER)
        self.assertEqual(self.client.get(reverse("panel:admin_create")).status_code, 403)
        self.assertEqual(self.client.get(reverse("panel:admins")).status_code, 403)

    def test_admin_cannot_edit_delete_or_promote_admin_accounts(self):
        self.login(self.admin)
        self.assertEqual(self.client.get(reverse("panel:user_edit", args=[self.other_admin.pk])).status_code, 403)
        self.assertEqual(self.client.post(reverse("panel:user_delete", args=[self.other_admin.pk])).status_code, 403)
        self.assertEqual(self.client.post(reverse("panel:user_delete", args=[self.master.pk])).status_code, 403)
        self.assertEqual(self.client.post(reverse("panel:change_role", args=[self.member.pk]), {"role": "admin"}).status_code, 403)
        self.member.refresh_from_db()
        self.assertEqual(self.member.role, Role.USER)
        # Posting a role while editing a member is ignored for admins.
        self.client.post(
            reverse("panel:user_edit", args=[self.member.pk]),
            {"full_name": "Member", "email": "member@example.com", "preferred_language": "en", "role": "admin", "is_active": "on"},
        )
        self.member.refresh_from_db()
        self.assertEqual(self.member.role, Role.USER)
        self.assertEqual(self.member.preferred_language, "en")

    # --- master admin
    def test_master_can_create_admins_and_change_roles(self):
        self.login(self.master)
        self.client.post(
            reverse("panel:admin_create"),
            {"full_name": "New Admin", "email": "newadmin@example.com", "preferred_language": "fr", "role": "admin", "is_active": "on"},
        )
        self.assertEqual(User.objects.get(email="newadmin@example.com").role, Role.ADMIN)
        self.client.post(reverse("panel:change_role", args=[self.member.pk]), {"role": "admin"})
        self.member.refresh_from_db()
        self.assertEqual(self.member.role, Role.ADMIN)
        self.assertTrue(AuditLog.objects.filter(action="user.role_change", target=self.member.email).exists())
        self.client.post(reverse("panel:user_delete", args=[self.other_admin.pk]))
        self.assertFalse(User.objects.filter(pk=self.other_admin.pk).exists())

    def test_last_master_admin_cannot_be_demoted_deleted_or_deactivated(self):
        self.login(self.master)
        self.client.post(reverse("panel:change_role", args=[self.master.pk]), {"role": "user"})
        self.client.post(reverse("panel:user_delete", args=[self.master.pk]))
        self.client.post(
            reverse("panel:user_edit", args=[self.master.pk]),
            {"full_name": "Master", "email": "master@example.com", "preferred_language": "fr", "role": "master"},
        )
        self.master.refresh_from_db()
        self.assertEqual(self.master.role, Role.MASTER)
        self.assertTrue(self.master.is_active)

    def test_master_can_step_down_once_another_master_exists(self):
        second = make_user("master2@example.com", Role.MASTER)
        perms.change_role(self.master, self.master, Role.ADMIN)
        self.master.refresh_from_db()
        self.assertEqual(self.master.role, Role.ADMIN)
        with self.assertRaises(perms.LastMasterAdminError):
            perms.delete_user(second, second)


class SeedTests(TestCase):
    def test_seed_creates_master_from_environment(self):
        import os
        from unittest import mock

        from django.core import mail
        from django.core.management import call_command

        with mock.patch.dict(os.environ, {"MASTER_ADMIN_EMAIL": "Boss@Example.com", "MASTER_ADMIN_NAME": "Boss"}):
            call_command("seed_master_admin", stdout=open(os.devnull, "w"))
            call_command("seed_master_admin", stdout=open(os.devnull, "w"))
        self.assertEqual(User.objects.filter(role=Role.MASTER).count(), 1)
        self.assertEqual(User.objects.get().email, "boss@example.com")
        self.assertEqual(len(mail.outbox), 1)
