from django.conf.urls.i18n import i18n_patterns
from django.urls import include, path

from core import views as core_views

urlpatterns = [
    # Bare "/" always lands on French unless the visitor already chose a language.
    path("", core_views.root_redirect, name="root"),
    path("healthz", core_views.healthz, name="healthz"),
]

urlpatterns += i18n_patterns(
    path("", include("core.urls")),
    path("account/", include("accounts.urls")),
    path("news/", include("news.urls")),
    path("qa/", include("qa.urls")),
    path("panel/", include("panel.urls")),
    prefix_default_language=True,
)

handler403 = "core.views.error_403"
handler404 = "core.views.error_404"
handler500 = "core.views.error_500"
