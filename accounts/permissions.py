"""Server-side permission rules. Every view that changes accounts goes through these.

The role table from the spec:
- Admins manage normal users only.
- Only the Master Admin creates admins, changes roles, or edits/deletes admin accounts.
- There must always be at least one active Master Admin.
"""

from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.db import transaction

from .models import Role, User


class LastMasterAdminError(Exception):
    pass


def admin_required(view):
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if not request.user.is_admin:
            raise PermissionDenied
        return view(request, *args, **kwargs)

    return wrapper


def master_required(view):
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if not request.user.is_master:
            raise PermissionDenied
        return view(request, *args, **kwargs)

    return wrapper


def can_manage(actor, target):
    """Can `actor` edit or delete `target`'s account?"""
    if not actor.is_authenticated or not actor.is_admin:
        return False
    if actor.is_master:
        return True
    return target.role == Role.USER


def can_assign_role(actor, role):
    if not actor.is_authenticated or not actor.is_admin:
        return False
    if actor.is_master:
        return role in Role.values
    return role == Role.USER


def _would_remove_last_master(target, new_role=None, deleting=False, deactivating=False):
    if target.role != Role.MASTER:
        return False
    losing = deleting or deactivating or (new_role is not None and new_role != Role.MASTER)
    if not losing:
        return False
    others = User.objects.select_for_update().filter(role=Role.MASTER, is_active=True).exclude(pk=target.pk)
    return not others.exists()


@transaction.atomic
def change_role(actor, target, new_role):
    if not can_manage(actor, target) or not can_assign_role(actor, new_role):
        raise PermissionDenied
    if _would_remove_last_master(target, new_role=new_role):
        raise LastMasterAdminError
    target.role = new_role
    target.save(update_fields=["role"])


@transaction.atomic
def set_active(actor, target, active):
    if not can_manage(actor, target):
        raise PermissionDenied
    if not active and _would_remove_last_master(target, deactivating=True):
        raise LastMasterAdminError
    target.is_active = active
    target.save(update_fields=["is_active"])


@transaction.atomic
def delete_user(actor, target):
    if not can_manage(actor, target):
        raise PermissionDenied
    if _would_remove_last_master(target, deleting=True):
        raise LastMasterAdminError
    target.delete()
