from django.contrib import admin
from .models import EmailLog


@admin.register(EmailLog)
class EmailLogAdmin(admin.ModelAdmin):
    list_display = ("subject", "to_emails", "from_email", "purpose", "status", "try_count", "created_at")
    list_filter = ("purpose", "status", "body_type", "created_at")
    search_fields = ("subject", "to_emails", "from_email")
    readonly_fields = ("created_at", "updated_at", "deleted_at")
