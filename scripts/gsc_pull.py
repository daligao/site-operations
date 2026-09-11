"""
Google Search Console API pull → per-page and per-query metrics.
Requires env: GSC_SITE_URL, GOOGLE_SERVICE_ACCOUNT_JSON.
"""
import os, json, sys
from datetime import datetime, timedelta
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

SITE_URL = os.environ["GSC_SITE_URL"]  # e.g. "sc-domain:chinesefortunetools.online"
SA_JSON = json.loads(os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"])
DAYS = 28

def service():
    creds = Credentials.from_service_account_info(SA_JSON, scopes=["https://www.googleapis.com/auth/webmasters.readonly"])
    return build("searchconsole", "v1", credentials=creds, cache_discovery=False)

def date_range():
    end = datetime.utcnow() - timedelta(days=2)
    start = end - timedelta(days=DAYS - 1)
    return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")

def query(svc, dimensions, row_limit=1000):
    start, end = date_range()
    body = {
        "startDate": start, "endDate": end,
        "dimensions": dimensions,
        "rowLimit": row_limit,
        "dataState": "all",
    }
    resp = svc.searchanalytics().query(siteUrl=SITE_URL, body=body).execute()
    return resp.get("rows", [])

def path_to_id(url):
    """https://chinesefortunetools.online/gift-checker/ → gift-checker"""
    path = url.replace("https://chinesefortunetools.online", "").replace("http://chinesefortunetools.online", "")
    tid = path.strip("/").split("/")[0]
    return tid if tid else "homepage"

def main():
    svc = service()

    # Per-page metrics
    page_rows = query(svc, ["page"])
    by_tool = {}
    for row in page_rows:
        url = row["keys"][0]
        tid = path_to_id(url)
        if tid not in by_tool:
            by_tool[tid] = {"impressions": 0, "clicks": 0, "ctr": 0, "position": 0, "_pos_sum": 0, "_count": 0}
        t = by_tool[tid]
        t["impressions"] += int(row.get("impressions", 0))
        t["clicks"] += int(row.get("clicks", 0))
        t["_pos_sum"] += row.get("position", 0) * int(row.get("impressions", 1))
        t["_count"] += int(row.get("impressions", 1))

    # Finalise per-tool
    for tid, t in by_tool.items():
        t["ctr"] = round(t["clicks"] / max(t["impressions"], 1), 4)
        t["avg_position"] = round(t["_pos_sum"] / max(t["_count"], 1), 1)
        del t["_pos_sum"], t["_count"]

    # Per-query metrics (for SEO opportunity bot)
    query_rows = query(svc, ["page", "query"], row_limit=2000)
    queries = []
    for row in query_rows:
        url, kw = row["keys"][0], row["keys"][1]
        queries.append({
            "page": url,
            "tool_id": path_to_id(url),
            "query": kw,
            "clicks": int(row.get("clicks", 0)),
            "impressions": int(row.get("impressions", 0)),
            "ctr": round(row.get("ctr", 0), 4),
            "position": round(row.get("position", 0), 1),
        })

    out = {
        "date": datetime.utcnow().strftime("%Y-%m-%d"),
        "site": SITE_URL,
        "date_range_days": DAYS,
        "by_tool": by_tool,
        "queries": queries,
    }
    print(json.dumps(out, indent=2))

if __name__ == "__main__":
    main()
