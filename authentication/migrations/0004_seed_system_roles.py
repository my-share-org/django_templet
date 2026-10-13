from django.db import migrations
from authentication.roles import DEFAULT_SYSTEM_ROLES


def seed_system_roles(apps, schema_editor):
    Role = apps.get_model("authentication", "Role")
    for role_data in DEFAULT_SYSTEM_ROLES:
        Role.objects.get_or_create(
            code=role_data["code"],
            defaults={
                "name": role_data["name"],
                "description": role_data["description"],
                "is_system": role_data["is_system"],
            },
        )


def rollback_system_roles(apps, schema_editor):
    Role = apps.get_model("authentication", "Role")
    codes = [r["code"] for r in DEFAULT_SYSTEM_ROLES]
    Role.objects.filter(code__in=codes, is_system=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0003_role_userrole_user_roles_and_more"),
    ]

    operations = [
        migrations.RunPython(seed_system_roles, reverse_code=rollback_system_roles),
    ]
