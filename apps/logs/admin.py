from django.contrib import admin
from django.utils.html import format_html
from .models import SystemLog

LEVEL_STYLES = {
    "DEBUG": {
        "bg": "#eff6ff",      # soft blue background
        "color": "#1e40af",   # strong blue text
        "border": "#93c5fd"
    },
    "INFO": {
        "bg": "#ecfeff",      # light cyan
        "color": "#0e7490",   # cyan text
        "border": "#67e8f9"
    },
    "SUCCESS": {
        "bg": "#ecfdf5",      # light green
        "color": "#047857",   # strong emerald text
        "border": "#6ee7b7"
    },
    "WARNING": {
        "bg": "#fffbeb",      # soft amber
        "color": "#b45309",   # amber text
        "border": "#fcd34d"
    },
    "ERROR": {
        "bg": "#fff7ed",      # soft orange
        "color": "#c2410c",   # strong orange text
        "border": "#fb923c"
    },
    "CRITICAL": {
        "bg": "#fef2f2",      # light red
        "color": "#b91c1c",   # strong red text
        "border": "#f87171"
    },
}

@admin.register(SystemLog)
class SystemLogAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'colored_level', 'event_name', 'actor_type', 'actor_email', 'business_id', 'service_name', 'ip_address')
    list_filter = ('log_level', 'actor_type', 'event_name', 'service_name', 'timestamp')
    search_fields = ('message', 'event_name', 'actor_id', 'actor_email', 'request_id', 'ip_address')
    readonly_fields = (
        'timestamp', 'log_level', 'event_name', 'message', 'actor_type', 'actor_id', 'actor_email', 'business_id',
        'model_name', 'file_name', 'function_name', 'traceback', 'metadata',
        'service_name', 'request_id', 'ip_address', 'user_agent', 'created_at'
    )

    def colored_level(self, obj):
        style = LEVEL_STYLES.get(obj.log_level, {"bg": "#f3f4f6", "color": "#374151", "border": "#d1d5db"})
        return format_html(
            '<span style="'
            'background-color:{bg};'
            'color:{color};'
            'border:1px solid {border};'
            'padding:2px 0;'
            'border-radius:12px;'
            'font-size:11px;'
            'font-weight:700;'
            'letter-spacing:0.5px;'
            'display:inline-block;'
            'min-width:72px;'
            'text-align:center;'
            '">{level}</span>',
            bg=style["bg"],
            color=style["color"],
            border=style["border"],
            level=obj.log_level,
        )

    colored_level.short_description = "Level"
    colored_level.admin_order_field = "log_level"

    # Strictly no modifications to immutable logs
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
