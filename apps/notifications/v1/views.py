from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.core.utils.pagination import StandardPagination
from apps.core.utils.response import error_response, success_response
from apps.notifications.models import Notification
from apps.notifications.services import NotificationService
from apps.notifications.v1.serializers import NotificationSerializer


class NotificationListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset   = Notification.objects.filter(user=request.user)
        paginator  = StandardPagination()
        page       = paginator.paginate_queryset(queryset, request)
        serializer = NotificationSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data, message="Notifications retrieved")


class UnreadCountView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        count = NotificationService.unread_count(request.user)
        return success_response(
            message="Unread notification count",
            data={"count": count},
        )


class MarkReadView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        marked = NotificationService.mark_read(pk, request.user)
        if not marked:
            return error_response(
                message="Notification not found or already read",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return success_response(message="Notification marked as read")


class MarkAllReadView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request):
        count = NotificationService.mark_all_read(request.user)
        return success_response(
            message=f"{count} notification(s) marked as read",
            data={"updated": count},
        )
