"""API routes to consume and curate analytical macro/surendettement data."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.core.analytics import analytics_connection, fetch_all, fetch_one, utc_now
from app.schemas.analytics import MacroOverrideCreate, MacroOverrideRead, MacroOverrideUpdate

analytics_api = APIRouter(prefix="/api/data", tags=["Analytical data"])


@analytics_api.get("/health")
def health() -> dict:
    with analytics_connection() as connection:
        tables = fetch_all(
            connection,
            "SELECT name FROM sqlite_master WHERE type IN ('table', 'view') ORDER BY name",
        )
    return {"status": "ok", "objects": [row["name"] for row in tables]}


@analytics_api.get("/departments")
def list_departments(limit: int = Query(200, ge=1, le=500), offset: int = Query(0, ge=0)) -> list[dict]:
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


@analytics_api.get("/indicators")
def list_indicators(
    source_system: str | None = Query(None),
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
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


@analytics_api.get("/surendettement")
def list_surendettement_data(
    departement_code: str | None = None,
    indicator_code: str | None = None,
    reference_year: int | None = None,
    limit: int = Query(5000, ge=1, le=100000),
    offset: int = Query(0, ge=0),
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
    with analytics_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO fact_macro_override (
                reference_year, departement_code, indicator_code, indicator_name,
                indicator_group, value, source_note, created_at, updated_at
            )
            VALUES (
                :reference_year, :departement_code, :indicator_code, :indicator_name,
                :indicator_group, :value, :source_note, :created_at, :updated_at
            )
            """,
            {
                **payload.model_dump(),
                "departement_code": _standardize_department_code(payload.departement_code),
                "created_at": now,
                "updated_at": now,
            },
        )
        row = fetch_one(
            connection,
            "SELECT * FROM fact_macro_override WHERE id = :id",
            {"id": cursor.lastrowid},
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
        connection.execute(
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
