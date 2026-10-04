from django.conf import settings


def site(request):
    return {
        "ORG_NAME": "Syndicat National du Personnel Navigant Commercial Algérien",
        "ORG_SHORT": "SNPNCA",
        "LANGUAGES": settings.LANGUAGES,
    }
