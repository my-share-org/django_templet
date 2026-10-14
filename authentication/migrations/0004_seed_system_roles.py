from django.db import migrations

INITIAL_SYSTEM_ROLES = [
    {
        "code": "SUPER_ADMIN",
        "name": "Super Administrator",
        "description": "Full system administration, configuration management, and user lifecycle control.",
        "is_system": True,
    },
    {
        "code": "ADMIN",
        "name": "Administrator",
        "description": "General administrative access for day-to-day operations and staff management.",
        "is_system": True,
    },
    {
        "code": "PROJECT_MANAGER",
        "name": "Project Manager",
        "description": "Management of projects, team assignments, deliverables, and workflow status.",
        "is_system": True,
    },
    {
        "code": "DEVELOPER",
        "name": "Developer",
        "description": "Technical and development access for building, integrating, and reviewing features.",
        "is_system": True,
    },
    {
        "code": "USER",
        "name": "Standard User",
        "description": "Default authenticated user with standard self-service privileges.",
        "is_system": True,
    },
]


def seed_system_roles(apps, schema_editor):
    Role = apps.get_model("authentication", "Role")
    for role_data in INITIAL_SYSTEM_ROLES:
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
    codes = [r["code"] for r in INITIAL_SYSTEM_ROLES]
    Role.objects.filter(code__in=codes, is_system=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0003_role_userrole_user_roles_and_more"),
    ]

    operations = [
        migrations.RunPython(seed_system_roles, reverse_code=rollback_system_roles),
    ]
