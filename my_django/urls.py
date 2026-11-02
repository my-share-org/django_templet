from django.conf import settings
from django.contrib import admin
from django.urls import path, include
from apps.core.views import HealthCheckView, HealthReportView

handler404 = "apps.core.utils.exception_handler.handle_404"
handler500 = "apps.core.utils.exception_handler.handle_500"

urlpatterns = [
    path("health/", HealthCheckView.as_view(), name="health_check"),
    path("admin/",  admin.site.urls),
    path("v1/",     include(("my_django.urls_v1", "v1"))),
]

# Developer diagnostics dashboard: available only when DEBUG=True
if settings.DEBUG:
    urlpatterns.insert(0, path("", HealthReportView.as_view(), name="health_dashboard"))
