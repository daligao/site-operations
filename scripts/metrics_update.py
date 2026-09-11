"""
Merges GA4 + GSC data into year-of-goat-2027 metrics.json.
Runs after ga4_pull.py and gsc_pull.py have written their output to:
  data/ga4_latest.json
  data/gsc_latest.json

Reads existing metrics.json from GitHub raw URL, merges, writes updated file.
Preserves history[] (last 90 days) for trend tracking.
"""
import json, os, sys, urllib.request
from datetime import datetime, timedelta

GOAT_REPO = "daligao/year-of-goat-2027"
METRICS_URL = f"https://raw.githubusercontent.com/{GOAT_REPO}/main/data/metrics.json"
TOOLS_URL   = f"https://raw.githubusercontent.com/{GOAT_REPO}/main/data/tools.json"

def fetch_json(url):
    try:
        with urllib.request.urlopen(url) as r:
            return json.loads(r.read())
    except Exception as e:
        print(f"WARN: could not fetch {url}: {e}", file=sys.stderr)
        return None

def load(path):
    with open(path) as f:
        return json.load(f)

def main():
    ga4  = load("data/ga4_latest.json")
    gsc  = load("data/gsc_latest.json")
    old  = fetch_json(METRICS_URL) or {"tools": [], "graduation_thresholds": {"uv_30d": 1000, "click_to_main": 50}}
    tools_meta = fetch_json(TOOLS_URL) or {"tools": []}

    today = datetime.utcnow().strftime("%Y-%m-%d")
    cutoff = (datetime.utcnow() - timedelta(days=90)).strftime("%Y-%m-%d")

    # Index existing data by id
    old_by_id = {t["id"]: t for t in old.get("tools", [])}
    ga4_by_id  = {t["id"]: t for t in ga4.get("tools", [])}
    gsc_by_id  = gsc.get("by_tool", {})

    # All known tool ids from tools.json
    all_ids = [t["id"] for t in tools_meta.get("tools", [])]

    updated_tools = []
    for tid in all_ids:
        old_entry = old_by_id.get(tid, {"id": tid})
        ga = ga4_by_id.get(tid, {})
        gs = gsc_by_id.get(tid, {})

        entry = {
            "id": tid,
            # GA4 fields
            "uv_30d":          ga.get("uv_30d", old_entry.get("uv_30d", 0)),
            "sessions_30d":    ga.get("sessions_30d", old_entry.get("sessions_30d", 0)),
            "tool_start":      ga.get("tool_start", old_entry.get("tool_start", 0)),
            "tool_complete":   ga.get("tool_complete", old_entry.get("tool_complete", 0)),
            "completion_rate": ga.get("completion_rate", old_entry.get("completion_rate", 0)),
            "share_count":     ga.get("share_result", old_entry.get("share_count", 0)),
            "share_rate":      ga.get("share_rate", old_entry.get("share_rate", 0)),
            "click_to_main":   ga.get("click_to_main", old_entry.get("click_to_main", 0)),
            # GSC fields
            "gsc": {
                "impressions_28d": gs.get("impressions", old_entry.get("gsc", {}).get("impressions_28d", 0)),
                "clicks_28d":      gs.get("clicks", old_entry.get("gsc", {}).get("clicks_28d", 0)),
                "ctr":             gs.get("ctr", old_entry.get("gsc", {}).get("ctr", 0)),
                "avg_position":    gs.get("avg_position", old_entry.get("gsc", {}).get("avg_position", 0)),
            },
        }

        # Experiment score: composite 0-100
        uv_score     = min(entry["uv_30d"] / 1000, 1) * 35
        comp_score   = entry["completion_rate"] * 25
        share_score  = min(entry["share_rate"] * 5, 1) * 10
        ctr_score    = min(entry["gsc"]["ctr"] / 0.05, 1) * 15
        pos_score    = max(0, (50 - entry["gsc"]["avg_position"]) / 50) * 15 if entry["gsc"]["avg_position"] > 0 else 0
        entry["experiment_score"] = round(uv_score + comp_score + share_score + ctr_score + pos_score, 1)

        # Recommendation
        score = entry["experiment_score"]
        uv    = entry["uv_30d"]
        ctr   = entry["gsc"]["ctr"]
        if uv >= 1000 and entry["click_to_main"] >= 50:
            entry["recommendation"] = "Graduate"
        elif score >= 60:
            entry["recommendation"] = "Accelerate"
        elif score >= 30 or uv >= 200:
            entry["recommendation"] = "Observe"
        elif uv < 50 and entry["gsc"]["impressions_28d"] < 100:
            entry["recommendation"] = "Retire"
        else:
            entry["recommendation"] = "Observe"

        # History: append today's snapshot, drop entries older than 90 days
        snapshot = {"date": today, "uv_30d": entry["uv_30d"], "experiment_score": entry["experiment_score"],
                    "gsc_impressions": entry["gsc"]["impressions_28d"], "gsc_clicks": entry["gsc"]["clicks_28d"]}
        history = [h for h in old_entry.get("history", []) if h.get("date", "") >= cutoff]
        if not history or history[-1]["date"] != today:
            history.append(snapshot)
        entry["history"] = history

        updated_tools.append(entry)

    result = {
        "_note": "Auto-updated daily from GA4 + GSC. Do not edit manually.",
        "_updated": today,
        "_source": "ga4+gsc",
        "tools": updated_tools,
        "graduation_thresholds": old.get("graduation_thresholds", {"uv_30d": 1000, "click_to_main": 50}),
    }

    out_path = "data/metrics.json"
    os.makedirs("data", exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)
    print(f"metrics.json updated: {len(updated_tools)} tools, {today}")

if __name__ == "__main__":
    main()
