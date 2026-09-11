#!/usr/bin/env python3
"""
Monthly experiment archive snapshot.
Merges tools.json + metrics.json → data/experiment-archive.json
Generates an "experiment card" for each tool, preserving history.
"""
import os, json, datetime, urllib.request

BASE = 'https://raw.githubusercontent.com/daligao/year-of-goat-2027/main/data'

def fetch(path):
    with urllib.request.urlopen(f'{BASE}/{path}') as r:
        return json.loads(r.read())

try:
    tools   = fetch('tools.json')['tools']
    metrics = {m['id']: m for m in fetch('metrics.json')['tools']}
except Exception as e:
    print(f"Failed to fetch data: {e}"); exit(1)

today = str(datetime.date.today())
archive_path = 'data/experiment-archive.json'

# Load existing archive
existing = {}
if os.path.exists(archive_path):
    try:
        for entry in json.load(open(archive_path)).get('experiments', []):
            existing[entry['id']] = entry
    except: pass

experiments = []
for t in tools:
    tid = t['id']
    m = metrics.get(tid, {})
    launched = t.get('launched', '')
    duration = 0
    if launched:
        try:
            delta = datetime.date.today() - datetime.date.fromisoformat(launched)
            duration = delta.days
        except: pass

    # Preserve historical snapshots
    prev = existing.get(tid, {})
    history = prev.get('history', [])
    snapshot = {
        'date': today,
        'uv_30d': m.get('uv_30d', 0),
        'click_to_main': m.get('click_to_main', 0),
        'share_count': m.get('share_count', 0),
        'status': t.get('status', 'testing'),
    }
    # Only append if something changed
    if not history or history[-1]['status'] != snapshot['status'] or abs(history[-1]['uv_30d'] - snapshot['uv_30d']) > 10:
        history.append(snapshot)

    card = {
        'id': tid,
        'title': t.get('title', tid),
        'emoji': t.get('emoji', '🧪'),
        'url': t.get('url', ''),
        'funnel': t.get('funnel', ''),
        'hypothesis': t.get('description', ''),
        'launched': launched,
        'duration_days': duration,
        'status': t.get('status', 'testing'),
        'priority': t.get('priority', 5),
        'latest_metrics': {
            'uv_30d': m.get('uv_30d', 0),
            'click_to_main': m.get('click_to_main', 0),
            'share_count': m.get('share_count', 0),
        },
        'history': history[-12:],  # keep last 12 snapshots
        'last_updated': today,
    }
    experiments.append(card)
    print(f"  {tid}: {snapshot['status']}, {snapshot['uv_30d']} UV")

result = {
    '_note': 'Monthly experiment archive. Each experiment card tracks full lifecycle.',
    'generated': today,
    'total': len(experiments),
    'by_status': {
        s: len([e for e in experiments if e['status'] == s])
        for s in ('testing', 'growing', 'graduated', 'retired')
    },
    'experiments': experiments,
}

os.makedirs('data', exist_ok=True)
with open(archive_path, 'w') as f:
    json.dump(result, f, indent=2)

print(f"\nArchive: {len(experiments)} experiments → {archive_path}")
print(f"  by status: {result['by_status']}")
