#!/usr/bin/env python3
"""Reproduce the captured MCEE before/after comparison without network or a key."""
import json
from pathlib import Path
from auto_brief import source_extract_brief

ROOT = Path(__file__).resolve().parents[1]


def compare():
    fixtures = ROOT / 'tests' / 'fixtures'
    before = json.loads((fixtures / 'waste_energy_20261014_before.json').read_text())
    page = (fixtures / 'waste_energy_20261014.html').read_bytes()
    after = source_extract_brief(before, fetcher=lambda *a, **k: page)
    return {
        'article_id': before['id'], 'original_url': before['url'],
        'before': {k: before['analysis'].get(k) for k in
                   ('status', 'key_takeaways', 'background', 'purpose', 'conclusion', 'research_ideas')},
        'after': after,
        'execution': {'network_requests': 0, 'external_ai_requests': 0,
                      'note': 'Captured live HTML fixture. Korean model synthesis is not exercised.'},
    }


if __name__ == '__main__':
    print(json.dumps(compare(), ensure_ascii=False, indent=2))
