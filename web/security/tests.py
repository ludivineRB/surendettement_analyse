from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import RequestFactory, SimpleTestCase, override_settings

from web.security.middleware import RequestSecurityMiddleware


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


def _response():
    from django.http import HttpResponse

    return HttpResponse("ok")


def _anonymous():
    from django.contrib.auth.models import AnonymousUser

    return AnonymousUser()
