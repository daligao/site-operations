#!/usr/bin/env python3
"""
Weekly "What we built" changelog generator.
Reads: closed Issues + merged PRs from the past 7 days across Lab repos.
Outputs: data/changelog.json + data/changelog.md
"""
import os, json, subprocess, datetime, urllib.request

TOKEN = os.environ.get('GH_TOKEN', '')
REPOS = [
    'daligao/year-of-goat-2027',
    'daligao/site-operations',
    'daligao/site-config',
]

def gh_api(path):
    req = urllib.request.Request(
        f'https://api.github.com{path}',
        headers={
            'Authorization': f'Bearer {TOKEN}',
            'Accept': 'application/vnd.github+json',
            'X-GitHub-Api-Version': '2022-11-28',
        }
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())

today = datetime.date.today()
week_ago = (today - datetime.timedelta(days=7)).isoformat() + 'T00:00:00Z'

entries = {'launches': [], 'improvements': [], 'fixes': [], 'retirements': []}

for repo in REPOS:
    # Closed issues in past 7 days
    try:
        issues = gh_api(f'/repos/{repo}/issues?state=closed&since={week_ago}&per_page=50')
        for i in issues:
            if i.get('pull_request'): continue
            title = i['title']
            labels = [l['name'] for l in i.get('labels', [])]
            if 'graduation' in labels:
                entries['launches'].append(f"[{repo.split('/')[1]}] 🏆 {title}")
            elif 'experiment-review' in labels or 'page-regression' in labels:
                entries['fixes'].append(f"[{repo.split('/')[1]}] {title}")
            else:
                entries['improvements'].append(f"[{repo.split('/')[1]}] {title}")
    except: pass

    # Merged PRs
    try:
        prs = gh_api(f'/repos/{repo}/pulls?state=closed&per_page=20')
        for pr in prs:
            if not pr.get('merged_at'): continue
            if pr['merged_at'] < week_ago: continue
            entries['improvements'].append(f"[{repo.split('/')[1]}] PR: {pr['title']}")
    except: pass

# Recent tools.json changes as proxy for launches
try:
    url = 'https://raw.githubusercontent.com/daligao/year-of-goat-2027/main/data/tools.json'
    with urllib.request.urlopen(url) as r:
        tools = json.loads(r.read())['tools']
    for t in tools:
        if t.get('launched') and t['launched'] >= str(today - datetime.timedelta(days=7)):
            entries['launches'].insert(0, f"🧪 New experiment: {t['emoji']} {t['title']} ({t['url']})")
        if t.get('status') == 'graduated':
            entries['launches'].append(f"🏆 Graduated: {t['emoji']} {t['title']} → {t.get('funnel','')}")
        if t.get('status') == 'retired':
            entries['retirements'].append(f"🪦 Retired: {t['emoji']} {t['title']}")
except: pass

result = {
    'week': str(today),
    'generated': str(today),
    'entries': entries,
    'total_changes': sum(len(v) for v in entries.values()),
}

os.makedirs('data', exist_ok=True)
with open('data/changelog.json', 'w') as f:
    json.dump(result, f, indent=2)

# Markdown version
lines = [f"# Chinese Culture Lab — Week of {today}\n"]
for section, items in entries.items():
    if not items: continue
    lines.append(f"\n## {section.title()}\n")
    for item in items:
        lines.append(f"- {item}")

if result['total_changes'] == 0:
    lines.append("\n*Quiet week — experiments running in the background.*")

with open('data/changelog.md', 'w') as f:
    f.write('\n'.join(lines) + '\n')

print(f"Changelog: {result['total_changes']} entries for week of {today}")
