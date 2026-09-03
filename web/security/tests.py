import json
import logging
import sys

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import RequestFactory, SimpleTestCase, override_settings

from web.security.middleware import RequestSecurityMiddleware
from web.security.logging import JSONFormatter


@override_settings(
    RATE_LIMIT_REQUESTS=2,
    RATE_LIMIT_WINDOW_SECONDS=60,
    LOGIN_RATE_LIMIT_REQUESTS=1,
    LOGIN_RATE_LIMIT_WINDOW_SECONDS=60,
    INFORMATION_DAILY_QUOTA=1,
    SQL_DAILY_QUOTA=1,
)
class RequestSecurityMiddlewareTests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.factory = RequestFactory()
        self.middleware = RequestSecurityMiddleware(lambda request: _response())

    def test_adds_or_replaces_request_identifier(self):
        request = self.factory.get("/", HTTP_X_REQUEST_ID="invalid")
        request.user = _anonymous()
        response = self.middleware(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response["X-Request-ID"]), 36)

    def test_general_rate_limit_returns_429(self):
        for _ in range(2):
            request = self.factory.get("/", REMOTE_ADDR="192.0.2.1")
            request.user = _anonymous()
            self.middleware(request)
        request = self.factory.get("/", REMOTE_ADDR="192.0.2.1")
        request.user = _anonymous()
        self.assertEqual(self.middleware(request).status_code, 429)


class JSONFormatterTests(SimpleTestCase):
    def _record(self, message, exc_info=None):
        return logging.LogRecord(
            "web.requests", logging.INFO, __file__, 1, message, (), exc_info
        )

    def test_redacts_supported_credential_fields(self):
        for field in ("password", "token", "secret", "authorization"):
            with self.subTest(field=field):
                payload = json.loads(
                    JSONFormatter().format(self._record(f"{field}=visible-value"))
                )

                self.assertEqual(payload["message"], f"{field}=[REDACTED]")
                self.assertNotIn("visible-value", str(payload))

    def test_ignores_actor_identifier(self):
        record = self._record("request completed")
        record.request_id = "8ec1389e-49c7-42fe-ab81-2d6476309a35"
        record.actor_id = "42"

        payload = json.loads(JSONFormatter().format(record))

        self.assertNotIn("actor_id", payload)

    def test_redacts_credentials_from_exception(self):
        try:
            raise ValueError("password=visible-value")
        except ValueError:
            record = self._record("request failed", sys.exc_info())

        payload = json.loads(JSONFormatter().format(record))

        self.assertIn("password=[REDACTED]", payload["exception"])
        self.assertNotIn("visible-value", payload["exception"])


def _response():
    from django.http import HttpResponse

    return HttpResponse("ok")


def _anonymous():
    from django.contrib.auth.models import AnonymousUser

    return AnonymousUser()
