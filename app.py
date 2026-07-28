from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from src.charts.dashboard_charts import (
    make_choropleth,
    make_correlation_heatmap,
    make_department_bar,
    make_scatter,
    make_time_series,
)
from src.data.dashboard_data import (
    MEASURE_OPTIONS,
    load_dashboard_data,
    load_inclusion_financiere_data,
    load_regional_macro_data,
)

st.set_page_config(
    page_title="Surendettement et indicateurs macro-économiques",
    page_icon="📊",
    layout="wide",
)


def main() -> None:
    st.title("Dashboard surendettement et inclusion financière")
    st.caption(
        "Exploration des données départementales annuelles et des baromètres mensuels régionaux."
    )

    departmental_tab, inclusion_tab, macro_tab = st.tabs(
        [
            "Analyse départementale",
            "Inclusion financière régionale",
            "Indicateurs macro régionaux",
        ]
    )
    with departmental_tab:
        render_departmental_dashboard()
    with inclusion_tab:
        render_inclusion_financiere_dashboard()
    with macro_tab:
        render_macro_regional_dashboard()


def render_departmental_dashboard() -> None:
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


def render_inclusion_financiere_dashboard() -> None:
    data, messages = load_inclusion_financiere_data()
    macro_data, macro_messages = load_regional_macro_data()
    for message in [*messages, *macro_messages]:
        st.info(message)
    if data.empty:
        st.error("Aucune observation mensuelle régionale n'est disponible.")
        return

    regions = sorted(data["region_name"].dropna().unique().tolist())
    indicators = (
        data[["indicator_code", "indicator_label"]]
        .drop_duplicates()
        .sort_values("indicator_label")
    )
    indicator_choices = list(indicators.itertuples(index=False, name=None))
    macro_indicators = (
        macro_data[["indicator_code", "indicator_name"]]
        .drop_duplicates()
        .sort_values("indicator_name")
        if not macro_data.empty
        else pd.DataFrame([{"indicator_code": "", "indicator_name": "Indisponible"}])
    )
    macro_choices = list(macro_indicators.itertuples(index=False, name=None))
    periods = sorted(data["reference_period"].unique().tolist())

    default_regions = regions[:4]
    default_macro = [
        choice
        for choice in macro_choices
        if choice[0] in {
            "taux_chomage_1564",
            "part_residences_principales",
            "part_familles_monoparentales",
        }
    ]
    filter_columns = st.columns(3)
    selected_regions = filter_columns[0].multiselect(
        "Régions",
        regions,
        default=default_regions,
    )
    selected_indicators = filter_columns[1].multiselect(
        "Indicateurs d'inclusion",
        indicator_choices,
        default=indicator_choices,
        format_func=lambda choice: choice[1],
    )
    selected_macro = filter_columns[2].multiselect(
        "Indicateurs macro régionaux",
        macro_choices,
        default=default_macro or macro_choices[:3],
        format_func=lambda choice: choice[1],
    )
    period_start, period_end = st.select_slider(
        "Période",
        options=periods,
        value=(periods[0], periods[-1]),
    )

    if not selected_regions or not selected_indicators:
        st.warning("Sélectionnez au moins une région et un indicateur d'inclusion.")
        return

    selected_indicator_codes = [choice[0] for choice in selected_indicators]
    comparison_source = data[
        data["indicator_code"].isin(selected_indicator_codes)
        & (data["reference_period"] >= period_start)
        & (data["reference_period"] <= period_end)
    ].copy()
    filtered = comparison_source[
        comparison_source["region_name"].isin(selected_regions)
    ].copy()
    if filtered.empty:
        st.warning("Aucune observation ne correspond aux filtres sélectionnés.")
        return

    latest_period = filtered["reference_period"].max()
    latest = filtered[filtered["reference_period"] == latest_period].copy()
    kpis = st.columns(4)
    kpis[0].metric("Dernière période", latest_period)
    kpis[1].metric("Observations", len(filtered))
    kpis[2].metric("Régions", int(filtered["region_code"].nunique()))
    kpis[3].metric("Indicateurs", int(filtered["indicator_code"].nunique()))

    line = px.line(
        filtered,
        x="reference_period",
        y="value",
        color="region_name",
        facet_row="indicator_label",
        markers=True,
        labels={
            "reference_period": "Mois",
            "value": "Valeur",
            "region_name": "Région",
            "indicator_label": "Indicateur",
        },
        title="Évolution mensuelle par indicateur",
    )
    line.for_each_annotation(lambda annotation: annotation.update(text=annotation.text.split("=")[-1]))
    line.update_yaxes(matches=None)
    line.update_layout(height=min(900, max(500, 280 * len(selected_indicators))))
    st.plotly_chart(line, use_container_width=True)

    ranking = latest.sort_values(["indicator_label", "value"], ascending=[True, False])
    bar = px.bar(
        ranking,
        x="region_name",
        y="value",
        color="region_name",
        facet_col="indicator_label",
        labels={"region_name": "Région", "value": "Valeur", "indicator_label": "Indicateur"},
        title=f"Comparaison régionale — {latest_period}",
    )
    bar.for_each_annotation(lambda annotation: annotation.update(text=annotation.text.split("=")[-1]))
    bar.update_yaxes(matches=None)
    bar.update_layout(height=470, xaxis_tickangle=-35, showlegend=False)
    st.plotly_chart(bar, use_container_width=True)

    if not macro_data.empty and selected_macro:
        inclusion_by_region = (
            filtered.groupby(["region_name", "indicator_label"], as_index=False)["value"]
            .mean()
            .pivot(index="region_name", columns="indicator_label", values="value")
            .add_prefix("Inclusion — ")
            .reset_index()
        )
        selected_macro_codes = [choice[0] for choice in selected_macro]
        selected_macro_data = (
            macro_data[
                macro_data["indicator_code"].isin(selected_macro_codes)
                & macro_data["region_name"].isin(selected_regions)
            ]
            .pivot(index="region_name", columns="indicator_name", values="value")
            .add_prefix("Macro — ")
            .reset_index()
        )
        comparison = inclusion_by_region.merge(
            selected_macro_data,
            on="region_name",
            how="inner",
        )
        inclusion_columns = [column for column in comparison if column.startswith("Inclusion — ")]
        macro_columns = [column for column in comparison if column.startswith("Macro — ")]
        if len(comparison) >= 3 and inclusion_columns and macro_columns:
            correlations = comparison[inclusion_columns + macro_columns].corr().loc[
                inclusion_columns,
                macro_columns,
            ]
            heatmap = px.imshow(
                correlations,
                text_auto=".2f",
                color_continuous_scale="RdBu_r",
                zmin=-1,
                zmax=1,
                aspect="auto",
                title="Corrélations régionales entre inclusion financière et contexte macro",
            )
            heatmap.update_layout(height=max(420, 100 * len(inclusion_columns)))
            st.plotly_chart(heatmap, use_container_width=True)
            st.caption(
                "Corrélations descriptives calculées sur les régions sélectionnées ; "
                "elles ne démontrent pas de relation causale."
            )
        else:
            st.warning("Sélectionnez au moins trois régions pour calculer les corrélations.")

    with st.expander("Voir et exporter les données filtrées"):
        display_columns = [
            "reference_period",
            "region_name",
            "indicator_label",
            "value",
            "unit",
        ]
        st.dataframe(filtered[display_columns], use_container_width=True, hide_index=True)
        st.download_button(
            "Télécharger en CSV",
            filtered[display_columns].to_csv(index=False).encode("utf-8"),
            file_name="inclusion_financiere_filtree.csv",
            mime="text/csv",
        )


def render_macro_regional_dashboard() -> None:
    data, messages = load_regional_macro_data()
    for message in messages:
        st.info(message)
    if data.empty:
        st.error("Aucune donnée macro régionale n'est disponible.")
        return

    groups = sorted(data["indicator_group"].dropna().unique().tolist())
    regions = sorted(data["region_name"].dropna().unique().tolist())
    filter_columns = st.columns(2)
    selected_groups = filter_columns[0].multiselect(
        "Thèmes macro",
        groups,
        default=groups,
        key="macro_groups",
    )
    selected_regions = filter_columns[1].multiselect(
        "Régions comparées",
        regions,
        default=regions[:6],
        key="macro_regions",
    )
    available_indicators = (
        data[data["indicator_group"].isin(selected_groups)][
            ["indicator_code", "indicator_name", "aggregation_rule"]
        ]
        .drop_duplicates()
        .sort_values(["aggregation_rule", "indicator_name"])
    )
    indicator_choices = list(available_indicators.itertuples(index=False, name=None))
    default_indicators = [
        choice
        for choice in indicator_choices
        if choice[0]
        in {
            "P22_POP",
            "taux_chomage_1564",
            "part_logements_vacants",
            "part_familles_monoparentales",
            "part_sans_diplome",
        }
    ]
    selected_indicators = st.multiselect(
        "Indicateurs macro",
        indicator_choices,
        default=default_indicators or indicator_choices[:5],
        format_func=lambda choice: choice[1],
        key="macro_indicators",
    )
    if not selected_groups or not selected_regions or not selected_indicators:
        st.warning("Sélectionnez au moins un thème, une région et un indicateur.")
        return

    selected_codes = [choice[0] for choice in selected_indicators]
    filtered = data[
        data["region_name"].isin(selected_regions)
        & data["indicator_code"].isin(selected_codes)
    ].copy()
    if filtered.empty:
        st.warning("Aucune donnée ne correspond à cette sélection.")
        return

    kpis = st.columns(4)
    kpis[0].metric("Millésime INSEE", int(filtered["reference_year"].max()))
    kpis[1].metric("Régions", filtered["region_name"].nunique())
    kpis[2].metric("Indicateurs", filtered["indicator_code"].nunique())
    kpis[3].metric("Thèmes", filtered["indicator_group"].nunique())

    bars = px.bar(
        filtered,
        x="region_name",
        y="value",
        color="region_name",
        facet_col="indicator_name",
        facet_col_wrap=2,
        labels={"region_name": "Région", "value": "Valeur", "indicator_name": "Indicateur"},
        title="Comparaison des régions par indicateur",
    )
    bars.for_each_annotation(lambda annotation: annotation.update(text=annotation.text.split("=")[-1]))
    bars.update_yaxes(matches=None)
    bars.update_layout(
        height=max(500, 330 * ((len(selected_indicators) + 1) // 2)),
        showlegend=False,
        xaxis_tickangle=-35,
    )
    st.plotly_chart(bars, use_container_width=True)

    profile = filtered.pivot(
        index="region_name",
        columns="indicator_name",
        values="value",
    )
    standard_deviation = profile.std(axis=0).replace(0, pd.NA)
    standardized = (profile - profile.mean(axis=0)) / standard_deviation
    heatmap = px.imshow(
        standardized,
        text_auto=".1f",
        color_continuous_scale="RdBu_r",
        color_continuous_midpoint=0,
        aspect="auto",
        labels={"x": "Indicateur", "y": "Région", "color": "Écart-type"},
        title="Profil macro comparé des régions (valeurs standardisées)",
    )
    heatmap.update_layout(height=max(480, 55 * len(selected_regions)))
    st.plotly_chart(heatmap, use_container_width=True)
    st.caption(
        "La standardisation exprime chaque valeur en nombre d’écarts-types par rapport "
        "à la moyenne des régions sélectionnées, ce qui rend comparables des unités différentes."
    )

    ranking_indicator = st.selectbox(
        "Indicateur à classer",
        selected_indicators,
        format_func=lambda choice: choice[1],
        key="macro_ranking_indicator",
    )
    ranking = filtered[
        filtered["indicator_code"] == ranking_indicator[0]
    ].sort_values("value", ascending=True)
    ranking_chart = px.bar(
        ranking,
        x="value",
        y="region_name",
        orientation="h",
        color="value",
        color_continuous_scale="Viridis",
        labels={"value": ranking_indicator[1], "region_name": "Région"},
        title=f"Classement régional — {ranking_indicator[1]}",
    )
    ranking_chart.update_layout(height=max(420, 42 * len(selected_regions)))
    st.plotly_chart(ranking_chart, use_container_width=True)

    with st.expander("Voir et exporter les données macro filtrées"):
        display_columns = [
            "reference_year",
            "region_name",
            "indicator_group",
            "indicator_name",
            "aggregation_rule",
            "value",
        ]
        st.dataframe(filtered[display_columns], use_container_width=True, hide_index=True)
        st.download_button(
            "Télécharger les données macro en CSV",
            filtered[display_columns].to_csv(index=False).encode("utf-8"),
            file_name="indicateurs_macro_regionaux.csv",
            mime="text/csv",
        )


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
