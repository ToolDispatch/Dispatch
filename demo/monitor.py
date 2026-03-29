# monitor.py — service health monitor
from notifier import send_slack_alert, format_alert


def check_health(services: list) -> dict:
    """Check service health and alert on failures. Returns summary dict."""
    results = {"healthy": [], "down": []}

    for svc in services:
        if svc.get("healthy"):
            results["healthy"].append(svc["name"])
        else:
            results["down"].append(svc["name"])
            alert_msg = format_alert(svc["name"], "down", svc.get("details"))
            send_slack_alert(alert_msg, "#alerts")

    return results
