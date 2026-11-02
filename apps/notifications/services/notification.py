from django.utils import timezone

from apps.notifications.models import Notification


class NotificationService:

    @staticmethod
    def send(user, title: str, body: str) -> Notification:
        return Notification.objects.create(user=user, title=title, body=body)

    @staticmethod
    def mark_read(notification_id, user) -> bool:
        updated = Notification.objects.filter(
            id=notification_id,
            user=user,
            is_read=False,
        ).update(is_read=True, read_at=timezone.now())
        return updated > 0

    @staticmethod
    def mark_all_read(user) -> int:
        return Notification.objects.filter(
            user=user,
            is_read=False,
        ).update(is_read=True, read_at=timezone.now())

    @staticmethod
    def unread_count(user) -> int:
        return Notification.objects.filter(user=user, is_read=False).count()
