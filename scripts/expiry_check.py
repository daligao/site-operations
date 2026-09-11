#!/usr/bin/env python3
"""
Content expiry check: scans site pages for stale year references.
Flags pages mentioning years that are 18+ months old.
Creates reports/stale_pages.txt for the GitHub Issues workflow.
"""
import os, re, requests
from datetime import date
from bs4 import BeautifulSoup

SITES = [
    "https://chinesefortunetools.online/",
    "https://chinesefortunetools.com/",
    "https://chinarules101.com/",
    "https://chinesenamecraft.com/",
]

HEADERS = {"User-Agent": "SiteOpsBot/1.0 (content-expiry check)"}
CURRENT_YEAR = date.today().year
STALE_THRESHOLD = CURRENT_YEAR - 2  # flag anything mentioning 2 years ago or older

def check_page_freshness(url):
    issues = []
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            return issues
        soup = BeautifulSoup(r.text, 'lxml')
        text = soup.get_text()

        # Find year mentions
        years = re.findall(r'\b(20\d{2})\b', text)
        old_years = [y for y in set(years) if int(y) <= STALE_THRESHOLD]
        if old_years:
            issues.append(f"{url} — mentions old years: {', '.join(sorted(old_years))}")

        # Check "updated" / "last modified" patterns
        updated = re.search(r'(?i)(updated|last modified|published)[:\s]+(\w+ \d{4})', text)
        if updated:
            year_match = re.search(r'20\d{2}', updated.group(2))
            if year_match and int(year_match.group()) <= STALE_THRESHOLD:
                issues.append(f"{url} — stale update date: {updated.group(2)}")

    except Exception as e:
        print(f"  Error checking {url}: {e}")
    return issues

def get_sitemap_urls(base_url):
    try:
        r = requests.get(base_url.rstrip('/') + '/sitemap.xml', headers=HEADERS, timeout=10)
        if r.status_code == 200:
            urls = re.findall(r'<loc>(https?://[^<]+)</loc>', r.text)
            return urls[:50]  # cap at 50 to avoid rate-limiting
    except:
        pass
    return [base_url]

def main():
    all_issues = []
    print(f"\nContent Expiry Check — {date.today()} (flagging refs to {STALE_THRESHOLD} or older)")
    print("=" * 60)

    for site in SITES:
        print(f"\n{site}")
        urls = get_sitemap_urls(site)
        print(f"  Checking {len(urls)} pages...")
        for url in urls:
            issues = check_page_freshness(url)
            for issue in issues:
                print(f"  ⚠️  {issue}")
                all_issues.append(issue)

    os.makedirs('reports', exist_ok=True)
    stale_path = 'reports/stale_pages.txt'
    if all_issues:
        with open(stale_path, 'w') as f:
            f.write('\n'.join(all_issues))
        print(f"\n{len(all_issues)} stale pages found. Saved to {stale_path}")
    else:
        if os.path.exists(stale_path):
            os.remove(stale_path)
        print("\n✅ No stale content found.")

if __name__ == '__main__':
    main()
