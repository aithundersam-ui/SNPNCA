from django.conf import settings

ASSETS = [settings.BASE_DIR / "static" / "css" / "site.css", settings.BASE_DIR / "static" / "js" / "site.js"]


def _asset_version():
    """Changes whenever site.css or site.js changes, so browsers never keep an old copy."""
    try:
        return str(int(max(p.stat().st_mtime for p in ASSETS)))
    except OSError:
        return "0"


_STARTUP_VERSION = _asset_version()


def site(request):
    active_alert = None
    if getattr(request, "user", None) is not None and request.user.is_authenticated:
        from alerts.models import Alert

        active_alert = Alert.active().first()
    return {
        "active_alert": active_alert,
        "ORG_NAME": "Syndicat National du Personnel Navigant Commercial Algérien",
        "ORG_SHORT": "SNPNCA",
        "LANGUAGES": settings.LANGUAGES,
        # In development files change while the server runs; in production they change with a restart.
        "ASSET_VERSION": _asset_version() if settings.DEBUG else _STARTUP_VERSION,
    }
