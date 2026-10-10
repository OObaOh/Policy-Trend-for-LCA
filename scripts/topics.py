"""Topic taxonomy, emerging-keyword extraction and personal reading relevance.

The public priority score is a configurable *research fit* score, not a legal,
political or scientific quality judgment. Only source title / metadata / short
published excerpts are matched; nothing privately syncs from ChatGPT.
"""
from __future__ import annotations

import json
from pathlib import Path
import re

PROFILE_PATH = Path(__file__).resolve().parents[1] / 'config' / 'interests.json'

# (display label, evidence aliases). Domain coverage is not limited to these:
# new uppercase acronyms and statute / treatment phrases can appear as tags.
TOPIC_ALIASES = {
    'Dynamic LCA': ['dynamic lca', 'dynamic life cycle', 'time-explicit lca', 'temporal lca', '시간적 전과정평가', '동적 lca', '동적 전과정'],
    'Prospective LCA': ['prospective lca', 'prospective life cycle', '전망적 lca', '미래 시나리오 lca'],
    'Consequential LCA': ['consequential lca', 'consequential life cycle', '결과적 lca', 'consequential assessment'],
    '할당·시스템경계': ['allocation', 'system expansion', 'system boundary', 'system boundaries', 'cut-off model', 'recycled content method', '할당', '시스템경계', '경계 설정'],
    '회피배출·탄소제거': ['avoided emission', 'avoided emissions', 'carbon removal', 'carbon dioxide removal', 'carbon credit', 'removals accounting', '회피배출', '탄소제거', '탄소 크레딧'],
    'Biogenic Carbon': ['biogenic carbon', 'biogenic co2', 'biomass carbon', '바이오탄소', '생물기원 탄소', 'biogenic'],
    '데이터 품질·DQR': ['data quality rating', 'data quality assessment', 'data quality requirements', 'data quality', 'dqr', 'dqa', '데이터 품질', '데이터품질'],
    'WTW·연비': ['well to wheel', 'well-to-wheel', 'well to tank', 'well-to-tank', 'tank to wheel', 'tank-to-wheel', 'real-world fuel', 'wtt', 'ttw', 'wtw', 'well-to-wake', '실연비', '공인연비'],
    '자동차 LCA': ['automotive lca', 'vehicle life cycle', 'vehicle lifecycle', 'a-lca', 'automotive footprint', '자동차 lca', '자동차 전과정', '차량 전과정', '차량 lca'],
    '자동차부품 PCF': ['automotive parts', 'automotive components', 'automotive suppliers', 'auto parts', '부품 탄소발자국', '자동차부품', '자동차 부품', '부품사 lca'],
    'Catena-X·PDS': ['catena-x', 'product data sheet', 'pds', 'product data standard', 'product data exchange', 'catena x'],
    'CoC·Mass Balance': ['chain of custody', 'mass balance', 'mass-balance', 'recycled content traceability', 'coc', '원료 추적성', '공급망 추적성', '질량수지', '관리연속성'],
    'CFP·PCF 산정': ['product carbon footprint', 'carbon footprint of product', 'cfp', 'pcf', 'iso 14067', '제품탄소발자국', '제품 탄소발자국', '탄소발자국 산정', 'carbon intensity'],
    'CBAM': ['cbam', 'carbon border adjustment', '탄소국경조정'],
    'ESPR·DPP': ['espr', 'ecodesign for sustainable products', 'digital product passport', 'dpp', '에코디자인 규정', '디지털 제품여권', '디지털제품여권'],
    'EPR': ['extended producer responsibility', 'producer responsibility', 'producer-responsibility', 'epr', '생산자책임재활용', '생산자책임', '생산자 책임'],
    'ELV·폐자동차': ['end-of-life vehicle', 'end of life vehicle', 'end of life vehicles', 'elv', '폐자동차', '폐차 재활용', '폐차 처리'],
    'PPWR·포장재': ['ppwr', 'packaging and packaging waste', 'packaging waste', 'packaging regulation', '포장재 폐기물', '포장폐기물', '포장재 규제'],
    '폐기물관리·처리': ['waste management', 'waste treatment', 'waste disposal', 'waste framework', 'waste shipment', 'industrial waste', 'municipal waste', 'landfill', 'incineration', 'waste-to-energy', '폐기물 관리', '폐기물처리', '폐기물 처리', '폐기물관리', '매립', '소각', '폐기물관리법', '폐기물관리 법', '废弃物', '廃棄物', 'Abfall', 'déchet', 'déchets'],
    '순환경제·재활용': ['circular economy', 'circularity', 'recycling', 'recycled', 'recyclability', 'resource circulation', '순환경제', '자원순환', '재활용', '재생원료', '재자원화', '再資源化', 'Kreislaufwirtschaft', 'recyclage'],
    '플라스틱·재생원료': ['plastic', 'polymer recycling', 'recycled plastics', 'r-pet', 'rpet', 'pet recycling', '플라스틱', '재생플라스틱', '재생 플라스틱', '폐플라스틱', '再生プラスチック'],
    '수소도시': ['hydrogen city', 'hydrogen cities', '수소도시', '수소 도시', '수소 건물'],
    '수소버스·수소철도': ['hydrogen bus', 'hydrogen buses', 'fuel cell bus', 'hydrogen rail', 'hydrogen tram', '수소버스', '수소 버스', '수소철도', '수소트램', '수소열차'],
    '수소 생산·공급': ['hydrogen production', 'clean hydrogen', 'green hydrogen', 'electrolysis', 'electrolyser', 'electrolyzer', 'hydrogen leakage', 'hydrogen supply', '수전해', '청정수소', '수소 생산', '수소 공급', '수소 누출'],
    '전력믹스·시간매칭': ['electricity mix', 'electricity matching', 'hourly matching', 'temporal matching', 'grid mix', 'renewable electricity matching', '전력믹스', '시간 매칭', '시간매칭', '계통전력', '배출계수'],
    'LCI·EF·PCR': ['life cycle inventory', 'lci database', 'lci db', 'environmental footprint', 'ef 3.1', 'pcr', 'epd', 'environmental product declaration', 'lci db', '전과정목록', '전과정 목록', '환경성적표지'],
    '배터리·패스포트': ['battery passport', 'battery regulation', 'battery recycling', '배터리 여권', '배터리 재활용', '폐배터리'],
    '탄소배출권·GHG': ['greenhouse gas', 'ghg protocol', 'emissions trading', 'ets', 'ndc', 'net zero', '탄소중립', '온실가스', '배출권', '탄소시장', '気候変動', '温室効果'],
    '바이오에너지·유기성 폐자원': ['bioenergy', 'biogas', 'anaerobic digestion', 'organic waste', 'biomass', 'biochar', 'organic residues', '바이오가스', '바이오매스', '바이오차', '유기성폐자원', '유기성 폐자원', '유기성자원', '바이오'],
    'CCUS': ['ccus', 'ccs', 'carbon capture', 'carbon utilization', 'carbon utilisation', '탄소포집', '탄소저장'],
    'EU 폐기물법·지침': ['waste framework directive', 'wfd', 'waste shipment regulation', 'waste shipments', 'landfill directive', 'single use plastics directive', 'supd', 'waste electrical and electronic equipment', 'weee', '폐기물 기본지침', '폐기물 수출입'],
}

BASE_WORDS = ['carbon', 'climate', 'emission', 'sustainab', 'environment', 'hydrogen', 'circular', 'waste', 'recycl', 'life cycle', 'lifecycle', 'footprint', 'biogenic', 'renewable', 'clean tech', 'plastic', 'vehicle', 'mobility', 'ecodesign', 'pollution', 'bioenergy', 'lca', '재활용', '재생원료', '전과정', '탄소', '환경', '폐기물', '친환경', '온실가스', '수소', '법 개정', '법률', '바이오', '자원순환', '脱炭素', '排出量', '温室効果', '再生循環', '廃棄物', '資源循環', 'Kreislauf', 'Abfall', 'Klima', 'Emissions', 'déchet', 'recyclage', 'carbone', 'empreinte environnementale']
STOP_ACRONYMS = {'THE', 'AND', 'FOR', 'WITH', 'IN', 'EU', 'USA', 'UK', 'GHG', 'CO2', 'PDF', 'NEWS', 'RSS', 'JOURNAL', 'OPEN', 'UN', 'MCEE', 'EPA', 'EEA', 'GOV', 'HTML', 'RESEARCH'}


def matches(text: str, term: str) -> bool:
    """Boundary check for abbreviated Latin terms; substring check otherwise."""
    src = (text or '').casefold()
    needle = term.casefold()
    if not needle:
        return False
    if needle[0].isascii() and needle[0].isalnum() and len(needle) < 6 and re.fullmatch(r'[a-z\d-]+', needle):
        return bool(re.search(r'(?<![a-z0-9])' + re.escape(needle) + r'(?![a-z0-9])', src))
    return needle in src


def topic_labels(text: str) -> list[str]:
    return [name for name, aliases in TOPIC_ALIASES.items() if any(matches(text, alias) for alias in aliases)]


def relevant(text: str) -> bool:
    return bool(topic_labels(text)) or any(word.casefold() in (text or '').casefold() for word in BASE_WORDS)


def emerging_tags(title: str) -> list[str]:
    """Emerging regulation acronyms and meaningful named phrases in new titles."""
    tags = []
    for acronym in re.findall(r'(?<![A-Za-z0-9])[A-Z][A-Z0-9-]{2,10}(?![A-Za-z0-9])', title or ''):
        if acronym not in STOP_ACRONYMS and not acronym.isdigit():
            tags.append(acronym)
    # New Korean law/regulation names beyond our current fixed taxonomy.
    for phrase in re.findall(r'[가-힣]{2,12}(?:관리법|촉진법|기본법|시행령|규정|지침|처리법|제도)', title or ''):
        tags.append(phrase)
    return tags


def tags_from(text: str, *, title: str = '') -> list[str]:
    known = topic_labels(text)
    dynamic = emerging_tags(title or text)
    return list(dict.fromkeys(known + dynamic))[:14]


def load_profile(path: Path = PROFILE_PATH) -> dict:
    return json.loads(path.read_text(encoding='utf-8'))


def compute_priority(item: dict, *, profile: dict | None = None) -> dict:
    """A transparent, bounded personal-interest relevance score, not an objective rating."""
    profile = profile or load_profile()
    title = item.get('title', '')
    context = ' '.join([item.get('source_excerpt', ''), item.get('summary', '')])
    scored = []
    for name, aliases in TOPIC_ALIASES.items():
        weight = profile.get('weights', {}).get(name, 0)
        if not weight:
            continue
        if any(matches(title, alias) for alias in aliases):
            scored.append((weight * 4, name))
        elif context and any(matches(context, alias) for alias in aliases):
            scored.append((weight * 2, name))
    scored.sort(reverse=True)
    score = min(100, sum(points for points, _ in scored[:4]))
    if scored and re.search(r'(시행|개정|공포|강화|의무화|개편|발효|확정|enters? into force|apply|applies|regulation|amendment|revis|mandatory|directive)', title, re.I):
        score = min(100, score + 3)
    level = '필독' if score >= 24 else ('우선 검토' if score >= 12 else '참고')
    return {
        'priority_score': score,
        'priority': level,
        'priority_reasons': [name for _, name in scored[:3]],
        'priority_basis': '개인 관심주제와 공개 제목·발췌문의 키워드 일치',
    }
