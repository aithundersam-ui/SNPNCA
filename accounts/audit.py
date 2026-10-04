from .models import AuditLog


def client_ip(request):
    # Behind Caddy the real client address arrives in X-Forwarded-For; Caddy
    # overwrites that header, so the first entry is trustworthy in our setup.
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def log_action(request, action, target="", **details):
    user = request.user if request.user.is_authenticated else None
    AuditLog.objects.create(
        actor=user,
        actor_email=user.email if user else "",
        action=action,
        target=str(target)[:255],
        details=details,
        ip_address=client_ip(request),
    )
