"""Dedicated Streamlit page for territorial risk-score exploration."""

from __future__ import annotations

import os

import pandas as pd
import plotly.express as px
import streamlit as st
import requests
from config.settings import DEPARTMENTS_GEOJSON_URL, REGIONS_GEOJSON_URL

RISK_SCORES_API_URL = os.getenv(
    "RISK_SCORES_API_URL",
    "http://127.0.0.1:8020/api/risk-scores",
)
API_TIMEOUT_SECONDS = int(os.getenv("SURENDETTEMENT_API_TIMEOUT", "8"))

LEVEL_LABELS = {"region": "Régions", "department": "Départements"}
STATUS_LABELS = {
    "partial": "Score calculé — couverture partielle",
    "valid": "Score complet",
    "insufficient_data": "Données insuffisantes",
    "error": "Erreur",
}
RISK_LABELS = {
    "very_low": "Très faible",
    "low": "Faible",
    "moderate": "Modéré",
    "high": "Élevé",
    "very_high": "Très élevé",
}
RISK_COLORS = {
    "Très faible": "#2E7D32",
    "Faible": "#7CB342",
    "Modéré": "#F9A825",
    "Élevé": "#EF6C00",
    "Très élevé": "#C62828",
    "Non calculé": "#9E9E9E",
}
INDICATOR_LABELS = {
    "dossiers_surendettement_1000_habitants": "Dossiers pour 1 000 habitants",
    "taux_chomage": "Taux de chômage",
    "taux_pauvrete": "Taux de pauvreté",
    "revenu_median": "Niveau de vie médian",
    "endettement_moyen": "Endettement moyen",
    "inflation": "Inflation",
}


@st.cache_data(show_spinner=False, ttl=300)
def load_risk_scores() -> tuple[pd.DataFrame, list[str]]:
    """Load all persisted scores and flatten nested API fields."""
    messages: list[str] = []
    try:
        response = requests.get(
            RISK_SCORES_API_URL,
            params={
                "model_code": "default",
                "active_model_only": True,
                "limit": 5000,
            },
            timeout=API_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError) as exc:
        messages.append(
            f"API des scores indisponible, lecture locale utilisée : {exc}"
        )
        try:
            from app.views.risk_scores_api import list_risk_scores

            payload = list_risk_scores(
                model_code="default",
                active_model_only=True,
                sort="score_desc",
                limit=5000,
                offset=0,
            )
        except Exception as local_exc:
            messages.append(f"Lecture locale impossible : {local_exc}")
            return pd.DataFrame(), messages
    if not isinstance(payload, list):
        return pd.DataFrame(), ["La réponse de l'API des scores n'est pas une liste."]
    data = pd.DataFrame(payload)
    if data.empty:
        return data, ["Aucun score territorial n'est encore enregistré."]
    required = {
        "geographic_level",
        "geographic_code",
        "geographic_name",
        "reference_period",
        "score",
        "coverage_ratio",
        "status",
        "risk_level",
        "details",
    }
    missing = sorted(required.difference(data.columns))
    if missing:
        return pd.DataFrame(), [f"Champs API manquants : {', '.join(missing)}"]
    data["score"] = pd.to_numeric(data["score"], errors="coerce")
    data["coverage_ratio"] = pd.to_numeric(
        data["coverage_ratio"], errors="coerce"
    )
    data["risk_code"] = data["risk_level"].map(
        lambda value: value.get("code") if isinstance(value, dict) else None
    )
    data["risk_label"] = data["risk_code"].map(RISK_LABELS).fillna("Non calculé")
    data["territory_label"] = (
        data["geographic_name"].fillna(data["geographic_code"])
        + " ("
        + data["geographic_code"].astype(str)
        + ")"
    )
    messages.append(f"{len(data)} diagnostics territoriaux chargés.")
    return data.sort_values(
        ["geographic_level", "reference_period", "geographic_code"]
    ), messages


def render_risk_scores_page() -> None:
    st.title("Scores territoriaux de risque de surendettement")
    st.caption(
        "Indice comparatif territorial de 0 à 100. Il ne constitue ni une "
        "probabilité individuelle ni une décision de crédit."
    )
    if st.button("Actualiser les scores", icon="🔄"):
        load_risk_scores.clear()
    data, messages = load_risk_scores()
    for message in messages:
        st.info(message)
    if data.empty:
        st.error(
            "Aucune donnée exploitable. Vérifiez que l'API FastAPI fonctionne "
            "et que les scores ont été calculés."
        )
        return
    versions = sorted(
        {
            item.get("version")
            for item in data["model"]
            if isinstance(item, dict) and item.get("version")
        }
    )
    st.caption("Modèle affiché : " + ", ".join(versions))

    selected_level = st.segmented_control(
        "Niveau territorial",
        options=list(LEVEL_LABELS),
        default="region",
        format_func=LEVEL_LABELS.get,
        selection_mode="single",
    )
    level_data = data[data["geographic_level"] == selected_level].copy()
    periods = sorted(level_data["reference_period"].unique())
    territories = (
        level_data[["territory_label", "geographic_code"]]
        .drop_duplicates()
        .sort_values("territory_label")
    )
    territory_options = territories["territory_label"].tolist()
    default_territories = (
        territory_options
        if selected_level == "region"
        else territory_options[:12]
    )

    filters = st.columns([2, 2, 1])
    selected_territories = filters[0].multiselect(
        "Territoires comparés",
        territory_options,
        default=default_territories,
    )
    selected_risks = filters[1].multiselect(
        "Niveaux de risque",
        list(RISK_COLORS),
        default=list(RISK_COLORS),
    )
    only_calculated = filters[2].toggle(
        "Scores calculés",
        value=selected_level == "region",
        help="Masque les diagnostics dont la couverture est insuffisante.",
    )
    period_start, period_end = st.select_slider(
        "Période analysée",
        periods,
        value=(periods[0], periods[-1]),
    )

    filtered = level_data[
        level_data["territory_label"].isin(selected_territories)
        & level_data["risk_label"].isin(selected_risks)
        & level_data["reference_period"].between(period_start, period_end)
    ].copy()
    if only_calculated:
        filtered = filtered[filtered["score"].notna()]
    if filtered.empty:
        st.warning("Aucun diagnostic ne correspond à cette sélection.")
        return

    _render_kpis(filtered)
    _render_period_comparison(filtered, periods)
    latest_period = filtered["reference_period"].max()
    latest = filtered[filtered["reference_period"] == latest_period].copy()

    st.subheader("Évolution des scores")
    evolution = px.line(
        filtered.dropna(subset=["score"]),
        x="reference_period",
        y="score",
        color="territory_label",
        markers=True,
        labels={
            "reference_period": "Mois",
            "score": "Score sur 100",
            "territory_label": "Territoire",
        },
    )
    evolution.update_yaxes(range=[0, 100])
    evolution.update_layout(legend_title_text="")
    st.plotly_chart(evolution, use_container_width=True)

    left, right = st.columns([3, 2])
    with left:
        st.subheader(f"Classement — {latest_period}")
        ranking = latest.dropna(subset=["score"]).sort_values("score")
        chart = px.bar(
            ranking,
            x="score",
            y="territory_label",
            color="risk_label",
            orientation="h",
            text_auto=".1f",
            color_discrete_map=RISK_COLORS,
            labels={
                "score": "Score sur 100",
                "territory_label": "Territoire",
                "risk_label": "Risque",
            },
        )
        chart.update_xaxes(range=[0, 100])
        chart.update_layout(
            height=max(430, 32 * len(ranking)),
            legend_title_text="Niveau",
        )
        st.plotly_chart(chart, use_container_width=True)
    with right:
        st.subheader("Qualité des données")
        coverage = latest.sort_values("coverage_ratio")
        coverage_chart = px.bar(
            coverage,
            x="coverage_ratio",
            y="territory_label",
            orientation="h",
            color="status",
            labels={
                "coverage_ratio": "Couverture",
                "territory_label": "Territoire",
                "status": "Statut",
            },
        )
        coverage_chart.update_xaxes(range=[0, 1], tickformat=".0%")
        coverage_chart.update_layout(
            height=max(430, 32 * len(coverage)),
            legend_title_text="Statut",
        )
        st.plotly_chart(coverage_chart, use_container_width=True)

    territory_label = "régionale" if selected_level == "region" else "départementale"
    st.subheader(f"Carte {territory_label} — {latest_period}")
    mapped = latest.dropna(subset=["score"])
    map_chart = px.choropleth_mapbox(
        mapped,
        geojson=(
            REGIONS_GEOJSON_URL
            if selected_level == "region"
            else DEPARTMENTS_GEOJSON_URL
        ),
        locations="geographic_code",
        featureidkey="properties.code",
        color="score",
        hover_name="geographic_name",
        hover_data={"coverage_ratio": ":.0%", "geographic_code": True},
        color_continuous_scale="RdYlGn_r",
        range_color=(0, 100),
        mapbox_style="carto-positron",
        center={"lat": 46.6, "lon": 2.4},
        zoom=4.6,
        opacity=0.75,
    )
    map_chart.update_layout(height=540, margin={"r": 0, "t": 0, "l": 0, "b": 0})
    st.plotly_chart(map_chart, use_container_width=True)

    _render_score_detail(filtered)
    _render_business_validation(selected_level)
    _render_data_table(filtered)


def _render_kpis(data: pd.DataFrame) -> None:
    calculated = data["score"].notna()
    kpis = st.columns(5)
    kpis[0].metric("Diagnostics", len(data))
    kpis[1].metric("Scores calculés", int(calculated.sum()))
    kpis[2].metric(
        "Score moyen",
        f"{data.loc[calculated, 'score'].mean():.1f}"
        if calculated.any()
        else "—",
    )
    kpis[3].metric(
        "Couverture moyenne",
        f"{data['coverage_ratio'].mean():.0%}",
    )
    kpis[4].metric(
        "Territoires",
        int(data["geographic_code"].nunique()),
    )


def _render_period_comparison(data: pd.DataFrame, periods: list[str]) -> None:
    st.subheader("Comparer deux périodes")
    columns = st.columns(2)
    period_a = columns[0].selectbox(
        "Période de départ", periods, index=max(0, len(periods) - 2)
    )
    period_b = columns[1].selectbox(
        "Période d’arrivée", periods, index=len(periods) - 1
    )
    comparison = (
        data[data["reference_period"].isin((period_a, period_b))]
        .pivot_table(
            index=["geographic_code", "geographic_name", "territory_label"],
            columns="reference_period",
            values="score",
            aggfunc="first",
        )
        .reset_index()
    )
    if period_a not in comparison or period_b not in comparison:
        st.info("Les deux périodes ne disposent pas de scores comparables.")
        return
    comparison["variation"] = comparison[period_b] - comparison[period_a]
    chart = px.bar(
        comparison.dropna(subset=["variation"]).sort_values("variation"),
        x="variation",
        y="territory_label",
        orientation="h",
        color="variation",
        color_continuous_scale="RdYlGn_r",
        color_continuous_midpoint=0,
        labels={"variation": "Variation du score", "territory_label": "Territoire"},
    )
    chart.update_layout(height=max(380, len(comparison) * 28))
    st.plotly_chart(chart, use_container_width=True)


def _render_score_detail(data: pd.DataFrame) -> None:
    st.subheader("Comprendre un score")
    calculated = data[data["score"].notna()].copy()
    if calculated.empty:
        st.info(
            "La couverture de la sélection est insuffisante pour détailler un score."
        )
        return
    selectors = st.columns(2)
    territory = selectors[0].selectbox(
        "Territoire détaillé",
        sorted(calculated["territory_label"].unique()),
    )
    available_periods = sorted(
        calculated.loc[
            calculated["territory_label"] == territory,
            "reference_period",
        ].unique(),
        reverse=True,
    )
    period = selectors[1].selectbox("Période détaillée", available_periods)
    selected = calculated[
        (calculated["territory_label"] == territory)
        & (calculated["reference_period"] == period)
    ].iloc[0]
    details = pd.DataFrame(selected["details"])
    if details.empty:
        st.info("Aucune contribution détaillée n'est enregistrée.")
        return
    details["indicator_label"] = details["indicator_code"].map(
        INDICATOR_LABELS
    ).fillna(details["indicator_code"])
    details["effective_weight_pct"] = details["effective_weight"] * 100
    detail_columns = st.columns([3, 2])
    with detail_columns[0]:
        contribution_chart = px.bar(
            details.sort_values("contribution"),
            x="contribution",
            y="indicator_label",
            orientation="h",
            text_auto=".1f",
            color="contribution",
            color_continuous_scale="OrRd",
            labels={
                "contribution": "Contribution au score",
                "indicator_label": "Indicateur",
            },
        )
        contribution_chart.update_coloraxes(showscale=False)
        st.plotly_chart(contribution_chart, use_container_width=True)
    with detail_columns[1]:
        st.metric("Score", f"{selected['score']:.1f} / 100")
        st.metric("Niveau", selected["risk_label"])
        st.metric("Couverture", f"{selected['coverage_ratio']:.0%}")
        missing = selected.get("missing_indicators") or []
        if missing:
            st.caption(
                "Indicateurs absents : "
                + ", ".join(INDICATOR_LABELS.get(item, item) for item in missing)
            )
    st.dataframe(
        details[
            [
                "indicator_label",
                "raw_value",
                "unit",
                "normalized_value",
                "effective_weight_pct",
                "contribution",
            ]
        ].rename(
            columns={
                "indicator_label": "Indicateur",
                "raw_value": "Valeur brute",
                "unit": "Unité",
                "normalized_value": "Valeur normalisée",
                "effective_weight_pct": "Poids effectif (%)",
                "contribution": "Contribution",
            }
        ),
        use_container_width=True,
        hide_index=True,
    )
    source_links = sorted(
        {
            item
            for item in details.get("source_url", pd.Series(dtype=str)).dropna()
            if str(item).startswith(("http://", "https://"))
        }
    )
    if source_links:
        st.caption("Sources : " + " · ".join(source_links))


def _render_data_table(data: pd.DataFrame) -> None:
    with st.expander("Données et export"):
        export = data[
            [
                "reference_period",
                "geographic_code",
                "geographic_name",
                "score",
                "risk_label",
                "coverage_ratio",
                "status",
            ]
        ].rename(
            columns={
                "reference_period": "Période",
                "geographic_code": "Code",
                "geographic_name": "Territoire",
                "score": "Score",
                "risk_label": "Niveau",
                "coverage_ratio": "Couverture",
                "status": "Statut",
            }
        )
        st.dataframe(export, use_container_width=True, hide_index=True)
        st.download_button(
            "Télécharger la sélection en CSV",
            export.to_csv(index=False).encode("utf-8"),
            file_name="scores_territoriaux.csv",
            mime="text/csv",
        )


def _render_business_validation(level: str) -> None:
    with st.expander("Validation métier et limites du modèle"):
        from src.risk_score.validation import build_score_validation_report

        report = build_score_validation_report(level)
        if report["status"] != "ok":
            st.info("Données insuffisantes pour valider ce niveau territorial.")
            return
        metrics = st.columns(3)
        correlation = report["dossier_rate_spearman"]
        sensitivity = report["equal_weight_rank_spearman"]
        metrics[0].metric(
            "Corrélation score–dossiers",
            f"{correlation:.2f}" if correlation is not None else "—",
            help="Corrélation de rang de Spearman.",
        )
        metrics[1].metric(
            "Variation mensuelle moyenne",
            f"{report['mean_absolute_monthly_change']:.1f} points",
        )
        metrics[2].metric(
            "Stabilité avec poids égaux",
            f"{sensitivity:.2f}" if sensitivity is not None else "—",
            help="Corrélation de rang entre le modèle et une pondération égale.",
        )
        volatile = pd.DataFrame(report["most_volatile"])
        if not volatile.empty:
            st.caption("Territoires dont le score varie le plus d’un mois à l’autre")
            st.dataframe(volatile, use_container_width=True, hide_index=True)
        for limitation in report["limitations"]:
            st.markdown(f"- {limitation}")
