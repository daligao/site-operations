#!/usr/bin/env python3
"""DNS + GitHub Pages health check for all repos."""
import os, json, requests
from datetime import date

TOKEN = os.environ.get('GH_TOKEN', '')
HEADERS = {
    'Authorization': f'Bearer {TOKEN}',
    'Accept': 'application/vnd.github+json',
    'X-GitHub-Api-Version': '2022-11-28'
}

PAGES_REPOS = [
    {'repo': 'daligao/year-of-goat-2027', 'cname': 'chinesefortunetools.online'},
]

def check_pages(repo, expected_cname):
    url = f'https://api.github.com/repos/{repo}/pages'
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        if r.status_code != 200:
            return [f"Pages API returned {r.status_code}"]
        d = r.json()
        issues = []
        if d.get('cname') != expected_cname:
            issues.append(f"CNAME mismatch: expected {expected_cname}, got {d.get('cname')}")
        cert = d.get('https_certificate', {})
        if cert.get('state') not in ('approved', None):
            issues.append(f"HTTPS cert state: {cert.get('state')}")
        if d.get('status') not in ('built', 'building'):
            issues.append(f"Pages status: {d.get('status')}")
        return issues
    except Exception as e:
        return [str(e)]

def main():
    results = []
    print(f"\nDNS + Pages Health — {date.today()}")
    print("=" * 50)
    for p in PAGES_REPOS:
        issues = check_pages(p['repo'], p['cname'])
        flag = '✅' if not issues else '⚠️'
        print(f"{flag} {p['cname']} ({p['repo']})")
        for i in issues: print(f"   ↳ {i}")
        results.append({'repo': p['repo'], 'cname': p['cname'], 'issues': issues})

    os.makedirs('reports', exist_ok=True)
    with open(f"reports/dns-{date.today()}.json", 'w') as f:
        json.dump({'date': str(date.today()), 'checks': results}, f, indent=2)

if __name__ == '__main__':
    main()
