#!/usr/bin/env python3
"""
Weekly site audit: checks all registered sites for SEO issues.
Outputs reports/audit-YYYY-MM-DD.json and a human-readable summary.
"""
import os, json, requests
from datetime import date
from bs4 import BeautifulSoup

SITES = [
    {"name": "chinesefortunetools.online", "url": "https://chinesefortunetools.online/"},
    {"name": "chinesefortunetools.com",    "url": "https://chinesefortunetools.com/"},
    {"name": "chinarules101.com",          "url": "https://chinarules101.com/"},
    {"name": "chinesenamecraft.com",       "url": "https://chinesenamecraft.com/"},
]

HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}

def audit_page(url):
    issues = []
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            return {"url": url, "status": r.status_code, "issues": [f"HTTP {r.status_code}"]}
        soup = BeautifulSoup(r.text, 'lxml')

        # Title
        title = soup.find('title')
        if not title or not title.text.strip():
            issues.append("MISSING title tag")
        elif len(title.text) > 70:
            issues.append(f"Title too long ({len(title.text)} chars, max 70)")
        elif len(title.text) < 20:
            issues.append(f"Title too short ({len(title.text)} chars)")

        # Meta description
        desc = soup.find('meta', {'name': 'description'})
        if not desc or not desc.get('content', '').strip():
            issues.append("MISSING meta description")
        elif len(desc['content']) > 165:
            issues.append(f"Description too long ({len(desc['content'])} chars)")

        # Canonical
        canonical = soup.find('link', {'rel': 'canonical'})
        if not canonical:
            issues.append("MISSING canonical link")

        # H1
        h1s = soup.find_all('h1')
        if len(h1s) == 0:
            issues.append("MISSING H1")
        elif len(h1s) > 1:
            issues.append(f"Multiple H1s ({len(h1s)})")

        # Images without alt
        imgs_no_alt = [img.get('src','?')[:60] for img in soup.find_all('img') if not img.get('alt')]
        if imgs_no_alt:
            issues.append(f"Images missing alt: {len(imgs_no_alt)}")

        # GA4
        if 'gtag' not in r.text and 'googletagmanager' not in r.text:
            issues.append("MISSING GA4 tag")

        # JSON-LD
        if 'application/ld+json' not in r.text:
            issues.append("MISSING JSON-LD schema")

        return {"url": url, "status": 200, "title": title.text.strip() if title else "", "issues": issues}
    except Exception as e:
        return {"url": url, "status": "error", "issues": [str(e)]}

def check_sitemap(base_url):
    sitemap_url = base_url.rstrip('/') + '/sitemap.xml'
    try:
        r = requests.get(sitemap_url, headers=HEADERS, timeout=10)
        if r.status_code == 200 and '<url>' in r.text:
            count = r.text.count('<url>')
            return {"ok": True, "count": count}
        return {"ok": False, "status": r.status_code}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def check_orphans(base_url):
    """Find pages in sitemap not linked internally, and internal links missing from sitemap."""
    try:
        import re, urllib.parse
        # Fetch sitemap URLs
        sitemap_url = base_url.rstrip('/') + '/sitemap.xml'
        r = requests.get(sitemap_url, headers=HEADERS, timeout=10)
        sitemap_urls = set(re.findall(r'<loc>(.*?)</loc>', r.text))

        # Fetch homepage + crawl one level of internal links
        r2 = requests.get(base_url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r2.text, 'lxml')
        domain = urllib.parse.urlparse(base_url).netloc
        linked = set()
        for a in soup.find_all('a', href=True):
            href = urllib.parse.urljoin(base_url, a['href'])
            parsed = urllib.parse.urlparse(href)
            if parsed.netloc == domain:
                clean = f"{parsed.scheme}://{parsed.netloc}{parsed.path.rstrip('/')}/"
                linked.add(clean)

        in_sitemap_not_linked = [u for u in sitemap_urls if u.rstrip('/') + '/' not in linked and u not in linked]
        linked_not_in_sitemap = [u for u in linked if u not in sitemap_urls and u.rstrip('/') + '/' not in sitemap_urls
                                  and u != base_url and u != base_url.rstrip('/') + '/']
        return {
            'orphans_in_sitemap': in_sitemap_not_linked[:10],
            'linked_missing_from_sitemap': linked_not_in_sitemap[:10],
        }
    except Exception as e:
        return {'error': str(e)}

def main():
    site_filter = os.environ.get('SITE_FILTER', 'all')
    sites = SITES if site_filter == 'all' else [s for s in SITES if site_filter in s['name']]

    results = []
    print(f"\n{'='*60}")
    print(f"Site Audit — {date.today()}")
    print(f"{'='*60}")

    for site in sites:
        print(f"\n{site['name']} ...")
        result = audit_page(site['url'])
        result['sitemap'] = check_sitemap(site['url'])
        result['orphans'] = check_orphans(site['url'])
        result['site_name'] = site['name']
        results.append(result)

        # Print orphan report
        orphans = result.get('orphans', {})
        if orphans.get('orphans_in_sitemap'):
            print(f"  🔍 Sitemap orphans (not linked from homepage): {len(orphans['orphans_in_sitemap'])}")
        if orphans.get('linked_missing_from_sitemap'):
            print(f"  ⚠️  Linked but not in sitemap: {len(orphans['linked_missing_from_sitemap'])}")

        if result['issues']:
            for issue in result['issues']:
                print(f"  ⚠️  {issue}")
        else:
            print(f"  ✅ No issues")
        sm = result['sitemap']
        if sm.get('ok'):
            print(f"  🗺  Sitemap: {sm['count']} URLs")
        else:
            print(f"  ❌ Sitemap: {sm}")

    # Save report
    os.makedirs('reports', exist_ok=True)
    report_path = f"reports/audit-{date.today()}.json"
    with open(report_path, 'w') as f:
        json.dump({"date": str(date.today()), "sites": results}, f, indent=2)

    total_issues = sum(len(r['issues']) for r in results)
    print(f"\n{'='*60}")
    print(f"Total issues: {total_issues} across {len(results)} sites")
    print(f"Report saved: {report_path}")

    if total_issues > 0:
        print("\nSummary of issues:")
        for r in results:
            if r['issues']:
                print(f"  {r['site_name']}: {', '.join(r['issues'])}")

if __name__ == '__main__':
    main()
