"""Plotly charts for the Streamlit dashboard."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from config.settings import DEPARTMENTS_GEOJSON_URL


def make_time_series(df: pd.DataFrame, measure_column: str, measure_label: str) -> go.Figure:
    trend = df.groupby("reference_year", as_index=False)[measure_column].sum()
    fig = px.line(trend, x="reference_year", y=measure_column, markers=True)
    fig.update_layout(xaxis_title="Année", yaxis_title=measure_label, height=360)
    return fig


def make_department_bar(df: pd.DataFrame, measure_column: str, measure_label: str) -> go.Figure:
    ranking = (
        df.groupby(["departement_code", "departement_name"], as_index=False)[measure_column]
        .mean()
        .sort_values(measure_column, ascending=False)
        .head(20)
    )
    fig = px.bar(
        ranking,
        x="departement_name",
        y=measure_column,
        color=measure_column,
        color_continuous_scale="Teal",
    )
    fig.update_layout(xaxis_title="Département", yaxis_title=measure_label, height=420)
    return fig


def make_choropleth(df: pd.DataFrame, measure_column: str, measure_label: str) -> go.Figure:
    map_df = df.groupby(["departement_code", "departement_name"], as_index=False)[measure_column].mean()
    fig = px.choropleth_mapbox(
        map_df,
        geojson=DEPARTMENTS_GEOJSON_URL,
        locations="departement_code",
        featureidkey="properties.code",
        color=measure_column,
        hover_name="departement_name",
        color_continuous_scale="Viridis",
        mapbox_style="carto-positron",
        center={"lat": 46.6, "lon": 2.4},
        zoom=4.6,
        opacity=0.72,
    )
    fig.update_layout(height=520, margin={"r": 0, "t": 0, "l": 0, "b": 0})
    fig.update_coloraxes(colorbar_title=measure_label)
    return fig


def make_scatter(df: pd.DataFrame, measure_column: str, measure_label: str) -> go.Figure:
    scatter_df = df.dropna(subset=["macro_value", measure_column])
    fig = px.scatter(
        scatter_df,
        x="macro_value",
        y=measure_column,
        color="departement_name",
        hover_name="departement_name",
    )
    fig.update_layout(
        xaxis_title="Indicateur macro-économique sélectionné",
        yaxis_title=measure_label,
        height=420,
        showlegend=False,
    )
    return fig


def make_correlation_heatmap(df: pd.DataFrame) -> go.Figure:
    corr = df[["surendettement_value", "macro_value"]].corr(numeric_only=True)
    fig = px.imshow(
        corr,
        text_auto=".2f",
        color_continuous_scale="RdBu_r",
        zmin=-1,
        zmax=1,
        aspect="auto",
    )
    fig.update_layout(height=380, coloraxis_colorbar_title="Corrélation")
    return fig
