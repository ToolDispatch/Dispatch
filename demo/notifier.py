# notifier.py — alert dispatch for service monitoring
from typing import Optional


def send_slack_alert(message: str, channel: str, priority: str = "normal") -> bool:
    """Send alert to Slack channel. Returns True on success."""
    ...


def send_pagerduty(message: str, severity: str, service_key: str) -> str:
    """Trigger PagerDuty incident. Returns incident ID."""
    ...


def format_alert(service_name: str, status: str, details: Optional[dict] = None) -> str:
    """Format a structured alert message for downstream consumers."""
    parts = [f"[{status.upper()}] {service_name}"]
    if details:
        parts.append(" | ".join(f"{k}={v}" for k, v in details.items()))
    return " ".join(parts)
