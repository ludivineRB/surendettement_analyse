"""Display new Alertmanager alerts as local Linux desktop notifications."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import time
from pathlib import Path
from urllib.request import urlopen

DEFAULT_URL = "http://127.0.0.1:9093/api/v2/alerts"
DEFAULT_STATE = Path("/tmp/surendettement-alert-notifier.json")


def fetch_active_alerts(url: str = DEFAULT_URL) -> list[dict]:
    with urlopen(url, timeout=5) as response:  # nosec B310 - local URL by default
        alerts = json.loads(response.read())
    return [alert for alert in alerts if alert.get("status", {}).get("state") == "active"]


def notify_new_alerts(alerts: list[dict], state_path: Path = DEFAULT_STATE) -> int:
    seen = _load_seen(state_path)
    current = {alert.get("fingerprint", "") for alert in alerts}
    new_alerts = [alert for alert in alerts if alert.get("fingerprint", "") not in seen]
    for alert in new_alerts:
        labels = alert.get("labels", {})
        annotations = alert.get("annotations", {})
        title = f"[{labels.get('severity', 'warning').upper()}] {labels.get('alertname', 'Alerte')}"
        message = annotations.get("summary") or annotations.get("description") or "Alerte active"
        subprocess.run(["notify-send", title, message], check=False)  # noqa: S603
    state_path.write_text(json.dumps(sorted(current)), encoding="utf-8")
    return len(new_alerts)


def _load_seen(state_path: Path) -> set[str]:
    try:
        return set(json.loads(state_path.read_text(encoding="utf-8")))
    except (FileNotFoundError, ValueError, TypeError):
        return set()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="local-alert-notifier")
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--interval", type=int, default=30)
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args(argv)
    if shutil.which("notify-send") is None:
        parser.error("notify-send est requis (paquet libnotify-bin)")
    while True:
        try:
            notify_new_alerts(fetch_active_alerts(args.url), args.state)
        except Exception as exc:
            print(f"Alertmanager indisponible : {exc}")
        if args.once:
            return 0
        time.sleep(max(5, args.interval))


if __name__ == "__main__":
    raise SystemExit(main())
