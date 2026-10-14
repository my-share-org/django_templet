import re
from django.contrib.auth.models import AbstractBaseUser, Group, Permission, PermissionsMixin
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from authentication.managers.user import UserManager
from core.models import BaseModel


class Role(BaseModel):
    """
    Database model representing an authorization role.
    Roles have direct permissions and can also contain permission groups (django.contrib.auth.models.Group).
    """
    code = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        help_text="Unique, stable programmatic code for role (e.g. SUPER_ADMIN, PROJECT_MANAGER).",
    )
    name = models.CharField(
        max_length=100,
        help_text="Human-readable display name for the role.",
    )
    description = models.TextField(
        blank=True,
        default="",
        help_text="Optional description of the role's responsibilities.",
    )
    is_system = models.BooleanField(
        default=False,
        db_index=True,
        help_text="System-defined roles cannot be deleted or have their codes modified.",
    )
    permissions = models.ManyToManyField(
        Permission,
        blank=True,
        related_name="roles",
        help_text="Permissions assigned directly to this role.",
    )
    groups = models.ManyToManyField(
        Group,
        blank=True,
        related_name="roles",
        help_text="Permission groups assigned to this role.",
    )

    class Meta:
        ordering = ["name"]
        verbose_name = "Role"
        verbose_name_plural = "Roles"

    def clean(self):
        super().clean()
        if self.code:
            self.code = self.code.strip().upper()
            if not re.match(r"^[A-Z0-9_]+$", self.code):
                raise ValidationError({
                    "code": "Role code must only contain uppercase letters, numbers, and underscores."
                })
        if self.pk:
            original = Role.all_objects.filter(pk=self.pk).first()
            if original and original.is_system and original.code != self.code:
                raise ValidationError({"code": "System role code cannot be modified."})

    def save(self, *args, **kwargs):
        if self.code:
            self.code = self.code.strip().upper()
            if not re.match(r"^[A-Z0-9_]+$", self.code):
                raise ValidationError({
                    "code": "Role code must only contain uppercase letters, numbers, and underscores."
                })
        if self.pk:
            original = Role.all_objects.filter(pk=self.pk).first()
            if original and original.is_system and original.code != self.code:
                raise ValidationError({"code": "System role code cannot be modified."})
        super().save(*args, **kwargs)

    def soft_delete(self):
        if self.is_system:
            raise ValidationError("System-defined roles cannot be soft-deleted.")
        super().soft_delete()

    def delete(self, using=None, keep_parents=False):
        if self.is_system:
            raise ValidationError("System-defined roles cannot be deleted.")
        return super().delete(using=using, keep_parents=keep_parents)

    def __str__(self):
        return f"{self.name} ({self.code})"


class UserRole(BaseModel):
    """
    Explicit intermediary through model for User to Role many-to-many relationship.
    Maintains audit timestamps and soft-delete capabilities.
    """
    user = models.ForeignKey(
        "authentication.User",
        on_delete=models.CASCADE,
        related_name="user_roles",
    )
    role = models.ForeignKey(
        Role,
        on_delete=models.CASCADE,
        related_name="user_roles",
    )

    class Meta:
        verbose_name = "User Role"
        verbose_name_plural = "User Roles"
        constraints = [
            models.UniqueConstraint(fields=["user", "role"], name="unique_user_role")
        ]


    def __str__(self):
        return f"{self.user} -> {self.role.code}"


class User(BaseModel, AbstractBaseUser, PermissionsMixin):
    email      = models.EmailField(unique=True, max_length=255)
    first_name = models.CharField(max_length=150, blank=True)
    last_name  = models.CharField(max_length=150, blank=True)

    is_active = models.BooleanField(default=True)
    is_staff  = models.BooleanField(default=False)

    date_joined = models.DateTimeField(default=timezone.now)

    roles = models.ManyToManyField(
        Role,
        through=UserRole,
        related_name="users",
        blank=True,
        help_text="Roles assigned to this user.",
    )

    # Overrides BaseModel's SoftDeleteManager — Django auth requires the default
    # manager to return all users, including soft-deleted ones.
    objects = UserManager()

    USERNAME_FIELD  = "email"
    REQUIRED_FIELDS = []

    def clear_permission_cache(self):
        """Clears cached effective permissions and role codes."""
        for attr in ("_cached_role_codes", "_cached_effective_permissions", "_role_perm_cache"):
            if hasattr(self, attr):
                delattr(self, attr)

    def __str__(self):
        return f"{self.id} - {self.email}"
