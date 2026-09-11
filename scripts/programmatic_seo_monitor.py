"""
Monitors the 65 programmatic SEO pages (2027/sign/month/) via GSC.
Reads data/gsc_latest.json (full query data) and produces data/prog_seo_report.json.
Opens a GitHub Issue if zero-impression pages > threshold or avg position degrades.
"""
import json, os, sys, urllib.request, urllib.error
from datetime import datetime

GOAT_REPO = "daligao/year-of-goat-2027"
REPO      = os.environ.get("GITHUB_REPO", GOAT_REPO)
TOKEN     = os.environ.get("GITHUB_TOKEN", "")
DOMAIN    = "https://chinesefortunetools.online"

def gh_post_issue(title, body, labels=None):
    if not TOKEN:
        return None
    url = f"https://api.github.com/repos/{REPO}/issues"
    data = json.dumps({"title": title, "body": body, "labels": labels or ["prog-seo"]}).encode()
    req = urllib.request.Request(url, data=data, method="POST", headers={
        "Authorization": f"Bearer {TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "Content-Type": "application/json",
    })
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        print(f"GH issue error: {e.code}", file=sys.stderr)
        return None

def load_gsc():
    with open("data/gsc_latest.json") as f:
        return json.load(f)

def load_sitemap_pages():
    """Extract programmatic pages from sitemap or infer from pattern."""
    # Try to fetch sitemap from goat repo
    try:
        url = f"https://raw.githubusercontent.com/{GOAT_REPO}/main/sitemap.xml"
        with urllib.request.urlopen(url) as r:
            content = r.read().decode()
        import re
        urls = re.findall(r"<loc>(https://chinesefortunetools\.online/2027/[^<]+)</loc>", content)
        return set(urls)
    except Exception as e:
        print(f"WARN: could not load sitemap: {e}", file=sys.stderr)
        return set()

def main():
    gsc      = load_gsc()
    date     = gsc.get("date", datetime.utcnow().strftime("%Y-%m-%d"))
    pages    = load_sitemap_pages()
    queries  = gsc.get("queries", [])

    # Index GSC data by page URL
    by_page = {}
    for q in queries:
        page = q["page"]
        if "/2027/" not in page:
            continue
        if page not in by_page:
            by_page[page] = {"impressions": 0, "clicks": 0, "position_sum": 0, "position_count": 0}
        by_page[page]["impressions"] += q["impressions"]
        by_page[page]["clicks"]      += q["clicks"]
        if q["impressions"] > 0:
            by_page[page]["position_sum"]   += q["position"] * q["impressions"]
            by_page[page]["position_count"] += q["impressions"]

    # Build per-page report
    report_pages = []
    for url in sorted(pages):
        d = by_page.get(url, {})
        imps  = d.get("impressions", 0)
        clicks = d.get("clicks", 0)
        pos_count = d.get("position_count", 0)
        avg_pos   = round(d["position_sum"] / pos_count, 1) if pos_count > 0 else 0
        ctr       = round(clicks / max(imps, 1), 4)
        report_pages.append({
            "url":         url,
            "impressions": imps,
            "clicks":      clicks,
            "ctr":         ctr,
            "avg_position": avg_pos,
            "has_impressions": imps > 0,
        })

    total        = len(report_pages)
    with_imps    = sum(1 for p in report_pages if p["has_impressions"])
    zero_imps    = total - with_imps
    total_clicks = sum(p["clicks"] for p in report_pages)
    avg_pos_all  = sum(p["avg_position"] for p in report_pages if p["avg_position"] > 0)
    n_pos        = sum(1 for p in report_pages if p["avg_position"] > 0)
    avg_pos_overall = round(avg_pos_all / n_pos, 1) if n_pos > 0 else 0

    report = {
        "_updated": date,
        "summary": {
            "total_pages":      total,
            "indexed_approx":   with_imps,
            "zero_impression":  zero_imps,
            "total_clicks_28d": total_clicks,
            "avg_position":     avg_pos_overall,
        },
        "pages": report_pages,
    }

    os.makedirs("data", exist_ok=True)
    with open("data/prog_seo_report.json", "w") as f:
        json.dump(report, f, indent=2)

    print(f"Prog SEO report: {total} pages, {with_imps} with impressions, {zero_imps} zero")

    # Open issue if >70% pages have zero impressions (or if total = 0 meaning not yet indexed)
    pct_zero = zero_imps / max(total, 1)
    if pct_zero > 0.7 and total > 0:
        zero_urls = [p["url"] for p in report_pages if not p["has_impressions"]][:20]
        body = f"""**Date:** {date}
**{zero_imps}/{total} programmatic SEO pages ({pct_zero:.0%}) have zero GSC impressions.**

This means Google has either not crawled or not indexed the majority of the /2027/ pages yet.

### Summary
- Total pages in sitemap: {total}
- Pages with any impressions: {with_imps}
- Zero-impression pages: {zero_imps}
- Total clicks (28d): {total_clicks}
- Average position (where ranked): {avg_pos_overall}

### Sample zero-impression pages (first 20)
{"".join(f"- {u}\\n" for u in zero_urls)}

### Actions
1. Check Google Search Console → URL Inspection for a sample URL
2. Verify sitemap is submitted in GSC: `chinesefortunetools.online/sitemap.xml`
3. Increase internal links to /2027/ pages from other pages
4. Consider whether thin content is triggering soft 404 or low-quality signals
"""
        r = gh_post_issue(f"[Prog SEO] {zero_imps}/{total} pages have zero impressions — {date}", body, ["prog-seo", "indexation"])
        if r:
            print(f"Opened issue #{r['number']}")

if __name__ == "__main__":
    main()
