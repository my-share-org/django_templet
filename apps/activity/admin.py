from django.contrib import admin

from .models import UserActivity, UserSession


@admin.register(UserSession)
class UserSessionAdmin(admin.ModelAdmin):
    list_display = ('user', 'session_key_short', 'device_type', 'ip_address',
                     'started_at', 'ended_at', 'is_active', 'duration_display')
    list_filter = ('device_type', 'is_active', 'started_at')
    search_fields = ('user__email', 'session_key', 'ip_address')
    readonly_fields = (
        'user', 'session_key', 'started_at', 'ended_at',
        'ip_address', 'user_agent', 'device_type', 'is_active',
        'created_at', 'updated_at',
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')

    def session_key_short(self, obj):
        return f"{obj.session_key[:8]}..."
    session_key_short.short_description = "Session key"

    def duration_display(self, obj):
        secs = obj.duration_seconds
        if secs is None:
            return "Active"
        minutes, seconds = divmod(secs, 60)
        return f"{minutes}m {seconds}s"
    duration_display.short_description = "Duration"

    # Strictly no modifications to immutable session records
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(UserActivity)
class UserActivityAdmin(admin.ModelAdmin):
    list_display = ('user', 'service', 'action', 'method', 'status_code',
                     'duration_ms', 'device_type', 'occurred_at')
    list_filter = ('service', 'action', 'method', 'status_code', 'device_type', 'occurred_at')
    search_fields = ('user__email', 'path', 'ip_address', 'request_id')
    date_hierarchy = 'occurred_at'
    readonly_fields = (
        'user', 'session', 'request_id', 'service', 'action', 'path', 'method',
        'status_code', 'duration_ms', 'ip_address', 'device_type', 'referrer',
        'occurred_at', 'created_at', 'updated_at',
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'session')

    # Strictly no modifications to immutable activity records
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
