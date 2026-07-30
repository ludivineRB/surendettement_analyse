from django.db import migrations


ROLE_PERMISSIONS = {
    "viewer": {"view_dashboard"},
    "analyst": {"view_dashboard", "use_analytics"},
    "administrator": {
        "view_dashboard",
        "use_analytics",
        "manage_application",
    },
}


def create_roles(apps, schema_editor):
    ContentType = apps.get_model("contenttypes", "ContentType")
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")

    content_type, _ = ContentType.objects.get_or_create(
        app_label="accounts",
        model="role",
    )
    permissions = {}
    for codename, name in (
        ("view_dashboard", "Can view the analytical dashboard"),
        ("use_analytics", "Can use analytical features"),
        ("manage_application", "Can administer the web application"),
    ):
        permission, _ = Permission.objects.get_or_create(
            content_type=content_type,
            codename=codename,
            defaults={"name": name},
        )
        permissions[codename] = permission

    for role, codenames in ROLE_PERMISSIONS.items():
        group, _ = Group.objects.get_or_create(name=role)
        group.permissions.set(permissions[codename] for codename in codenames)


def remove_roles(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Group.objects.filter(name__in=ROLE_PERMISSIONS).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
        ("contenttypes", "0002_remove_content_type_name"),
    ]

    operations = [
        migrations.RunPython(create_roles, remove_roles),
    ]
