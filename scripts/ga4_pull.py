"""
GA4 Data API pull → writes per-tool metrics to stdout as JSON.
Requires env: GA4_PROPERTY_ID, GOOGLE_SERVICE_ACCOUNT_JSON (full JSON string).
Events tracked: tool_start, tool_complete, share_result, visit_main_site.
"""
import os, json, sys
from datetime import datetime, timedelta
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    RunReportRequest, Dimension, Metric, DateRange, FilterExpression,
    Filter, FilterExpressionList
)
from google.oauth2.service_account import Credentials

PROPERTY_ID = os.environ["GA4_PROPERTY_ID"]
SA_JSON = json.loads(os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"])
DATE_RANGE_DAYS = 30

def client():
    creds = Credentials.from_service_account_info(SA_JSON, scopes=["https://www.googleapis.com/auth/analytics.readonly"])
    return BetaAnalyticsDataClient(credentials=creds)

def run(c, dimensions, metrics, date_range_days=DATE_RANGE_DAYS, row_limit=500):
    req = RunReportRequest(
        property=f"properties/{PROPERTY_ID}",
        dimensions=[Dimension(name=d) for d in dimensions],
        metrics=[Metric(name=m) for m in metrics],
        date_ranges=[DateRange(start_date=f"{date_range_days}daysAgo", end_date="today")],
        limit=row_limit,
    )
    return c.run_report(req)

def pull_uv_sessions(c):
    """active users + sessions per page path."""
    resp = run(c, ["pagePath"], ["activeUsers", "sessions"])
    out = {}
    for row in resp.rows:
        path = row.dimension_values[0].value
        out[path] = {
            "uv_30d": int(row.metric_values[0].value),
            "sessions_30d": int(row.metric_values[1].value),
        }
    return out

def pull_events(c):
    """Custom events per page path."""
    resp = run(c, ["pagePath", "eventName"], ["eventCount"])
    out = {}
    tracked = {"tool_start", "tool_complete", "share_result", "visit_main_site"}
    for row in resp.rows:
        path = row.dimension_values[0].value
        ev = row.dimension_values[1].value
        if ev not in tracked:
            continue
        if path not in out:
            out[path] = {}
        out[path][ev] = int(row.metric_values[0].value)
    return out

def path_to_id(path):
    """Convert /gift-checker/ → gift-checker."""
    return path.strip("/").split("/")[0] if path else ""

def main():
    c = client()
    uv = pull_uv_sessions(c)
    events = pull_events(c)

    # Merge by tool id
    merged = {}
    for path, stats in uv.items():
        tid = path_to_id(path)
        if not tid or tid in ("lab", "beta", "api", "dashboard", "changelog", "previews", "2027", ""):
            continue
        if tid not in merged:
            merged[tid] = {"id": tid, "uv_30d": 0, "sessions_30d": 0, "tool_start": 0, "tool_complete": 0, "share_result": 0, "visit_main_site": 0}
        merged[tid]["uv_30d"] += stats["uv_30d"]
        merged[tid]["sessions_30d"] += stats["sessions_30d"]

    for path, evs in events.items():
        tid = path_to_id(path)
        if tid not in merged:
            continue
        for k, v in evs.items():
            merged[tid][k] = merged[tid].get(k, 0) + v

    # Compute derived rates
    for tid, t in merged.items():
        starts = t.get("tool_start", 0)
        t["completion_rate"] = round(t["tool_complete"] / starts, 4) if starts > 0 else 0
        t["share_rate"] = round(t["share_result"] / max(t["uv_30d"], 1), 4)
        t["click_to_main"] = t.pop("visit_main_site", 0)

    print(json.dumps({"date": datetime.utcnow().strftime("%Y-%m-%d"), "tools": list(merged.values())}, indent=2))

if __name__ == "__main__":
    main()
