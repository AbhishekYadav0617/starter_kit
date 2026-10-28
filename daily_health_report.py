"""Generate a daily Markdown health report from integration request logs."""
import argparse
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

from integration_utils import load_logs


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_LOGS = BASE_DIR / "data" / "integration_logs.json"
DEFAULT_OUTPUT_DIR = BASE_DIR / "reports"
DEFAULT_WINDOW_HOURS = 24
DEFAULT_FAILURE_THRESHOLD = 20.0


def parse_datetime(value):
    parsed = datetime.fromisoformat(value) if value else datetime.now().astimezone()
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=datetime.now().astimezone().tzinfo)
    return parsed


def build_report(logs, as_of, window_hours, failure_threshold):
    window_start = as_of - timedelta(hours=window_hours)
    integration_names = set()
    recent = defaultdict(list)

    for index, log in enumerate(logs, start=1):
        name = log.get("integration")
        timestamp_value = log.get("timestamp")
        status = log.get("status")
        if not name or not timestamp_value or not status:
            raise ValueError(f"Log entry {index} is missing integration, timestamp, or status")

        integration_names.add(name)
        timestamp = parse_datetime(timestamp_value)
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=as_of.tzinfo)
        else:
            timestamp = timestamp.astimezone(as_of.tzinfo)
        if window_start <= timestamp <= as_of:
            recent[name].append(log)

    lines = [
        "# Daily Integration Health Report",
        "",
        f"Generated: {as_of.isoformat(timespec='minutes')}",
        f"Window: {window_start.isoformat(timespec='minutes')} to {as_of.isoformat(timespec='minutes')} ({window_hours} hours)",
        f"Attention threshold: failure rate > {failure_threshold:.1f}%",
        "",
        "| Integration | Requests | Failures | Failure rate | Avg successful latency | Status |",
        "|---|---:|---:|---:|---:|---|",
    ]
    attention = []

    for name in sorted(integration_names):
        entries = recent[name]
        request_count = len(entries)
        successes = sum(1 for entry in entries if entry["status"] == "success")
        failures = request_count - successes
        failure_rate = failures / request_count * 100 if request_count else None
        successful_latencies = [
            entry["latency_ms"]
            for entry in entries
            if entry["status"] == "success" and isinstance(entry.get("latency_ms"), (int, float))
        ]
        average_latency = (
            f"{sum(successful_latencies) / len(successful_latencies):.0f} ms"
            if successful_latencies
            else "N/A"
        )

        if not request_count:
            status = "NO DATA"
            reason = "No requests in the reporting window"
            rate_display = "N/A"
        elif failure_rate > failure_threshold:
            status = "ATTENTION"
            reason = f"{failures}/{request_count} requests failed ({failure_rate:.1f}%)"
            rate_display = f"{failure_rate:.1f}%"
        else:
            status = "HEALTHY"
            reason = ""
            rate_display = f"{failure_rate:.1f}%"

        lines.append(
            f"| {name.replace('|', '\\|')} | {request_count} | {failures} | {rate_display} | {average_latency} | {status} |"
        )
        if reason:
            attention.append(f"- **{name}**: {reason}.")

    lines.extend(["", "## Needs Attention", ""])
    lines.extend(attention or ["No integrations need attention."])
    lines.append("")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--logs", type=Path, default=DEFAULT_LOGS, help="Path to integration_logs.json")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="Directory for Markdown reports")
    parser.add_argument("--window-hours", type=float, default=DEFAULT_WINDOW_HOURS)
    parser.add_argument("--failure-threshold", type=float, default=DEFAULT_FAILURE_THRESHOLD)
    parser.add_argument("--as-of", help="Reporting end time in ISO 8601 format; defaults to local time")
    args = parser.parse_args()

    if args.window_hours <= 0:
        parser.error("--window-hours must be greater than zero")
    if not 0 <= args.failure_threshold <= 100:
        parser.error("--failure-threshold must be between 0 and 100")

    as_of = parse_datetime(args.as_of)
    report = build_report(load_logs(args.logs), as_of, args.window_hours, args.failure_threshold)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    report_path = args.output_dir / f"integration-health-{as_of:%Y-%m-%d}.md"
    report_path.write_text(report, encoding="utf-8")
    print(report)
    print(f"Report saved to: {report_path}")


if __name__ == "__main__":
    main()