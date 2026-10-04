from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class Role(models.TextChoices):
    USER = "user", _("Member")
    ADMIN = "admin", _("Admin")
    MASTER = "master", _("Master Admin")


class Language(models.TextChoices):
    FR = "fr", _("French")
    EN = "en", _("English")


class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, email, full_name, password=None, **extra):
        if not email:
            raise ValueError("Email is required")
        user = self.model(email=self.normalize_email(email).lower(), full_name=full_name, **extra)
        if password:
            user.set_password(password)
        else:
            # New accounts get a set-password link by email instead of a password.
            user.set_unusable_password()
        user.save(using=self._db)
        return user


class User(AbstractBaseUser):
    """A member account. Email is the login. Roles drive every permission check."""

    email = models.EmailField(_("email"), unique=True)
    full_name = models.CharField(_("full name"), max_length=150)
    role = models.CharField(_("role"), max_length=10, choices=Role.choices, default=Role.USER)
    preferred_language = models.CharField(
        _("preferred language"), max_length=2, choices=Language.choices, default=Language.FR
    )
    is_active = models.BooleanField(_("active"), default=True)
    date_joined = models.DateTimeField(default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = "email"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS = ["full_name"]

    class Meta:
        ordering = ["full_name"]

    def __str__(self):
        return f"{self.full_name} <{self.email}>"

    def save(self, *args, **kwargs):
        self.email = (self.email or "").strip().lower()
        super().save(*args, **kwargs)

    @property
    def is_admin(self):
        return self.role in (Role.ADMIN, Role.MASTER)

    @property
    def is_master(self):
        return self.role == Role.MASTER

    # Django's auth framework asks for these; there is no Django admin site here.
    @property
    def is_staff(self):
        return False

    @property
    def is_superuser(self):
        return False

    def has_perm(self, perm, obj=None):
        return False

    def has_module_perms(self, app_label):
        return False


class AuditLog(models.Model):
    """Append-only record of admin actions."""

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    actor = models.ForeignKey(User, null=True, on_delete=models.SET_NULL, related_name="+")
    actor_email = models.EmailField(blank=True)
    action = models.CharField(max_length=64, db_index=True)
    target = models.CharField(max_length=255, blank=True)
    details = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.created_at:%Y-%m-%d %H:%M} {self.actor_email} {self.action} {self.target}"
