import json
import logging

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
    def test_redacts_credentials_and_ignores_actor_identifier(self):
        record = logging.LogRecord(
            "web.requests",
            logging.INFO,
            __file__,
            1,
            "request failed token=visible-secret",
            (),
            None,
        )
        record.request_id = "8ec1389e-49c7-42fe-ab81-2d6476309a35"
        record.actor_id = "42"

        payload = json.loads(JSONFormatter().format(record))

        self.assertEqual(payload["message"], "request failed token=[REDACTED]")
        self.assertNotIn("visible-secret", str(payload))
        self.assertNotIn("actor_id", payload)


def _response():
    from django.http import HttpResponse

    return HttpResponse("ok")


def _anonymous():
    from django.contrib.auth.models import AnonymousUser

    return AnonymousUser()
