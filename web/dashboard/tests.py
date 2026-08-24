from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from unittest.mock import call, patch

from web.accounts.services import ROLE_NAMES, assign_role
from web.analytics.client import AnalyticsAPIError


SCORE = {
    "geographic_level": "department",
    "geographic_code": "59",
    "geographic_name": "Nord",
    "reference_period": "2025",
    "score": 42.5,
    "coverage_ratio": 0.9,
    "status": "valid",
    "model": {"code": "default", "version": "1.2.0"},
    "details": [],
}

MODEL = {
    "code": "default",
    "name": "Modèle territorial",
    "version": "1.2.0",
    "is_active": True,
    "indicators": [],
}


class DashboardTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.password = "test-password-with-length"
        cls.viewer = get_user_model().objects.create_user(
            username="viewer",
            password=cls.password,
        )
        assign_role(cls.viewer, "viewer")
        cls.unassigned = get_user_model().objects.create_user(
            username="unassigned",
            password=cls.password,
        )

    def test_home_is_public_and_explains_statistical_scope(self):
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "aucun diagnostic")

    def test_dashboard_redirects_anonymous_users_to_login(self):
        response = self.client.get(reverse("dashboard"))
        self.assertRedirects(
            response,
            f"{reverse('login')}?next={reverse('dashboard')}",
        )

    @patch("web.dashboard.views.AnalyticsClient")
    def test_viewer_can_access_dashboard(self, client_class):
        analytics = client_class.return_value
        analytics.list_models.return_value = [MODEL]
        analytics.list_scores.return_value = [SCORE]
        analytics.get_series.return_value = {
            "series": [SCORE],
            "count": 1,
        }
        analytics.get_factors.return_value = {"factors": []}
        analytics.get_observability.return_value = {"status": "ok"}
        self.client.force_login(self.viewer)
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "42,50")
        self.assertIn(
            {"active_model_only": True, "include_details": False},
            [call.kwargs for call in analytics.list_scores.call_args_list],
        )
        analytics.get_series.assert_called_once_with(
            "department",
            "59",
            model_version="1.2.0",
        )

    @patch("web.dashboard.views.AnalyticsClient")
    def test_dashboard_handles_unavailable_analytical_api(self, client_class):
        client_class.return_value.list_models.side_effect = AnalyticsAPIError(
            "Le service analytique est temporairement indisponible."
        )
        self.client.force_login(self.viewer)
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "temporairement indisponible")

    def test_user_without_role_is_forbidden(self):
        self.client.force_login(self.unassigned)
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 403)

    @patch("web.dashboard.views.AnalyticsClient")
    def test_viewer_can_access_methodology(self, client_class):
        client_class.return_value.list_models.return_value = [MODEL]
        self.client.force_login(self.viewer)

        response = self.client.get(reverse("methodology"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Méthodologie et lexique")
        self.assertContains(response, "Modèle 1.2.0")
        client_class.return_value.list_models.assert_called_once_with(active_only=True)

    def test_user_without_role_cannot_access_methodology(self):
        self.client.force_login(self.unassigned)
        response = self.client.get(reverse("methodology"))
        self.assertEqual(response.status_code, 403)

    def test_login_redirects_to_dashboard(self):
        response = self.client.post(
            reverse("login"),
            {"username": self.viewer.username, "password": self.password},
        )
        self.assertRedirects(
            response,
            reverse("dashboard"),
            fetch_redirect_response=False,
        )

    def test_health_checks_database(self):
        response = self.client.get(reverse("health"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"status": "healthy", "database": "ok"},
        )

    def test_roles_and_permissions_are_seeded(self):
        self.assertEqual(
            set(Group.objects.filter(name__in=ROLE_NAMES).values_list(
                "name",
                flat=True,
            )),
            set(ROLE_NAMES),
        )
        self.assertTrue(self.viewer.has_perm("accounts.view_dashboard"))
        with self.assertRaises(ValidationError):
            assign_role(self.viewer, "unsupported")


class DataQualityTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.superuser = get_user_model().objects.create_superuser(
            username="quality-admin", password="test-password"
        )
        cls.viewer = get_user_model().objects.create_user(
            username="quality-viewer", password="test-password"
        )
        assign_role(cls.viewer, "viewer")

    def test_page_is_reserved_for_superusers(self):
        self.client.force_login(self.viewer)
        response = self.client.get(reverse("data-quality"))
        self.assertEqual(response.status_code, 403)

    @patch("web.dashboard.views.AnalyticsClient")
    def test_superuser_can_view_quality_report(self, client_class):
        client_class.return_value.get_observability.return_value = {
            "status": "ok",
            "generated_at": "2026-08-24T12:00:00+00:00",
            "alerts": [],
            "operational": {
                "counts": {"source_documents": 12, "observations": 240, "risk_scores": 30, "pipeline_runs": 4},
                "document_statuses": [], "pipeline_versions": [],
                "indicator_freshness": [], "pipeline_runs": [],
                "missing_regional_dossiers": [], "needs_review": [],
                "integrity": {"foreign_key_violations": 0, "indicator_code_mismatches": 0},
            },
            "analytics": {"integrity": {"foreign_key_violations": 0, "departments_without_region": 0}},
        }
        self.client.force_login(self.superuser)
        response = self.client.get(reverse("data-quality"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Qualité et extraction des données")
        self.assertContains(response, "240")
        client_class.return_value.get_observability.assert_called_once_with()
