from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.admin.sites import AdminSite
from django.test import RequestFactory, TestCase
from django.urls import reverse

from web.accounts.admin import ApplicationUserAdmin
from web.assistant.models import Conversation


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


class AccessRequestTests(TestCase):
    def setUp(self):
        self.superuser = get_user_model().objects.create_superuser(
            username="superuser",
            email="superuser@example.org",
            password="password",
        )
        self.pending = get_user_model().objects.create_user(
            username="pending-user",
            email="pending@example.org",
            password="password",
            is_active=False,
        )

    def test_page_is_reserved_for_superusers(self):
        ordinary_user = get_user_model().objects.create_user(
            username="ordinary", password="password"
        )
        self.client.force_login(ordinary_user)

        response = self.client.get(reverse("access-requests"))

        self.assertEqual(response.status_code, 403)

    def test_superuser_can_approve_pending_account(self):
        self.client.force_login(self.superuser)

        response = self.client.post(
            reverse("access-requests"),
            {"user_id": self.pending.pk, "role": "analyst"},
            follow=True,
        )

        self.pending.refresh_from_db()
        self.assertTrue(self.pending.is_active)
        self.assertEqual(
            set(self.pending.groups.values_list("name", flat=True)), {"analyst"}
        )
        self.assertContains(response, "a été approuvé comme analyste")

    def test_superuser_can_edit_account_and_role(self):
        self.client.force_login(self.superuser)
        response = self.client.post(
            reverse("edit-account", args=[self.pending.pk]),
            {
                "username": "renamed-user",
                "email": "renamed@example.org",
                "first_name": "Prénom",
                "last_name": "Nom",
                "role": "analyst",
                "is_active": "on",
            },
            follow=True,
        )
        self.pending.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.pending.username, "renamed-user")
        self.assertTrue(self.pending.is_active)
        self.assertEqual(
            set(self.pending.groups.values_list("name", flat=True)), {"analyst"}
        )

    def test_superuser_can_delete_another_superuser_and_conversations(self):
        target = get_user_model().objects.create_superuser(
            username="target-admin", email="target@example.org", password="password"
        )
        Conversation.objects.create(user=target, title="À supprimer")
        self.client.force_login(self.superuser)

        response = self.client.post(
            reverse("delete-account", args=[target.pk]), follow=True
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(get_user_model().objects.filter(pk=target.pk).exists())
        self.assertFalse(Conversation.objects.filter(user_id=target.pk).exists())
        self.assertContains(response, "1 conversation(s) ont été supprimés")

    def test_superuser_cannot_delete_own_account(self):
        self.client.force_login(self.superuser)
        response = self.client.post(
            reverse("delete-account", args=[self.superuser.pk]), follow=True
        )
        self.assertTrue(
            get_user_model().objects.filter(pk=self.superuser.pk).exists()
        )
        self.assertContains(response, "ne pouvez pas supprimer votre propre compte")

    def test_last_active_superuser_cannot_be_demoted(self):
        self.client.force_login(self.superuser)
        response = self.client.post(
            reverse("edit-account", args=[self.superuser.pk]),
            {
                "username": self.superuser.username,
                "email": self.superuser.email,
                "role": "administrator",
                "is_active": "on",
                "is_staff": "on",
            },
        )
        self.superuser.refresh_from_db()
        self.assertTrue(self.superuser.is_superuser)
        self.assertContains(response, "dernier superuser actif")
