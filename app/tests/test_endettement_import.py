import io

import pandas as pd
import pytest

from src.risk_score.endettement_import import extract_mean_debt


def test_extract_mean_debt_from_department_sheet():
    buffer = io.BytesIO()
    frame = pd.DataFrame(
        [
            ["Autre ligne", 1, 2],
            ["Endettement global", 68215.5, 1758],
        ]
    )
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        frame.to_excel(writer, sheet_name="Aisne", header=False, index=False)
    result = extract_mean_debt(
        buffer.getvalue(), {"aisne": ("02", "Aisne")}
    )
    assert result["02"][1] == pytest.approx(68215.5 * 1000 / 1758)
