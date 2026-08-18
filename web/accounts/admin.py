"""Administration of registrations and application roles."""

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin

from web.accounts.services import assign_role


User = get_user_model()


class ApplicationUserAdmin(UserAdmin):
    actions = (
        "approve_as_viewer",
        "approve_as_analyst",
        "approve_as_administrator",
    )
    list_display = UserAdmin.list_display + ("application_role", "is_active")
    list_filter = UserAdmin.list_filter + ("groups",)

    @admin.display(description="Rôle applicatif")
    def application_role(self, user):
        role = user.groups.filter(
            name__in=("viewer", "analyst", "administrator")
        ).values_list("name", flat=True).first()
        return role or "En attente"

    def _approve(self, request, queryset, role):
        approved = 0
        for user in queryset:
            assign_role(user, role)
            if not user.is_active:
                user.is_active = True
                user.save(update_fields=("is_active",))
            approved += 1
        self.message_user(
            request,
            f"{approved} compte(s) approuvé(s) avec le rôle {role}.",
        )

    @admin.action(description="Approuver avec le rôle lecteur")
    def approve_as_viewer(self, request, queryset):
        self._approve(request, queryset, "viewer")

    @admin.action(description="Approuver avec le rôle analyste")
    def approve_as_analyst(self, request, queryset):
        self._approve(request, queryset, "analyst")

    @admin.action(description="Approuver avec le rôle administrateur applicatif")
    def approve_as_administrator(self, request, queryset):
        self._approve(request, queryset, "administrator")


admin.site.unregister(User)
admin.site.register(User, ApplicationUserAdmin)
