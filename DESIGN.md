# Daily Health Report Design

## Purpose

`daily_health_report.py` reads integration request logs, summarizes each integration over a configurable recent time window, and writes a Markdown health report. A Windows Scheduled Task can run the process daily at 8:00 AM.

## Scope and components

| Component | Responsibility |
|---|---|
| `daily_health_report.py` | Parses options, loads logs, filters and aggregates records, renders Markdown, and writes the report. |
| `integration_utils.py` | Loads the JSON log file and returns its `logs` array. |
| `data/integration_logs.json` | Default input, containing synthetic request records. |
| `schedule_daily_report.ps1` | Registers the daily Windows Scheduled Task. |
| `reports/` | Default destination directory, created if it does not exist. |

The report process is local and file-based. It does not call integration APIs, persist aggregate state, or send notifications.

## Process flow

1. Parse command-line options and validate that the reporting window is positive and the failure threshold is between 0 and 100 inclusive.
2. Resolve the report end time from `--as-of`, or use the current local time when it is omitted.
3. Load the JSON input using `load_logs`. The expected top-level shape is an object containing a `logs` array.
4. For every log entry, require non-empty `integration`, `timestamp`, and `status` values. Parse the ISO 8601 timestamp and normalize it to the report end time's timezone.
5. Include records whose timestamps are within the inclusive interval from `as_of - window_hours` through `as_of`.
6. Aggregate the included records by integration and render a Markdown table and an attention section.
7. Create the output directory if necessary, write the report as UTF-8, and print both the report and its output path.

Invalid JSON, file access errors, malformed timestamps, and entries missing required fields raise errors; the process does not turn these failures into a successful-looking report.

## Input data contract

Each entry in `logs` must contain:

| Field | Expected value | Use |
|---|---|---|
| `integration` | Non-empty integration name | Grouping and report row label. |
| `timestamp` | ISO 8601 datetime string | Inclusion in the reporting window. |
| `status` | Non-empty status string | Success/failure classification. |

`latency_ms` is optional for report generation; numeric values on successful records are used to calculate average successful latency. `status_code` and other fields are currently ignored. Naive timestamps are interpreted in the machine's local timezone; timezone-aware timestamps are converted to the timezone of `as_of`.

## Aggregation and status rules

For each integration found anywhere in the input:

- **Requests** is the number of records in the reporting window.
- **Failures** is the number of those records whose status is anything other than exactly `success`. This includes statuses such as `error` and `timeout`.
- **Failure rate** is `failures / requests * 100`. An integration is `ATTENTION` only when this percentage is strictly greater than the configured threshold; equality remains `HEALTHY`.
- **Average successful latency** is the arithmetic mean of numeric `latency_ms` values on successful records. It is shown as a whole number of milliseconds, or `N/A` if no eligible values exist.
- **No requests in the window** produces `NO DATA`, with an `N/A` failure rate and an explanatory item in the attention section.

The table includes all integration names present in the input, including names with no records in the selected window. The report's attention section lists integrations above threshold and those with no data; if neither applies, it says that no integrations need attention.

## Configuration and outputs

| Option | Default | Description |
|---|---|---|
| `--logs` | `data/integration_logs.json` beside the script | Input JSON file. |
| `--output-dir` | `reports/` beside the script | Directory for generated reports. |
| `--window-hours` | `24` | Positive floating-point lookback window. |
| `--failure-threshold` | `20.0` | Failure-rate percentage from 0 to 100. |
| `--as-of` | Current local time | Optional ISO 8601 report end time. |

The output filename is `integration-health-YYYY-MM-DD.md`, using the date of `as_of`. A second run for the same date replaces the existing file. The report records its generation time, window bounds, and threshold.

Example:

```powershell
python .\daily_health_report.py --window-hours 24 --failure-threshold 20
```

## Scheduling and operations

Run `schedule_daily_report.ps1` in a PowerShell session with permission to register a scheduled task. It registers **Integration Health Daily Report**, invoking the script with the `python` executable found on `PATH`, using the repository directory as the working directory. The trigger is daily at 8:00 AM, and `StartWhenAvailable` allows a missed run to start when the machine next becomes available.

The scheduled task uses the script's defaults; to change its input, output, window, or threshold, adjust the scheduled action arguments or invoke the Python script directly with the corresponding options. Check the task's last-run result and the generated file in `reports/` when troubleshooting. The script prints exceptions through normal Python failure behavior; it does not configure a separate log file or retry policy.

## Current limitations and considerations

- The sample data covers about one hour on August 4, 2026, while the default report window is the 24 hours preceding the current time. Running the default report against this fixture at another date can result in `NO DATA`; use `--as-of` to select a matching interval when exercising the sample.
- The process treats every non-`success` status as a failure. New status categories therefore affect the failure rate unless this rule is intentionally changed.
- There is no explicit validation of the JSON top-level type, that `logs` is an array, or that individual field values have the expected types beyond the required-value checks and datetime parsing.
- The date-based output path is not a run-history store: multiple reports with the same `as_of` date overwrite one another.
- The Windows scheduler's 8:00 AM execution time is local to the host. The task depends on Python being available on `PATH` when the task is registered and executable by the task identity.
