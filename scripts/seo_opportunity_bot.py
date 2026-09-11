"""
SEO Opportunity Bot — reads GSC query data and opens GitHub Issues for actionable opportunities.
Runs weekly. Reads data/gsc_latest.json written by gsc_pull.py.
Requires env: GITHUB_TOKEN, GITHUB_REPO (e.g. daligao/year-of-goat-2027).
"""
import json, os, sys
from datetime import datetime
import urllib.request, urllib.error

REPO    = os.environ.get("GITHUB_REPO", "daligao/year-of-goat-2027")
TOKEN   = os.environ["GITHUB_TOKEN"]
BASE    = "https://api.github.com"

def gh(method, path, body=None):
    url = f"{BASE}{path}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": f"Bearer {TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "Content-Type": "application/json",
    })
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        print(f"GH {method} {path}: {e.code} {e.read()}", file=sys.stderr)
        return None

def open_issue(title, body, labels=None):
    return gh("POST", f"/repos/{REPO}/issues", {
        "title": title, "body": body, "labels": labels or ["seo-opportunity"]
    })

def load():
    with open("data/gsc_latest.json") as f:
        return json.load(f)

def find_opportunities(data):
    queries = data.get("queries", [])
    date    = data.get("date", datetime.utcnow().strftime("%Y-%m-%d"))
    opps    = {"high_imp_low_ctr": [], "near_top": [], "imp_no_clicks": [], "growing": []}

    for q in queries:
        imp   = q.get("impressions", 0)
        clicks = q.get("clicks", 0)
        ctr    = q.get("ctr", 0)
        pos    = q.get("position", 0)

        if imp >= 100 and ctr < 0.02:
            opps["high_imp_low_ctr"].append(q)
        if 8 <= pos <= 20 and imp >= 50:
            opps["near_top"].append(q)
        if imp >= 20 and clicks == 0:
            opps["imp_no_clicks"].append(q)

    return opps, date

def fmt_table(rows, cols):
    header = "| " + " | ".join(cols) + " |"
    sep    = "|" + "|".join(["---"] * len(cols)) + "|"
    lines  = [header, sep]
    for r in rows[:20]:
        vals = []
        for c in cols:
            v = r.get(c, "")
            vals.append(str(v) if not isinstance(v, float) else f"{v:.3f}")
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines)

def main():
    data = load()
    opps, date = find_opportunities(data)
    created = 0

    # 1. High impression, low CTR
    rows = sorted(opps["high_imp_low_ctr"], key=lambda x: -x["impressions"])
    if rows:
        body = f"""**Date:** {date}
**Found {len(rows)} queries with ≥100 impressions and CTR < 2%.**
These are ranking but not being clicked — title/description optimisation opportunity.

{fmt_table(rows, ["tool_id","query","impressions","clicks","ctr","position"])}

### Suggested actions
- Review title tags and meta descriptions for these pages
- Ensure query intent matches page content
- Add structured data if missing
"""
        r = open_issue(f"[SEO] High Impression / Low CTR — {date}", body, ["seo-opportunity", "title-optimization"])
        if r:
            created += 1
            print(f"Opened issue #{r['number']}: High Imp/Low CTR")

    # 2. Near-top (position 8-20)
    rows = sorted(opps["near_top"], key=lambda x: x["position"])
    if rows:
        body = f"""**Date:** {date}
**Found {len(rows)} queries ranking position 8–20 with ≥50 impressions.**
A small push could move these to top 10 and significantly increase clicks.

{fmt_table(rows, ["tool_id","query","impressions","clicks","ctr","position"])}

### Suggested actions
- Add content depth (FAQ, examples, related tools) to these pages
- Build internal links from other pages to these pages
- Check if competitor pages for these queries have content elements we're missing
"""
        r = open_issue(f"[SEO] Near-Top Opportunities (Position 8–20) — {date}", body, ["seo-opportunity", "near-top"])
        if r:
            created += 1
            print(f"Opened issue #{r['number']}: Near-Top")

    # 3. Impressions but zero clicks
    rows = sorted(opps["imp_no_clicks"], key=lambda x: -x["impressions"])
    if rows:
        body = f"""**Date:** {date}
**Found {len(rows)} pages/queries with impressions but zero clicks.**
Appearing in search but being completely ignored — possible mismatch between query intent and page content.

{fmt_table(rows, ["tool_id","query","impressions","position"])}

### Suggested actions
- Review if page content matches what searchers expect
- Add featured snippet-style answer blocks at the top of the page
- Consider if these queries warrant a dedicated page
"""
        r = open_issue(f"[SEO] Impressions With Zero Clicks — {date}", body, ["seo-opportunity", "zero-clicks"])
        if r:
            created += 1
            print(f"Opened issue #{r['number']}: Zero Clicks")

    if created == 0:
        print("No significant SEO opportunities found this week.")
    else:
        print(f"Created {created} SEO opportunity issues.")

if __name__ == "__main__":
    main()
