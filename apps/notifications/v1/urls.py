from django.urls import path

from apps.notifications.v1.views import (
    MarkAllReadView,
    MarkReadView,
    NotificationListView,
    UnreadCountView,
)

app_name = "notifications_v1"

urlpatterns = [
    path("",              NotificationListView.as_view(), name="list"),
    path("unread-count/", UnreadCountView.as_view(),      name="unread-count"),
    path("read-all/",     MarkAllReadView.as_view(),      name="mark-all-read"),
    path("<int:pk>/read/", MarkReadView.as_view(),        name="mark-read"),
]
