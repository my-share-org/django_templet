from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _
from authentication.models import Role, User, UserRole


class UserRoleInline(admin.TabularInline):
    model = UserRole
    extra = 1
    fields = ("role", "created_at")
    readonly_fields = ("created_at",)


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "is_system", "created_at")
    list_filter = ("is_system",)
    search_fields = ("code", "name", "description")
    filter_horizontal = ("permissions", "groups")
    readonly_fields = ("created_at", "updated_at")
    ordering = ("name",)

    def get_readonly_fields(self, request, obj=None):
        readonly = list(super().get_readonly_fields(request, obj))
        if obj and obj.is_system:
            readonly.extend(["code", "is_system"])
        return readonly


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ("email",)
    list_display = (
        "email",
        "first_name",
        "last_name",
        "is_staff",
        "is_active",
        "date_joined",
    )
    list_filter = ("is_staff", "is_active", "is_superuser")
    search_fields = ("email", "first_name", "last_name")
    inlines = [UserRoleInline]

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (_("Personal info"), {"fields": ("first_name", "last_name")}),
        (
            _("Permissions"),
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        (_("Important dates"), {"fields": ("last_login", "date_joined")}),
    )

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "password1",
                    "password2",
                    "is_staff",
                    "is_active",
                ),
            },
        ),
    )

    readonly_fields = ("date_joined", "last_login")
