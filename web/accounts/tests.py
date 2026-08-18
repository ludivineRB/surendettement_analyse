from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.admin.sites import AdminSite
from django.test import RequestFactory, TestCase
from django.urls import reverse

from web.accounts.admin import ApplicationUserAdmin


class RegistrationTests(TestCase):
    def test_registration_creates_inactive_user_without_role(self):
        response = self.client.post(
            reverse("register"),
            {
                "username": "new-user",
                "email": "new@example.org",
                "password1": "a-long-test-password-42",
                "password2": "a-long-test-password-42",
            },
            follow=True,
        )
        user = get_user_model().objects.get(username="new-user")
        self.assertFalse(user.is_active)
        self.assertEqual(user.groups.count(), 0)
        self.assertContains(response, "administrateur doit maintenant valider")

    def test_admin_action_activates_user_and_assigns_role(self):
        user = get_user_model().objects.create_user(
            username="pending", is_active=False
        )
        request = RequestFactory().post("/admin/")
        request.user = get_user_model().objects.create_superuser(
            username="admin", email="admin@example.org", password="password"
        )
        model_admin = ApplicationUserAdmin(get_user_model(), AdminSite())
        model_admin.message_user = lambda *args, **kwargs: None

        model_admin.approve_as_analyst(
            request, get_user_model().objects.filter(pk=user.pk)
        )

        user.refresh_from_db()
        self.assertTrue(user.is_active)
        self.assertEqual(
            set(user.groups.values_list("name", flat=True)), {"analyst"}
        )
        self.assertTrue(Group.objects.filter(name="analyst").exists())
