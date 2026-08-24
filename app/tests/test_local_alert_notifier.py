import json
from unittest.mock import patch

from src.local_alert_notifier import notify_new_alerts


def test_notifies_each_fingerprint_only_once(tmp_path):
    state = tmp_path / "alerts.json"
    alerts = [{
        "fingerprint": "abc",
        "labels": {"alertname": "ServiceUnavailable", "severity": "critical"},
        "annotations": {"summary": "Django indisponible"},
    }]

    with patch("src.local_alert_notifier.subprocess.run") as run:
        assert notify_new_alerts(alerts, state) == 1
        assert notify_new_alerts(alerts, state) == 0

    run.assert_called_once_with(
        ["notify-send", "[CRITICAL] ServiceUnavailable", "Django indisponible"],
        check=False,
    )
    assert json.loads(state.read_text()) == ["abc"]


def test_resolved_alert_is_removed_from_seen_state(tmp_path):
    state = tmp_path / "alerts.json"
    state.write_text('["abc"]')

    with patch("src.local_alert_notifier.subprocess.run"):
        assert notify_new_alerts([], state) == 0

    assert json.loads(state.read_text()) == []
