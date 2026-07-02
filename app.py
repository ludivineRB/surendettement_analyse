from __future__ import annotations

import pandas as pd
import streamlit as st

from src.charts.dashboard_charts import (
    make_choropleth,
    make_correlation_heatmap,
    make_department_bar,
    make_scatter,
    make_time_series,
)
from src.data.dashboard_data import MEASURE_OPTIONS, load_dashboard_data

st.set_page_config(
    page_title="Surendettement et indicateurs macro-économiques",
    page_icon="📊",
    layout="wide",
)


def main() -> None:
    st.title("Dashboard surendettement et indicateurs macro-économiques")
    st.caption(
        "Exploration par département et par année des données de surendettement "
        "et des indicateurs macro-économiques disponibles."
    )

    data, messages = load_dashboard_data(use_api=True)
    for message in messages:
        st.info(message)

    if data.empty:
        st.error("Aucune donnée exploitable n'est disponible pour construire le dashboard.")
        return

    filtered, selected_measure_label, selected_indicator_label = render_filters(data)
    measure_column = MEASURE_OPTIONS[selected_measure_label]

    if filtered.empty:
        st.warning("Aucune donnée ne correspond aux filtres sélectionnés.")
        return

    render_kpis(filtered, measure_column, selected_measure_label)
    render_charts(filtered, measure_column, selected_measure_label, selected_indicator_label)


def render_filters(data: pd.DataFrame) -> tuple[pd.DataFrame, str, str]:
    st.sidebar.header("Filtres")

    years = sorted(data["reference_year"].dropna().unique().tolist())
    selected_year = st.sidebar.selectbox("Année", years, index=len(years) - 1)

    departments = (
        data[["departement_code", "departement_name"]]
        .drop_duplicates()
        .sort_values(["departement_code", "departement_name"])
    )
    department_labels = ["Tous les départements"] + [
        f"{row.departement_code} - {row.departement_name}" for row in departments.itertuples()
    ]
    selected_department = st.sidebar.selectbox("Département", department_labels)

    indicators = (
        data[["indicator_code", "macro_indicator_label"]]
        .drop_duplicates()
        .sort_values("macro_indicator_label")
    )
    indicator_choices = [
        (row.indicator_code, row.macro_indicator_label) for row in indicators.itertuples()
    ]
    selected_indicator_label = st.sidebar.selectbox(
        "Indicateur macro-économique",
        indicator_choices,
        format_func=lambda choice: choice[1],
    )
    selected_indicator_code = selected_indicator_label[0]
    selected_indicator_display = selected_indicator_label[1]

    selected_measure_label = st.sidebar.selectbox(
        "Mesure de surendettement",
        list(MEASURE_OPTIONS.keys()),
    )

    filtered = data[
        (data["reference_year"] == selected_year)
        & (data["indicator_code"] == selected_indicator_code)
    ].copy()

    if selected_department != "Tous les départements":
        selected_department_code = selected_department.split(" - ", 1)[0]
        filtered = filtered[filtered["departement_code"] == selected_department_code]

    return filtered, selected_measure_label, selected_indicator_display


def render_kpis(df: pd.DataFrame, measure_column: str, measure_label: str) -> None:
    total_surendettement = float(df["surendettement_value"].sum())
    annual_change = float(df["annual_change_pct"].mean())
    macro_value = float(df["macro_value"].mean())
    national_gap = float(df[measure_column].mean() - df["national_surendettement_mean"].mean())

    cols = st.columns(4)
    cols[0].metric("Nombre de dossiers déposés", f"{total_surendettement:,.0f}".replace(",", " "))
    cols[1].metric("Évolution annuelle", f"{annual_change:+.1f} %")
    cols[2].metric("Indicateur macro sélectionné", f"{macro_value:,.1f}".replace(",", " "))
    cols[3].metric("Écart à la moyenne nationale", f"{national_gap:+,.1f}".replace(",", " "))

    st.caption(f"Les indicateurs ci-dessus synthétisent la sélection courante : {measure_label}.")


def render_charts(
    df: pd.DataFrame,
    measure_column: str,
    measure_label: str,
    selected_indicator_label: str,
) -> None:
    st.subheader("Évolution temporelle")
    st.plotly_chart(make_time_series(df, measure_column, measure_label), use_container_width=True)
    st.caption("Cette courbe montre l'évolution annuelle de la mesure sélectionnée.")

    left, right = st.columns(2)
    with left:
        st.subheader("Comparaison entre départements")
        st.plotly_chart(make_department_bar(df, measure_column, measure_label), use_container_width=True)
        st.caption("Le graphique compare les départements selon la mesure choisie.")

    with right:
        st.subheader("Lien avec l'indicateur macro-économique")
        st.plotly_chart(make_scatter(df, measure_column, measure_label), use_container_width=True)
        st.caption(f"Chaque point rapproche {selected_indicator_label} et le nombre de dossiers déposés.")

    st.subheader("Carte des départements")
    st.plotly_chart(make_choropleth(df, measure_column, measure_label), use_container_width=True)
    st.caption("La carte met en évidence les écarts territoriaux de la sélection.")

    st.subheader("Corrélations")
    st.plotly_chart(make_correlation_heatmap(df), use_container_width=True)
    st.caption("La heatmap aide à repérer les relations entre les mesures disponibles.")


if __name__ == "__main__":
    main()
