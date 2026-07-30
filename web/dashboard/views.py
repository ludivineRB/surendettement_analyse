from django.contrib.auth.decorators import login_required, permission_required
from django.db import connection
from django.http import JsonResponse
from django.shortcuts import render

from web.analytics.client import AnalyticsAPIError, AnalyticsClient
from web.dashboard.forms import DashboardFilterForm, dashboard_defaults


def home(request):
    return render(request, "home.html")


@login_required
@permission_required("accounts.view_dashboard", raise_exception=True)
def dashboard(request):
    client = AnalyticsClient()
    context = {
        "form": None,
        "score": None,
        "factors": [],
        "series": [],
        "period_comparison": [],
        "model_comparison": None,
        "observability": None,
        "analytics_error": None,
    }
    try:
        models = client.list_models()
        catalog = client.list_scores(active_model_only=True)
        defaults = dashboard_defaults(catalog, models)
        form = DashboardFilterForm(
            request.GET or defaults,
            scores=catalog,
            models=models,
        )
        context["form"] = form
        if not form.is_valid():
            return render(request, "dashboard/index.html", context)

        filters = form.cleaned_data
        scores = client.list_scores(
            geographic_level=filters["geographic_level"],
            geographic_code=filters["geographic_code"],
            reference_period=filters["reference_period"],
            model_code="default",
            model_version=filters["model_version"],
            limit=1,
        )
        context["score"] = scores[0] if scores else None
        series_response = client.get_series(
            filters["geographic_level"],
            filters["geographic_code"],
            model_version=filters["model_version"],
        )
        context["series"] = series_response["series"]
        if context["score"]:
            factor_response = client.get_factors(
                filters["geographic_level"],
                filters["geographic_code"],
                filters["reference_period"],
                model_version=filters["model_version"],
            )
            context["factors"] = factor_response["factors"]

        comparison_period = filters.get("comparison_period")
        if comparison_period:
            compared_periods = {
                filters["reference_period"],
                comparison_period,
            }
            context["period_comparison"] = [
                item
                for item in context["series"]
                if item["reference_period"] in compared_periods
            ]

        comparison_version = filters.get("comparison_model_version")
        if comparison_version:
            context["model_comparison"] = client.compare_models(
                version_a=filters["model_version"],
                version_b=comparison_version,
                geographic_level=filters["geographic_level"],
                reference_period=filters["reference_period"],
            )
        context["observability"] = client.get_observability()
    except AnalyticsAPIError as exc:
        context["analytics_error"] = str(exc)
    return render(request, "dashboard/index.html", context)


def health(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:
        return JsonResponse(
            {"status": "unhealthy", "database": "unavailable"},
            status=503,
        )
    return JsonResponse({"status": "healthy", "database": "ok"})
