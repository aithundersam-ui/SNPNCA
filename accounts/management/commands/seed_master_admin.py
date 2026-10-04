import os

from django.core.management.base import BaseCommand, CommandError

from accounts.emails import send_invitation
from accounts.models import Role, User


class Command(BaseCommand):
    help = (
        "Create the first Master Admin from MASTER_ADMIN_EMAIL / MASTER_ADMIN_NAME "
        "(and optionally MASTER_ADMIN_PASSWORD). Safe to run on every deploy."
    )

    def handle(self, *args, **options):
        email = (os.environ.get("MASTER_ADMIN_EMAIL") or "").strip().lower()
        name = (os.environ.get("MASTER_ADMIN_NAME") or "").strip() or "Master Admin"
        password = os.environ.get("MASTER_ADMIN_PASSWORD") or None
        if not email:
            raise CommandError("MASTER_ADMIN_EMAIL is not set.")

        if User.objects.filter(role=Role.MASTER).exists():
            self.stdout.write("A Master Admin already exists; nothing to do.")
            return

        user = User.objects.filter(email=email).first()
        if user:
            user.role = Role.MASTER
            user.is_active = True
            user.save(update_fields=["role", "is_active"])
            self.stdout.write(self.style.SUCCESS(f"Promoted {email} to Master Admin."))
            return

        user = User.objects.create_user(email=email, full_name=name, password=password, role=Role.MASTER)
        if password:
            self.stdout.write(self.style.SUCCESS(f"Created Master Admin {email} with the password from the environment."))
            self.stdout.write("Remove MASTER_ADMIN_PASSWORD from the environment now that the account exists.")
        else:
            send_invitation(user)
            self.stdout.write(self.style.SUCCESS(f"Created Master Admin {email}; a set-password link was emailed."))
