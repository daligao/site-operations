#!/usr/bin/env python3
"""
Weekly page element snapshot + regression detection.
Tracks: title, description, H1, canonical, word_count, schema_count.
Opens GitHub Issue on regression (field disappeared or changed unexpectedly).
"""
import os, json, subprocess, datetime, re
import requests
from bs4 import BeautifulSoup

UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
TOKEN = os.environ.get('GH_TOKEN', '')
REPO  = os.environ.get('REPO', '')

PAGES = [
    'https://chinesefortunetools.online/',
    'https://chinesefortunetools.online/gift-checker/',
    'https://chinesefortunetools.online/red-envelope/',
    'https://chinesefortunetools.online/zodiac/',
    'https://chinesefortunetools.online/kinship/',
    'https://chinesefortunetools.com/',
    'https://chinarules101.com/',
    'https://chinesenamecraft.com/',
]

SNAPSHOT_DIR = 'data/page-snapshots'

def extract(url):
    try:
        r = requests.get(url, headers={'User-Agent': UA}, timeout=15)
        soup = BeautifulSoup(r.text, 'lxml')
        title = soup.title.string.strip() if soup.title else ''
        desc_tag = soup.find('meta', attrs={'name': 'description'})
        desc = desc_tag['content'].strip() if desc_tag and desc_tag.get('content') else ''
        h1s = [h.get_text(strip=True) for h in soup.find_all('h1')]
        canonical = ''
        can_tag = soup.find('link', rel='canonical')
        if can_tag: canonical = can_tag.get('href', '')
        text = soup.get_text(' ', strip=True)
        word_count = len(re.findall(r'\b\w+\b', text))
        schema_count = len(soup.find_all('script', type='application/ld+json'))
        return {
            'url': url, 'status': r.status_code,
            'title': title, 'description': desc,
            'h1s': h1s, 'canonical': canonical,
            'word_count': word_count, 'schema_count': schema_count,
        }
    except Exception as e:
        return {'url': url, 'status': 0, 'error': str(e)}

def load_prev(slug):
    path = f'{SNAPSHOT_DIR}/{slug}.json'
    if os.path.exists(path):
        return json.load(open(path))
    return None

def save(slug, data):
    os.makedirs(SNAPSHOT_DIR, exist_ok=True)
    with open(f'{SNAPSHOT_DIR}/{slug}.json', 'w') as f:
        json.dump(data, f, indent=2)

def open_issue(title, body):
    if not TOKEN or not REPO: return
    subprocess.run([
        'gh', 'issue', 'create',
        '--title', title, '--body', body,
        '--label', 'page-regression', '--repo', REPO
    ], check=False)

def slug(url):
    return url.replace('https://', '').rstrip('/').replace('/', '_').replace('.', '-')

today = str(datetime.date.today())
regressions = []

for url in PAGES:
    s = slug(url)
    current = extract(url)
    current['date'] = today
    prev = load_prev(s)

    if prev:
        issues = []
        if current.get('status', 0) < 200:
            issues.append(f"Page returned HTTP {current.get('status')} (was {prev.get('status')})")
        if not current.get('title') and prev.get('title'):
            issues.append(f"Title disappeared (was: `{prev['title']}`)")
        if current.get('title') and prev.get('title') and current['title'] != prev['title']:
            issues.append(f"Title changed: `{prev['title']}` → `{current['title']}`")
        if not current.get('h1s') and prev.get('h1s'):
            issues.append(f"H1 disappeared (was: `{prev['h1s'][0]}`)")
        if current.get('schema_count', 0) < prev.get('schema_count', 0):
            issues.append(f"Schema count dropped: {prev['schema_count']} → {current['schema_count']}")
        wc_delta = current.get('word_count', 0) - prev.get('word_count', 0)
        if wc_delta < -500:
            issues.append(f"Word count dropped by {abs(wc_delta)} (was {prev['word_count']}, now {current['word_count']})")

        if issues:
            title = f"🔴 Page regression: {url}"
            body = f"**URL:** {url}\n**Date:** {today}\n\n**Issues detected:**\n" + '\n'.join(f'- {i}' for i in issues)
            body += f"\n\n> Auto-detected by page-monitor.yml"
            open_issue(title, body)
            regressions.append({'url': url, 'issues': issues})
            print(f"⚠️  {url}: {len(issues)} regression(s)")
        else:
            print(f"✅ {url}: no changes")
    else:
        print(f"📸 {url}: baseline snapshot saved")

    save(s, current)

if regressions:
    print(f"\n{len(regressions)} regression(s) detected — Issues opened.")
else:
    print("\nAll pages stable.")
