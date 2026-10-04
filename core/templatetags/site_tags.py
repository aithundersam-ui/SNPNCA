from django import template

register = template.Library()


@register.simple_tag
def localized(obj, field):
    """{% localized article "title" %} -> French or English value with fallback."""
    return obj.localized(field)


@register.filter
def can_manage(actor, target):
    from accounts.permissions import can_manage as _can_manage

    return _can_manage(actor, target)
