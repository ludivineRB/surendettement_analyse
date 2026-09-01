from contextlib import contextmanager
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from pydantic import TypeAdapter

from app.main import app
from app.schemas.analytics import IndicatorRead, SurendettementObservationRead
from app.views.analytics_api import list_indicators, list_surendettement_data
from assistant_api.auth import require_internal_token


@contextmanager
def _connection():
    yield object()


def test_data_access_requires_valid_internal_token(monkeypatch):
    monkeypatch.setenv("ASSISTANT_INTERNAL_TOKEN", "test-token")

    with pytest.raises(HTTPException) as missing:
        require_internal_token(None)
    with pytest.raises(HTTPException) as invalid:
        require_internal_token("wrong-token")

    assert missing.value.status_code == 401
    assert invalid.value.status_code == 403
    assert require_internal_token("test-token") is None


@patch("app.views.analytics_api.fetch_all")
@patch("app.views.analytics_api.analytics_connection", _connection)
def test_surendettement_filters_pagination_and_json_contract(fetch_all):
    fetch_all.return_value = [
        {
            "reference_year": 2024,
            "departement_code": "59",
            "departement_name": "Nord",
            "region_name": "Hauts-de-France",
            "indicator_code": "surendettement_dossiers_deposes",
            "indicator_name": "Dossiers déposés",
            "indicator_group": "surendettement",
            "unit": "dossiers",
            "value": 1234,
            "surendettement_value": 1234,
            "dossiers_deposes": 1234,
            "source_file": "statistiques.xlsx",
        }
    ]

    rows = list_surendettement_data(
        departement_code="59",
        indicator_code="surendettement_dossiers_deposes",
        reference_year=2024,
        limit=25,
        offset=50,
    )
    payload = TypeAdapter(list[SurendettementObservationRead]).validate_python(rows)

    assert payload[0].departement_name == "Nord"
    params = fetch_all.call_args.args[2]
    assert params == {
        "departement_code": "59",
        "indicator_code": "surendettement_dossiers_deposes",
        "reference_year": 2024,
        "limit": 25,
        "offset": 50,
    }


@patch("app.views.analytics_api.fetch_all")
@patch("app.views.analytics_api.analytics_connection", _connection)
def test_indicator_contract_accepts_real_textual_business_key(fetch_all):
    fetch_all.return_value = [
        {
            "indicator_key": "bdf_statinfo:autres_livrets",
            "source_system": "bdf_statinfo",
            "indicator_code": "autres_livrets",
            "indicator_name": "Autres livrets",
            "indicator_group": "inclusion_financiere",
            "unit": "nombre",
            "aggregation_rule": "sum",
        }
    ]

    rows = list_indicators(source_system=None, limit=2, offset=0)
    payload = TypeAdapter(list[IndicatorRead]).validate_python(rows)

    assert payload[0].indicator_key == "bdf_statinfo:autres_livrets"


def test_openapi_documents_validation_readonly_and_security():
    schema = app.openapi()
    operation = schema["paths"]["/api/data/surendettement"]["get"]
    health_operation = schema["paths"]["/api/data/health"]["get"]
    limit = next(item for item in operation["parameters"] if item["name"] == "limit")

    assert set(schema["paths"]["/api/data/surendettement"]) == {"get"}
    assert limit["schema"]["maximum"] == 500
    assert operation["security"] == [{"InternalToken": []}]
    assert "security" not in health_operation
    assert "200" in operation["responses"]
    assert "422" in operation["responses"]
    assert schema["components"]["securitySchemes"]["InternalToken"] == {
        "type": "apiKey",
        "in": "header",
        "name": "X-Internal-Token",
        "description": (
            "Jeton interne fourni par la variable d'environnement "
            "ASSISTANT_INTERNAL_TOKEN."
        ),
    }
