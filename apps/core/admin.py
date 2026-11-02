from django.contrib import admin
from django.contrib.admin.models import LogEntry
from django.utils.html import format_html

# Admin Logs
class AdminLogEntry(LogEntry):
    class Meta:
        proxy = True
        app_label = "admin"
        verbose_name = "Admin Log"
        verbose_name_plural = "Admin Logs"
@admin.register(AdminLogEntry)
class LogEntryAdmin(admin.ModelAdmin):
    list_display = ("action_time", "user", "content_type", "object_link", "colored_action")
    list_filter = ("action_flag", "content_type", "user")
    search_fields = ("object_repr", "change_message", "user__username")
    readonly_fields = ("action_time", "user", "content_type", "object_repr", "action_flag", "change_message")
    ordering = ("-action_time",)
    list_per_page = 50
    date_hierarchy = "action_time"

    def object_link(self, obj):
        return format_html("<strong>{}</strong>", obj.object_repr)

    object_link.short_description = "Object"

    def colored_action(self, obj):
        colors = {1: "#16a34a", 2: "#2563eb", 3: "#dc2626"}
        labels = {1: "ADD", 2: "CHANGE", 3: "DELETE"}
        color = colors.get(obj.action_flag, "#374151")
        label = labels.get(obj.action_flag, "UNKNOWN")
        return format_html('<strong style="color:{};">{}</strong>', color, label)

    colored_action.short_description = "Action"
    colored_action.admin_order_field = "action_flag"

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False