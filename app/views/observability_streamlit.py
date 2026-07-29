"""Streamlit supervision page for pipeline freshness and data quality."""

from __future__ import annotations

import os

import pandas as pd
import plotly.express as px
import requests
import streamlit as st

OBSERVABILITY_API_URL = os.getenv(
    "OBSERVABILITY_API_URL",
    "http://127.0.0.1:8020/api/data/observability",
)
API_TIMEOUT_SECONDS = int(os.getenv("SURENDETTEMENT_API_TIMEOUT", "8"))


@st.cache_data(show_spinner=False, ttl=120)
def load_observability() -> tuple[dict | None, list[str]]:
    messages = []
    try:
        response = requests.get(
            OBSERVABILITY_API_URL,
            timeout=API_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        return response.json(), messages
    except (requests.RequestException, ValueError) as exc:
        messages.append(
            f"API de supervision indisponible, lecture locale utilisée : {exc}"
        )
        try:
            from src.observability import build_observability_report

            return build_observability_report(), messages
        except Exception as local_exc:
            messages.append(f"Lecture locale impossible : {local_exc}")
            return None, messages


def render_observability_page() -> None:
    st.title("Supervision des données et des scores")
    st.caption(
        "Fraîcheur des sources, complétude territoriale, intégrité des bases "
        "et version active du modèle."
    )
    if st.button("Actualiser les contrôles"):
        load_observability.clear()
    report, messages = load_observability()
    for message in messages:
        st.info(message)
    if not report:
        st.error("Le rapport de supervision ne peut pas être produit.")
        return

    if report["status"] == "ok":
        st.success("Tous les contrôles sont au vert.")
    else:
        for alert in report["alerts"]:
            renderer = (
                st.error if alert["severity"] == "error" else st.warning
            )
            renderer(alert["message"])

    operational = report["operational"]
    analytics = report["analytics"]
    model = operational.get("active_model") or {}
    counts = operational["counts"]
    kpis = st.columns(6)
    kpis[0].metric("Documents", counts["source_documents"])
    kpis[1].metric("Observations", counts["observations"])
    kpis[2].metric("Scores", counts["risk_scores"])
    kpis[3].metric(
        "Mois-régions manquants",
        len(operational["missing_regional_dossiers"]),
    )
    kpis[4].metric(
        "Documents à vérifier",
        len(operational["needs_review"]),
    )
    kpis[5].metric(
        "Modèle actif",
        f"{model.get('code', '—')} {model.get('version', '')}".strip(),
    )

    left, right = st.columns(2)
    with left:
        st.subheader("Couverture des scores")
        statuses = pd.DataFrame(operational["score_statuses"])
        if not statuses.empty:
            statuses["coverage_pct"] = statuses["average_coverage"] * 100
            chart = px.bar(
                statuses,
                x="geographic_level",
                y="count",
                color="status",
                text="coverage_pct",
                labels={
                    "geographic_level": "Niveau",
                    "count": "Diagnostics",
                    "status": "Statut",
                    "coverage_pct": "Couverture moyenne (%)",
                },
            )
            chart.update_traces(
                texttemplate="%{text:.0f} %",
                textposition="inside",
            )
            st.plotly_chart(chart, use_container_width=True)
    with right:
        st.subheader("État des documents")
        documents = pd.DataFrame(operational["document_statuses"])
        if not documents.empty:
            chart = px.bar(
                documents,
                x="status",
                y="count",
                color="status",
                text_auto=True,
                labels={"status": "Statut", "count": "Documents"},
            )
            chart.update_layout(showlegend=False)
            st.plotly_chart(chart, use_container_width=True)

    st.subheader("Fraîcheur par indicateur")
    freshness = pd.DataFrame(operational["indicator_freshness"])
    if not freshness.empty:
        st.dataframe(
            freshness.rename(
                columns={
                    "indicator_code": "Code",
                    "indicator_label": "Indicateur",
                    "observations": "Observations",
                    "first_period": "Première période",
                    "latest_period": "Dernière période",
                    "territories": "Territoires",
                    "last_updated_at": "Dernière mise à jour",
                }
            ),
            use_container_width=True,
            hide_index=True,
        )

    st.subheader("Dernières exécutions automatisées")
    pipeline_runs = pd.DataFrame(operational.get("pipeline_runs", []))
    if pipeline_runs.empty:
        st.info(
            "Aucune exécution complète n’est encore journalisée. "
            "Le prochain rafraîchissement apparaîtra ici."
        )
    else:
        st.dataframe(
            pipeline_runs.rename(
                columns={
                    "pipeline_name": "Pipeline",
                    "status": "Statut",
                    "started_at": "Début",
                    "finished_at": "Fin",
                    "error_message": "Erreur",
                }
            ),
            use_container_width=True,
            hide_index=True,
        )

    missing = pd.DataFrame(operational["missing_regional_dossiers"])
    review = pd.DataFrame(operational["needs_review"])
    detail_left, detail_right = st.columns(2)
    with detail_left:
        st.subheader("Couples région-mois manquants")
        if missing.empty:
            st.success("Aucun mois régional manquant.")
        else:
            st.dataframe(missing, use_container_width=True, hide_index=True)
    with detail_right:
        st.subheader("Documents à vérifier")
        if review.empty:
            st.success("Aucun document en attente de vérification.")
        else:
            st.dataframe(
                review[
                    [
                        "region_name",
                        "reference_period",
                        "pdf_filename",
                        "page_url",
                    ]
                ],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "page_url": st.column_config.LinkColumn("Publication")
                },
            )

    with st.expander("Intégrité et architecture"):
        integrity = pd.DataFrame(
            [
                {
                    "Base": "Opérationnelle",
                    **operational["integrity"],
                },
                {
                    "Base": "Analytique",
                    **analytics["integrity"],
                },
            ]
        )
        st.dataframe(integrity, use_container_width=True, hide_index=True)
        st.write("Objets historiques dépréciés")
        st.dataframe(
            pd.DataFrame(analytics["deprecated_objects"]),
            use_container_width=True,
            hide_index=True,
        )
        st.caption(f"Rapport généré le {report['generated_at']}.")
