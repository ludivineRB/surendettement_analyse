import pandas as pd

from src.statinfo_bi_quality import (
    EXPECTED_DEPARTMENT_CODES,
    build_indicator_dictionary,
    build_validation_summary,
    curate_bi_frame,
)


def _sample_raw_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "reference_year": 2025,
                "reference_month": "février",
                "region": "Corse",
                "departement_code": "2a",
                "departement_name": "Corse du Sud",
                "indicator_name": "TOTAL",
                "value": "5.2",
                "source_file": "sample.pdf",
                "page_number": 6,
            },
            {
                "reference_year": 2025,
                "reference_month": "février",
                "region": "Corse",
                "departement_code": "2b",
                "departement_name": "Haute Corse",
                "indicator_name": "Comptes ordinaires créditeurs",
                "value": "3.3",
                "source_file": "sample.pdf",
                "page_number": 6,
            },
        ]
    )


def test_curate_bi_frame_adds_stable_bi_columns_and_types():
    curated = curate_bi_frame(_sample_raw_frame())

    assert list(curated["departement_code"]) == ["2A", "2B"]
    assert set(curated["reference_period"]) == {"2025-02"}
    assert set(curated["reference_month_number"]) == {2}
    assert set(curated["reference_month_label"]) == {"février"}
    assert set(curated["unit"]) == {"milliards_euros"}
    assert curated["indicator_code"].notna().all()


def test_validation_summary_reports_missing_departments_and_no_unknown_indicators():
    curated = curate_bi_frame(_sample_raw_frame())
    summary = build_validation_summary(curated)

    assert summary["department_count"] == 2
    assert "01" in summary["missing_departments"]
    assert "2A" not in summary["missing_departments"]
    assert "2B" not in summary["missing_departments"]
    assert summary["suspicious_indicators"] == []
    assert summary["duplicate_count"] == 0
    assert summary["source_period_mismatches"] == {}


def test_indicator_dictionary_matches_expected_department_pipeline_scope():
    dictionary = build_indicator_dictionary()

    assert dictionary["indicator_code"].is_unique
    assert dictionary["indicator_order"].is_unique
    assert len(EXPECTED_DEPARTMENT_CODES) == 96
    assert {"indicator_code", "indicator_name", "indicator_group", "unit", "indicator_order"}.issubset(
        dictionary.columns
    )
