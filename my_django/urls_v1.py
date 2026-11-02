from django.urls import path, include

urlpatterns = [
    path("auth/",          include("apps.authentication.v1.urls")),
    path("otp/",           include("apps.otp.v1.urls")),
    path("notifications/", include("apps.notifications.v1.urls")),
]
