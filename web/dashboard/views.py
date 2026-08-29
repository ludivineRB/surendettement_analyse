from django.contrib.auth.decorators import login_required, permission_required
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.db import connection
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET
import requests

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
        "territory_selected": False,
    }
    try:
        models = client.list_models()
        catalog = client.list_scores(
            active_model_only=True,
            include_details=False,
        )
        defaults = dashboard_defaults(catalog, models)
        selected_values = defaults.copy()
        selected_values.update(request.GET.dict())
        requested_level = request.GET.get("geographic_level")
        requested_code = request.GET.get("geographic_code")
        if requested_level and requested_code:
            territory_scores = [
                item
                for item in catalog
                if item["geographic_level"] == requested_level
                and item["geographic_code"] == requested_code
            ]
            if territory_scores:
                selected_values["reference_period"] = max(
                    item["reference_period"] for item in territory_scores
                )
                context["territory_selected"] = True
        form = DashboardFilterForm(
            selected_values,
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


@login_required
def data_quality(request):
    if not request.user.is_superuser:
        raise PermissionDenied
    report = None
    analytics_error = None
    try:
        report = AnalyticsClient().get_observability()
    except AnalyticsAPIError as exc:
        analytics_error = str(exc)
    return render(
        request,
        "dashboard/data_quality.html",
        {"report": report, "analytics_error": analytics_error},
    )


@login_required
@permission_required("accounts.view_dashboard", raise_exception=True)
def methodology(request):
    model = None
    analytics_error = None
    try:
        models = AnalyticsClient().list_models(active_only=True)
        model = models[0] if models else None
    except AnalyticsAPIError as exc:
        analytics_error = str(exc)
    indicator_labels = {
        "dossiers_surendettement_1000_habitants": "Dossiers de surendettement pour 1 000 habitants",
        "taux_chomage": "Taux de chômage",
        "taux_pauvrete": "Taux de pauvreté",
        "revenu_median": "Revenu médian",
        "endettement_moyen": "Endettement moyen",
        "inflation": "Inflation",
    }
    if model:
        for indicator in model.get("indicators", []):
            indicator["display_label"] = indicator_labels.get(
                indicator.get("logical_code"), indicator.get("logical_code", "Indicateur")
            )
    return render(
        request,
        "dashboard/methodology.html",
        {"model": model, "analytics_error": analytics_error},
    )


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


@require_GET
@login_required
@permission_required("accounts.view_dashboard", raise_exception=True)
def territorial_indicators(request):
    client = AnalyticsClient()
    try:
        if request.GET.get("catalog") == "1":
            payload = client.territorial_indicator_catalog()
        else:
            payload = client.territorial_indicator_data(
                source=request.GET.get("source"),
                indicator_code=request.GET.get("indicator_code"),
                geographic_level=request.GET.get("geographic_level"),
                from_period=request.GET.get("from_period"),
                to_period=request.GET.get("to_period"),
            )
    except AnalyticsAPIError as exc:
        return JsonResponse({"detail": str(exc)}, status=503)
    return JsonResponse(payload, safe=False)


@require_GET
@login_required
@permission_required("accounts.view_dashboard", raise_exception=True)
def territorial_boundaries(request):
    level = request.GET.get("level")
    filenames = {
        "department": "departements-1000m.geojson",
        "region": "regions-1000m.geojson",
    }
    if level not in filenames:
        return JsonResponse({"detail": "Niveau géographique invalide."}, status=400)
    cache_key = f"territorial-boundaries:{level}"
    payload = cache.get(cache_key)
    if payload is None:
        try:
            response = requests.get(
                "https://etalab-datasets.geo.data.gouv.fr/"
                "contours-administratifs/latest/geojson/"
                + filenames[level],
                timeout=20,
            )
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError):
            return JsonResponse(
                {"detail": "Les contours territoriaux sont indisponibles."},
                status=503,
            )
        cache.set(cache_key, payload, timeout=86_400)
    return JsonResponse(payload)
