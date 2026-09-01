"""API routes to consume and curate analytical macro/surendettement data."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from app.core.analytics import (
    analytics_connection,
    database_objects,
    execute,
    fetch_all,
    fetch_one,
    table_columns,
    utc_now,
)
from app.schemas.analytics import (
    DepartmentRead,
    IndicatorRead,
    MacroOverrideCreate,
    MacroOverrideRead,
    MacroOverrideUpdate,
    SurendettementObservationRead,
)
from src.storage.database import get_session_factory
from src.storage.models import InclusionIndicator, InclusionObservation, InclusionSourceDocument
from src.observability import build_observability_report

analytics_api = APIRouter(prefix="/api/data", tags=["Analytical data"])
public_analytics_api = APIRouter(prefix="/api/data", tags=["Health"])

INDICATOR_POLARITY = {
    "risk_score": "higher_is_adverse",
    "taux_chomage": "higher_is_adverse",
    "taux_chomage_1564": "higher_is_adverse",
    "taux_pauvrete": "higher_is_adverse",
    "inflation": "higher_is_adverse",
    "dossiers_surendettement_1000_habitants": "higher_is_adverse",
    "surendettement_dossiers_deposes": "higher_is_adverse",
    "endettement_moyen": "higher_is_adverse",
    "part_sans_diplome": "higher_is_adverse",
    "revenu_median": "higher_is_favorable",
    "part_diplomees_bac5": "higher_is_favorable",
    "taux_emploi_1564": "higher_is_favorable",
    "taux_activite_1564": "higher_is_favorable",
}


@analytics_api.get("/observability")
def observability() -> dict:
    """Expose freshness, completeness, integrity and active-model diagnostics."""
    return build_observability_report()


@public_analytics_api.get("/health")
def health() -> dict:
    try:
        with analytics_connection() as connection:
            objects = database_objects(connection)
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail={"status": "not_ready", "database": "unavailable"},
        ) from exc
    return {"status": "ok", "objects": objects}


@analytics_api.get("/territorial-indicators/catalog")
def territorial_indicator_catalog() -> list[dict]:
    """List only indicators and periods that are actually available."""
    catalog: list[dict] = []
    with analytics_connection() as connection:
        score_rows = fetch_all(
            connection,
            """
            SELECT geographic_level, MIN(reference_period) AS period_min,
                   MAX(reference_period) AS period_max,
                   COUNT(DISTINCT reference_period) AS period_count
            FROM analytics_risk_scores
            WHERE model_is_active = TRUE
            GROUP BY geographic_level
            """,
        )
        for row in score_rows:
            catalog.append({
                "source": "risk_score", "code": "risk_score",
                "label": "Score territorial", "group": "surendettement",
                "level": row["geographic_level"], "unit": "score",
                "period_min": row["period_min"], "period_max": row["period_max"],
                "period_count": row["period_count"],
                "polarity": INDICATOR_POLARITY["risk_score"],
            })
        observation_rows = fetch_all(
            connection,
            """
            SELECT o.indicator_code AS code, i.label,
                   o.geographic_level AS level, MAX(o.unit) AS unit,
                   MIN(o.reference_period) AS period_min,
                   MAX(o.reference_period) AS period_max,
                   COUNT(DISTINCT o.reference_period) AS period_count
            FROM observations o JOIN indicators i ON i.id = o.indicator_id
            GROUP BY o.indicator_code, i.label, o.geographic_level
            """,
        )
        for row in observation_rows:
            catalog.append({
                "source": "observations", "group": "indicateurs associés",
                **row,
                "polarity": INDICATOR_POLARITY.get(row["code"], "neutral"),
            })
        macro_rows = fetch_all(
            connection,
            """
            SELECT indicator_code AS code, indicator_name AS label,
                   indicator_group AS "group", 'region' AS level,
                   MIN(reference_year) AS period_min,
                   MAX(reference_year) AS period_max,
                   COUNT(DISTINCT reference_year) AS period_count
            FROM analytics_macro_regions
            GROUP BY indicator_code, indicator_name, indicator_group
            """,
        )
        for row in macro_rows:
            catalog.append({
                "source": "macro_regions", "unit": None, **row,
                "polarity": INDICATOR_POLARITY.get(row["code"], "neutral"),
            })
    return catalog


@analytics_api.get("/territorial-indicators/data")
def territorial_indicator_data(
    source: str,
    indicator_code: str,
    geographic_level: str,
    from_period: str | None = None,
    to_period: str | None = None,
) -> list[dict]:
    """Return bounded territorial values for maps and time series."""
    if geographic_level not in {"department", "region"}:
        raise HTTPException(status_code=400, detail="Invalid geographic level")
    filters = []
    params = {"level": geographic_level, "code": indicator_code}
    if source == "risk_score":
        period_column = "reference_period"
        query = """
            SELECT geographic_code, geographic_name, reference_period,
                   score AS value_numeric
            FROM analytics_risk_scores
            WHERE geographic_level = :level AND model_is_active = TRUE
        """
    elif source == "observations":
        period_column = "reference_period"
        query = """
            SELECT geographic_code, geographic_name, reference_period,
                   value_numeric
            FROM analytics_observations
            WHERE geographic_level = :level AND indicator_code = :code
        """
    elif source == "macro_regions" and geographic_level == "region":
        period_column = "reference_year"
        query = """
            SELECT NULL AS geographic_code, region_name AS geographic_name,
                   reference_year AS reference_period, value_numeric
            FROM analytics_macro_regions WHERE indicator_code = :code
        """
    else:
        raise HTTPException(status_code=400, detail="Invalid indicator source")
    if from_period:
        filters.append(f"{period_column} >= :from_period")
        params["from_period"] = from_period
    if to_period:
        filters.append(f"{period_column} <= :to_period")
        params["to_period"] = to_period
    if filters:
        query += " AND " + " AND ".join(filters)
    query += f" ORDER BY {period_column}, geographic_name LIMIT 10000"
    with analytics_connection() as connection:
        return fetch_all(connection, query, params)


@analytics_api.get(
    "/departments",
    response_model=list[DepartmentRead],
    summary="Référentiel des départements",
    description="Retourne les territoires réellement présents dans PostgreSQL.",
    responses={401: {"description": "Jeton absent"}, 403: {"description": "Jeton invalide"}},
)
def list_departments(
    limit: int = Query(200, ge=1, le=500, description="Nombre maximal de lignes"),
    offset: int = Query(0, ge=0, description="Décalage de pagination"),
) -> list[dict]:
    with analytics_connection() as connection:
        return fetch_all(
            connection,
            """
            SELECT departement_code, departement_name, region_name, is_metropolitan_scope
            FROM dim_department
            ORDER BY departement_code
            LIMIT :limit OFFSET :offset
            """,
            {"limit": limit, "offset": offset},
        )


@analytics_api.get(
    "/indicators",
    response_model=list[IndicatorRead],
    summary="Catalogue des indicateurs",
    description="Liste les indicateurs disponibles, filtrables par système source.",
    responses={401: {"description": "Jeton absent"}, 403: {"description": "Jeton invalide"}},
)
def list_indicators(
    source_system: Annotated[
        str | None, Query(description="Système source exact")
    ] = None,
    limit: int = Query(200, ge=1, le=500, description="Nombre maximal de lignes"),
    offset: int = Query(0, ge=0, description="Décalage de pagination"),
) -> list[dict]:
    where = "WHERE source_system = :source_system" if source_system else ""
    params = {"source_system": source_system, "limit": limit, "offset": offset}
    with analytics_connection() as connection:
        return fetch_all(
            connection,
            f"""
            SELECT indicator_key, source_system, indicator_code, indicator_name,
                   indicator_group, unit, aggregation_rule
            FROM dim_indicator
            {where}
            ORDER BY source_system, indicator_code
            LIMIT :limit OFFSET :offset
            """,
            params,
        )


@analytics_api.get("/bdf")
def list_bdf_facts(
    departement_code: str | None = None,
    indicator_code: str | None = None,
    reference_period: str | None = None,
    limit: int = Query(500, ge=1, le=5000),
    offset: int = Query(0, ge=0),
) -> list[dict]:
    filters = []
    params = {"limit": limit, "offset": offset}
    if departement_code:
        filters.append("b.departement_code = :departement_code")
        params["departement_code"] = _standardize_department_code(departement_code)
    if indicator_code:
        filters.append("i.indicator_code = :indicator_code")
        params["indicator_code"] = indicator_code
    if reference_period:
        filters.append("b.reference_period = :reference_period")
        params["reference_period"] = reference_period
    where = "WHERE " + " AND ".join(filters) if filters else ""
    with analytics_connection() as connection:
        return fetch_all(
            connection,
            f"""
            SELECT b.reference_period, b.reference_year, b.reference_month_number,
                   b.departement_code, d.departement_name, d.region_name,
                   i.indicator_code, i.indicator_name, i.indicator_group, i.unit,
                   b.value, b.source_file
            FROM fact_bdf_statinfo b
            JOIN dim_indicator i ON i.indicator_key = b.indicator_key
            LEFT JOIN dim_department d ON d.departement_code = b.departement_code
            {where}
            ORDER BY b.reference_period, b.departement_code, i.indicator_code
            LIMIT :limit OFFSET :offset
            """,
            params,
        )


@analytics_api.get(
    "/surendettement",
    response_model=list[SurendettementObservationRead],
    summary="Observations de surendettement",
    description=(
        "Extrait en lecture seule les observations annuelles par département "
        "depuis PostgreSQL. Aucun SQL libre n'est accepté."
    ),
    responses={401: {"description": "Jeton absent"}, 403: {"description": "Jeton invalide"}},
)
def list_surendettement_data(
    departement_code: Annotated[
        str | None, Query(description="Code département")
    ] = None,
    indicator_code: Annotated[
        str | None, Query(description="Code indicateur exact")
    ] = None,
    reference_year: Annotated[
        int | None,
        Query(ge=1900, le=2100, description="Année de référence"),
    ] = None,
    limit: int = Query(100, ge=1, le=500, description="Nombre maximal de lignes"),
    offset: int = Query(0, ge=0, description="Décalage de pagination"),
) -> list[dict]:
    """Expose actual over-indebtedness facts from the surendettement source."""
    filters = []
    params = {"limit": limit, "offset": offset}
    if departement_code:
        filters.append("s.departement_code = :departement_code")
        params["departement_code"] = _standardize_department_code(departement_code)
    if indicator_code:
        filters.append("i.indicator_code = :indicator_code")
        params["indicator_code"] = indicator_code
    if reference_year:
        filters.append("s.reference_year = :reference_year")
        params["reference_year"] = reference_year
    where = "WHERE " + " AND ".join(filters) if filters else ""
    with analytics_connection() as connection:
        return fetch_all(
            connection,
            f"""
            SELECT s.reference_year,
                   s.departement_code,
                   d.departement_name,
                   d.region_name,
                   i.indicator_code,
                   i.indicator_name,
                   i.indicator_group,
                   i.unit,
                   s.value,
                   s.value AS surendettement_value,
                   s.value AS dossiers_deposes,
                   s.source_file
            FROM fact_surendettement s
            JOIN dim_indicator i ON i.indicator_key = s.indicator_key
            LEFT JOIN dim_department d ON d.departement_code = s.departement_code
            {where}
            ORDER BY s.reference_year, s.departement_code, i.indicator_code
            LIMIT :limit OFFSET :offset
            """,
            params,
        )


@analytics_api.get("/inclusion-financiere")
def list_inclusion_financiere(
    region_code: str | None = None,
    indicator_code: str | None = None,
    from_period: str | None = None,
    to_period: str | None = None,
    limit: int = Query(5000, ge=1, le=100000),
    offset: int = Query(0, ge=0),
) -> list[dict]:
    """Expose monthly regional financial-inclusion observations."""
    statement = (
        select(
            InclusionObservation.reference_period,
            InclusionObservation.region_code,
            InclusionObservation.geographic_name.label("region_name"),
            InclusionIndicator.code.label("indicator_code"),
            InclusionIndicator.label.label("indicator_label"),
            InclusionObservation.value_numeric.label("value"),
            InclusionObservation.unit,
            InclusionObservation.observation_type,
            InclusionObservation.confidence_score,
            InclusionObservation.page_number,
            InclusionSourceDocument.page_url,
            InclusionSourceDocument.pdf_url,
        )
        .join(InclusionIndicator, InclusionIndicator.id == InclusionObservation.indicator_id)
        .join(InclusionSourceDocument, InclusionSourceDocument.id == InclusionObservation.source_document_id)
    )
    if region_code:
        statement = statement.where(InclusionObservation.region_code == region_code.strip())
    if indicator_code:
        statement = statement.where(InclusionIndicator.code == indicator_code)
    if from_period:
        statement = statement.where(InclusionObservation.reference_period >= from_period)
    if to_period:
        statement = statement.where(InclusionObservation.reference_period <= to_period)
    statement = statement.order_by(
        InclusionObservation.reference_period,
        InclusionObservation.region_code,
        InclusionObservation.indicator_code,
    ).limit(limit).offset(offset)

    factory = get_session_factory()
    with factory() as session:
        return [dict(row) for row in session.execute(statement).mappings().all()]


@analytics_api.get("/insee")
def list_insee_facts(
    departement_code: str | None = None,
    indicator_code: str | None = None,
    reference_year: int | None = None,
    limit: int = Query(500, ge=1, le=5000),
    offset: int = Query(0, ge=0),
) -> list[dict]:
    filters = []
    params = {"limit": limit, "offset": offset}
    if departement_code:
        filters.append("m.departement_code = :departement_code")
        params["departement_code"] = _standardize_department_code(departement_code)
    if indicator_code:
        filters.append("i.indicator_code = :indicator_code")
        params["indicator_code"] = indicator_code
    if reference_year:
        filters.append("m.reference_year = :reference_year")
        params["reference_year"] = reference_year
    where = "WHERE " + " AND ".join(filters) if filters else ""
    with analytics_connection() as connection:
        return fetch_all(
            connection,
            f"""
            SELECT m.reference_year, m.departement_code, d.departement_name, d.region_name,
                   i.indicator_code, i.indicator_name, i.indicator_group, i.aggregation_rule,
                   m.value, m.source_dataset
            FROM fact_insee_macro m
            JOIN dim_indicator i ON i.indicator_key = m.indicator_key
            LEFT JOIN dim_department d ON d.departement_code = m.departement_code
            {where}
            ORDER BY m.reference_year, m.departement_code, i.indicator_code
            LIMIT :limit OFFSET :offset
            """,
            params,
        )


@analytics_api.get("/macro-economic")
def list_macro_economic_data(
    departement_code: str | None = None,
    indicator_code: str | None = None,
    indicator_group: str | None = None,
    reference_year: int | None = None,
    limit: int = Query(5000, ge=1, le=100000),
    offset: int = Query(0, ge=0),
) -> list[dict]:
    """Expose INSEE macro-economic department-level facts."""
    filters = []
    params = {"limit": limit, "offset": offset}
    if departement_code:
        filters.append("m.departement_code = :departement_code")
        params["departement_code"] = _standardize_department_code(departement_code)
    if indicator_code:
        filters.append("i.indicator_code = :indicator_code")
        params["indicator_code"] = indicator_code
    if indicator_group:
        filters.append("i.indicator_group = :indicator_group")
        params["indicator_group"] = indicator_group
    if reference_year:
        filters.append("m.reference_year = :reference_year")
        params["reference_year"] = reference_year
    where = "WHERE " + " AND ".join(filters) if filters else ""
    with analytics_connection() as connection:
        return fetch_all(
            connection,
            f"""
            SELECT m.reference_year,
                   m.departement_code,
                   d.departement_name,
                   d.region_name,
                   i.indicator_code,
                   i.indicator_name,
                   i.indicator_group,
                   i.aggregation_rule,
                   m.value,
                   m.value AS macro_value,
                   m.source_dataset
            FROM fact_insee_macro m
            JOIN dim_indicator i ON i.indicator_key = m.indicator_key
            LEFT JOIN dim_department d ON d.departement_code = m.departement_code
            {where}
            ORDER BY m.reference_year, m.departement_code, i.indicator_code
            LIMIT :limit OFFSET :offset
            """,
            params,
        )


@analytics_api.get("/macro-economic-regions")
def list_regional_macro_economic_data(
    region_code: str | None = None,
    region_name: str | None = None,
    indicator_code: str | None = None,
    reference_year: int | None = None,
    limit: int = Query(5000, ge=1, le=100000),
    offset: int = Query(0, ge=0),
) -> list[dict]:
    """Expose the curated INSEE macro indicators aggregated by region."""
    filters = []
    params = {"limit": limit, "offset": offset}
    if region_code:
        filters.append("region_code = :region_code")
        params["region_code"] = region_code.strip()
    if region_name:
        filters.append("region_name = :region_name")
        params["region_name"] = region_name
    if indicator_code:
        filters.append("indicator_code = :indicator_code")
        params["indicator_code"] = indicator_code
    if reference_year:
        filters.append("reference_year = :reference_year")
        params["reference_year"] = reference_year
    where = "WHERE " + " AND ".join(filters) if filters else ""
    with analytics_connection() as connection:
        columns = table_columns(connection, "v_insee_macro_region_selected")
        if region_code and "region_code" not in columns:
            raise HTTPException(
                status_code=409,
                detail="Analytics schema migration required for region_code",
            )
        region_projection = (
            "region_code, region_name"
            if "region_code" in columns
            else "region_name"
        )
        return fetch_all(
            connection,
            f"""
            SELECT reference_year, {region_projection},
                   indicator_code, indicator_name,
                   indicator_group, aggregation_rule, value
            FROM v_insee_macro_region_selected
            {where}
            ORDER BY reference_year, region_name, indicator_code
            LIMIT :limit OFFSET :offset
            """,
            params,
        )


@analytics_api.get("/joined")
def list_joined_data(
    departement_code: str | None = None,
    macro_indicator_code: str | None = None,
    reference_period: str | None = None,
    limit: int = Query(500, ge=1, le=5000),
    offset: int = Query(0, ge=0),
) -> list[dict]:
    filters = []
    params = {"limit": limit, "offset": offset}
    if departement_code:
        filters.append("departement_code = :departement_code")
        params["departement_code"] = _standardize_department_code(departement_code)
    if macro_indicator_code:
        filters.append("macro_indicator_code = :macro_indicator_code")
        params["macro_indicator_code"] = macro_indicator_code
    if reference_period:
        filters.append("bdf_reference_period = :reference_period")
        params["reference_period"] = reference_period
    where = "WHERE " + " AND ".join(filters) if filters else ""
    with analytics_connection() as connection:
        return fetch_all(
            connection,
            f"""
            SELECT *
            FROM v_bdf_total_deposits_with_insee_macro
            {where}
            ORDER BY bdf_reference_period, departement_code, macro_indicator_code
            LIMIT :limit OFFSET :offset
            """,
            params,
        )


@analytics_api.get("/streamlit")
def streamlit_dataset(
    departement_code: str | None = None,
    macro_indicator_code: str | None = None,
    reference_year: int | None = None,
    limit: int = Query(50000, ge=1, le=250000),
    offset: int = Query(0, ge=0),
) -> list[dict]:
    """Return joined rows using the column names expected by the Streamlit dashboard."""
    filters = []
    params = {"limit": limit, "offset": offset}
    if departement_code:
        filters.append("departement_code = :departement_code")
        params["departement_code"] = _standardize_department_code(departement_code)
    if macro_indicator_code:
        filters.append("macro_indicator_code = :macro_indicator_code")
        params["macro_indicator_code"] = macro_indicator_code
    if reference_year:
        filters.append("reference_year = :reference_year")
        params["reference_year"] = reference_year
    where = "WHERE " + " AND ".join(filters) if filters else ""
    with analytics_connection() as connection:
        return fetch_all(
            connection,
            f"""
            SELECT reference_year,
                   departement_code,
                   departement_name,
                   region_name,
                   macro_reference_year,
                   macro_indicator_code AS indicator_code,
                   macro_indicator_name AS indicator_name,
                   macro_indicator_group AS indicator_group,
                   macro_value,
                   surendettement_value,
                   surendettement_value AS dossiers_deposes
            FROM v_surendettement_with_insee_macro
            {where}
            ORDER BY reference_year, departement_code, indicator_code
            LIMIT :limit OFFSET :offset
            """,
            params,
        )


@analytics_api.post("/macro-overrides", response_model=MacroOverrideRead, status_code=201)
def create_macro_override(payload: MacroOverrideCreate) -> dict:
    now = utc_now()
    indicator_key = f"override:{payload.indicator_code}"
    with analytics_connection() as connection:
        columns = table_columns(connection, "fact_macro_override")
        base_params = {
            **payload.model_dump(),
            "departement_code": _standardize_department_code(
                payload.departement_code
            ),
            "created_at": now,
            "updated_at": now,
        }
        if "period_key" not in columns:
            cursor = execute(
                connection,
                """
                INSERT INTO fact_macro_override (
                    reference_year, departement_code, indicator_code,
                    indicator_name, indicator_group, value, source_note,
                    created_at, updated_at
                ) VALUES (
                    :reference_year, :departement_code, :indicator_code,
                    :indicator_name, :indicator_group, :value, :source_note,
                    :created_at, :updated_at
                )
                """,
                base_params,
            )
            override_id = getattr(cursor, "lastrowid", None)
            return fetch_one(
                connection,
                "SELECT * FROM fact_macro_override WHERE id = :id",
                {"id": override_id},
            )
        execute(
            connection,
            """
            INSERT INTO dim_period(
                period_key, reference_year, reference_month_number, granularity
            ) VALUES (:period_key, :reference_year, NULL, 'year')
            ON CONFLICT(period_key) DO NOTHING
            """,
            {
                "period_key": str(payload.reference_year),
                "reference_year": payload.reference_year,
            },
        )
        execute(
            connection,
            """
            INSERT INTO dim_indicator(
                indicator_key, source_system, indicator_code, indicator_name,
                indicator_group, aggregation_rule
            ) VALUES (
                :indicator_key, 'override', :indicator_code, :indicator_name,
                :indicator_group, 'manual'
            )
            ON CONFLICT(indicator_key) DO NOTHING
            """,
            {
                **base_params,
                "indicator_key": indicator_key,
            },
        )
        cursor = execute(
            connection,
            """
            INSERT INTO fact_macro_override (
                period_key, reference_year, departement_code, indicator_key,
                indicator_code, indicator_name, indicator_group, value,
                source_note, created_at, updated_at
            )
            VALUES (
                :period_key, :reference_year, :departement_code, :indicator_key,
                :indicator_code, :indicator_name, :indicator_group, :value,
                :source_note, :created_at, :updated_at
            )
            """,
            {
                **base_params,
                "period_key": str(payload.reference_year),
                "indicator_key": indicator_key,
            },
        )
        override_id = getattr(cursor, "lastrowid", None)
        if override_id is None:
            override_id = execute(connection, "SELECT MAX(id) FROM fact_macro_override").scalar_one()
        row = fetch_one(
            connection,
            "SELECT * FROM fact_macro_override WHERE id = :id",
            {"id": override_id},
        )
    return row


@analytics_api.get("/macro-overrides", response_model=list[MacroOverrideRead])
def list_macro_overrides(
    departement_code: str | None = None,
    reference_year: int | None = None,
    limit: int = Query(500, ge=1, le=5000),
    offset: int = Query(0, ge=0),
) -> list[dict]:
    filters = []
    params = {"limit": limit, "offset": offset}
    if departement_code:
        filters.append("departement_code = :departement_code")
        params["departement_code"] = _standardize_department_code(departement_code)
    if reference_year:
        filters.append("reference_year = :reference_year")
        params["reference_year"] = reference_year
    where = "WHERE " + " AND ".join(filters) if filters else ""
    with analytics_connection() as connection:
        return fetch_all(
            connection,
            f"""
            SELECT *
            FROM fact_macro_override
            {where}
            ORDER BY reference_year, departement_code, indicator_code, id
            LIMIT :limit OFFSET :offset
            """,
            params,
        )


@analytics_api.patch("/macro-overrides/{override_id}", response_model=MacroOverrideRead)
def update_macro_override(override_id: int, payload: MacroOverrideUpdate) -> dict:
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    updates["updated_at"] = utc_now()
    assignments = ", ".join(f"{column} = :{column}" for column in updates)
    params = {**updates, "id": override_id}
    with analytics_connection() as connection:
        execute(
            connection,
            f"UPDATE fact_macro_override SET {assignments} WHERE id = :id",
            params,
        )
        row = fetch_one(
            connection,
            "SELECT * FROM fact_macro_override WHERE id = :id",
            {"id": override_id},
        )
    if row is None:
        raise HTTPException(status_code=404, detail="Override not found")
    return row


def _standardize_department_code(value: str) -> str:
    text = str(value).strip().upper()
    return text.zfill(2) if text.isdigit() else text
