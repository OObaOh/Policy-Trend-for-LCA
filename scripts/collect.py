#!/usr/bin/env python3
"""Conservative, source-linked carbon/LCA intelligence collector.

Direct official ministry news + government Atom + EU RSS discovery + Crossref DOIs.
Optional OpenAI API summaries are explicitly marked as preliminary analyses.
Public HTML bodies or publisher abstracts are read; only cited excerpts are archived.
"""
from __future__ import annotations

import datetime as dt
import email.utils
import hashlib
import html
import json
import os
from pathlib import Path
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

from bs4 import BeautifulSoup
from topics import tags_from, relevant, compute_priority, load_profile
from auto_brief import BRIEF_VERSION, read_source, source_extract_brief
from grounded_analysis import BRIEF_SCHEMA, INSTRUCTION, bounded_source, normalize_brief

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / 'site' / 'data' / 'articles.json'
UTC = dt.timezone.utc
TODAY = dt.datetime.now(UTC).date()
CUTOFF = TODAY - dt.timedelta(days=int(os.getenv('LOOKBACK_DAYS', '14')))
MAX_NEW = int(os.getenv('MAX_NEW_ITEMS', '60'))
RUN_HEALTH: dict[str, list[str]] = {'ok': [], 'errors': []}
USER_AGENT = 'CarbonLCAIntelligenceHub/1.2 (research metadata; GitHub Pages; link to original source)'

# Broad coverage; no arbitrary cap on discovery topics on the frontend.
TECH_TERMS = ['수전해', '연료전지', '태양전지', '바이오가스', '열분해', 'carbon capture',
              'electrolysis', 'electrolyser', 'electrolyzer', 'carbon capture',
              'battery technology', 'hydrogen', 'hydrogen technology', 'hydrogen infrastructure']
RESEARCH_QUERIES = [
    'dynamic life cycle assessment', 'prospective life cycle assessment',
    'consequential life cycle assessment allocation',
    'waste management life cycle assessment', 'extended producer responsibility life cycle',
    'recycling recycled plastics product carbon footprint',
    'end of life vehicles environmental impact',
    'automotive parts product carbon footprint',
    'hydrogen well to wheel life cycle assessment',
    'hydrogen life cycle assessment', 'bioenergy avoided emissions carbon removals',
    'product environmental footprint ecodesign regulation',
    'mass balance recycling chain of custody',
]


def document_kind(title: str, category: str) -> str:
    if category == 'LCA 논문': return '논문'
    if category == '연구보고서': return '연구보고서'
    if category == '저탄소 기술': return '기술'
    if re.search(r'(act\b|regulation|directive|amendment|final rule|law\b|시행령|법률|개정안|규칙|법령|規則|法律|Gesetz|Verordnung|loi\b|décret)', title, re.I):
        return '법령·규제'
    if re.search(r'(report|study|assessment|briefing|연구보고서|실태조사|백서|보고서|Bericht|rapport)', title, re.I):
        return '연구보고서'
    return '정책·발표'


def fetch(url: str, *, timeout: int = 28, accept: str = '*/*') -> bytes:
    req = urllib.request.Request(url, headers={
        'User-Agent': USER_AGENT, 'Accept': accept,
    })
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return response.read(3_000_000)


def clean_text(value: str, length: int = 650) -> str:
    if not value:
        return ''
    soup = BeautifulSoup(html.unescape(value), 'html.parser')
    text = ' '.join(soup.get_text(' ', strip=True).split())
    return text[:length].strip()


def canonical(url: str) -> str:
    url = html.unescape((url or '').strip())
    url = re.sub(r';jsessionid=[^?&#]+', '', url, flags=re.I)
    p = urllib.parse.urlsplit(url)
    if p.scheme not in ('http', 'https') or not p.netloc:
        return ''
    pairs = urllib.parse.parse_qsl(p.query, keep_blank_values=True)
    pairs = [(k, v) for k, v in pairs if not k.lower().startswith(('utm_', 'fbclid', 'gclid'))]
    query = urllib.parse.urlencode(pairs)
    return urllib.parse.urlunsplit(('https', p.netloc.lower(), p.path, query, ''))


def stable_id(url: str) -> str:
    return hashlib.sha256(url.encode('utf-8')).hexdigest()[:14]


def date_of(value: str) -> str:
    if not value:
        return ''
    value = value.strip()
    try:
        match = re.search(r'(20\d{2})[-./](\d{1,2})[-./](\d{1,2})', value)
        if match:
            return dt.date(*map(int, match.groups())).isoformat()
        return email.utils.parsedate_to_datetime(value).date().isoformat()
    except (ValueError, TypeError, OverflowError):
        try:
            return dt.datetime.fromisoformat(value.replace('Z', '+00:00')).date().isoformat()
        except ValueError:
            return ''


def article(*, url: str, title: str, date: str, source: str, region: str,
            category: str, snippet: str = '', doi: str = '', verification: str = '공식 출처') -> dict | None:
    link = canonical(url)
    title = clean_text(title, 260)
    when = date_of(date)
    if not link or not title or not when or when < CUTOFF.isoformat() or when > TODAY.isoformat():
        return None
    if not relevant(title + ' ' + snippet):
        return None
    # Separate technology-oriented entries, without hiding their country and original source.
    if category != 'LCA 논문' and any(t in title.lower() for t in TECH_TERMS):
        category = '저탄소 기술'
    return {
        'id': stable_id(link), 'date': when, 'category': category,
        'region': region, 'title': title, 'source': source, 'url': link,
        'doi': doi, 'tags': tags_from(title + ' ' + snippet, title=title),
        'document_type': document_kind(title, category),
        'link_status': '원문 링크 제공 · 접근 여부 미검증',
        'summary': '', 'insight': '', 'source_excerpt': clean_text(snippet, 550),
        'review_status': '서지·원문 링크 확인' if doi else '원문 검토 필요',
        'verification': verification,
    }


def discover_mcee() -> list[dict]:
    """Read MCEE official Korean press release listing (currently 10 per page)."""
    url = 'https://mcee.go.kr/m/mob/index.do?menuId=156'
    soup = BeautifulSoup(fetch(url).decode('utf-8', errors='replace'), 'html.parser')
    RUN_HEALTH['ok'].append('기후에너지환경부')
    result = []
    for a in soup.select('a[href]'):
        href = a.get('href', '')
        if 'board/read.do' not in href or 'boardId=' not in href:
            continue
        if 'boardMasterId=939' not in href and 'boardMasterId%3D939' not in href:
            continue
        text = ' '.join(a.stripped_strings)
        date = date_of(text)
        # Official mobile list uses "제목{title} 게시자{name} 작성일{date}".
        title = re.sub(r'^제목\s*', '', text)
        title = re.split(r'게시자\s*|작성일\s*', title)[0].strip()
        item = article(url=urllib.parse.urljoin(url, href), title=title, date=date,
                       source='기후에너지환경부', region='한국', category='국내 정책',
                       verification='정부 공식 보도자료')
        if item:
            result.append(item)
    return result



def discover_unfccc() -> list[dict]:
    """Scrape dated titles from UNFCCC's public official news listing."""
    base = 'https://unfccc.int/news'
    soup = BeautifulSoup(fetch(base).decode('utf-8', errors='replace'), 'html.parser')
    RUN_HEALTH['ok'].append('UNFCCC')
    records = []
    month = r'(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)'
    date_pattern = re.compile(r'\b(\d{1,2}\s+' + month + r'\s+20\d{2})\b', re.I)
    for a in soup.select('a[href]'):
        href = urllib.parse.urljoin(base, a.get('href', ''))
        parsed = urllib.parse.urlsplit(href)
        if parsed.netloc not in ('unfccc.int', 'www.unfccc.int') or not parsed.path.startswith('/news/'):
            continue
        title = clean_text(a.get_text(' ', strip=True), 270)
        title = date_pattern.sub('', title, count=1).strip(' -–|')
        if len(title) < 12:
            continue
        day = ''
        parent = a
        for _ in range(4):
            text = parent.get_text(' ', strip=True)
            match = date_pattern.search(text)
            if match:
                try:
                    day = dt.datetime.strptime(match.group(1), '%d %b %Y').date().isoformat()
                except ValueError:
                    try:
                        day = dt.datetime.strptime(match.group(1), '%d %B %Y').date().isoformat()
                    except ValueError:
                        pass
                if day:
                    break
            if parent.parent is None:
                break
            parent = parent.parent
        item = article(url=href, title=title, date=day, source='UNFCCC',
                       region='UN', category='국제 정책', verification='UNFCCC 공식 뉴스')
        if item:
            records.append(item)
    return records

def local_name(element: ET.Element) -> str:
    return element.tag.split('}')[-1]


def child_text(parent: ET.Element, name: str) -> str:
    for child in parent:
        if local_name(child) == name:
            return ''.join(child.itertext()).strip()
    return ''


def parse_syndication(body: bytes, *, source: str, region: str, category: str) -> list[dict]:
    """RSS 2.0 and Atom support with official-article URLs only."""
    root = ET.fromstring(body)
    entries = [e for e in root.iter() if local_name(e) in ('item', 'entry')]
    found = []
    for item in entries:
        title = child_text(item, 'title')
        date = (child_text(item, 'published') or child_text(item, 'pubDate')
                or child_text(item, 'updated') or child_text(item, 'date'))
        url = child_text(item, 'link')
        if not url:
            for link in item:
                if local_name(link) == 'link' and link.attrib.get('href') and link.attrib.get('rel', 'alternate') == 'alternate':
                    url = link.attrib['href']
                    break
        snippet = child_text(item, 'summary') or child_text(item, 'description') or child_text(item, 'content')
        rec = article(url=url, title=title, date=date, source=source, region=region,
                      category=category, snippet=snippet, verification='기관 공식 피드')
        if rec:
            found.append(rec)
    return found


def official_feeds() -> list[dict]:
    sources = [
        ('영국 에너지안보·넷제로부 (DESNZ)', '영국',
         'https://www.gov.uk/government/organisations/department-for-energy-security-and-net-zero.atom'),
        ('영국 환경식품농촌부 (Defra)', '영국',
         'https://www.gov.uk/government/organisations/department-for-environment-food-rural-affairs.atom'),
    ]
    found = []
    for label, region, url in sources:
        try:
            found += parse_syndication(fetch(url), source=label, region=region, category='국제 정책')
            RUN_HEALTH['ok'].append(label)
            print('OK feed:', label)
        except Exception as exc:
            RUN_HEALTH['errors'].append(label)
            print('WARN feed', label, type(exc).__name__, str(exc)[:150])
    return found


def eu_feeds() -> list[dict]:
    # Discover live RSS URLs via the Commission's own link, rather than guessing URLs.
    pages = [
        ('EU 집행위원회 환경총국', 'https://environment.ec.europa.eu/news_en', None),
        ('EU 집행위원회 통상총국', 'https://policy.trade.ec.europa.eu/news_en', None),
        ('EU 집행위원회 역내시장·산업총국', 'https://single-market-economy.ec.europa.eu/rss_en', 'News'),
    ]
    found = []
    for label, page, selected in pages:
        try:
            soup = BeautifulSoup(fetch(page).decode('utf-8', errors='replace'), 'html.parser')
            anchors = soup.select('a[href]')
            links = []
            if selected:
                links = [a.get('href', '') for a in anchors if a.get_text(' ', strip=True) == selected]
            else:
                links = [a.get('href', '') for a in anchors if a.get_text(' ', strip=True).upper() == 'RSS']
                if not links:
                    links = [a.get('href', '') for a in soup.select('link[type="application/rss+xml"]')]
            if not links:
                raise ValueError('No RSS link visible')
            rss = urllib.parse.urljoin(page, links[0])
            found += parse_syndication(fetch(rss), source=label, region='EU', category='국제 정책')
            RUN_HEALTH['ok'].append(label)
            print('OK feed:', label)
        except Exception as exc:
            RUN_HEALTH['errors'].append(label)
            print('WARN feed', label, type(exc).__name__, str(exc)[:150])
    return found




def federal_register() -> list[dict]:
    """US Federal Register API gives canonical individual rule/proposed-rule URLs."""
    queries = ['waste recycling', 'vehicle emissions', 'carbon footprint']
    entries = []
    for term in queries:
        args = urllib.parse.urlencode({
            'conditions[term]': term, 'conditions[publication_date][gte]': CUTOFF.isoformat(),
            'per_page': 25, 'order': 'newest',
        })
        try:
            payload = json.loads(fetch('https://www.federalregister.gov/api/v1/documents.json?' + args).decode('utf-8'))
            for doc in payload.get('results', []):
                link = doc.get('html_url') or ''
                item = article(url=link, title=doc.get('title', ''), date=doc.get('publication_date', ''),
                    source='미국 Federal Register', region='미국', category='국제 정책',
                    snippet=doc.get('abstract', '') or '', verification='미국 연방 관보 공식 기록')
                if item:
                    item['document_type'] = '법령·규제' if doc.get('type') in ('Rule', 'Proposed Rule') else '정부 공고'
                    item['regulatory_status'] = doc.get('type') or '문서유형 미확인'
                    entries.append(item)
            RUN_HEALTH['ok'].append('미국 Federal Register · ' + term)
        except Exception as exc:
            RUN_HEALTH['errors'].append('미국 Federal Register · ' + term)
            print('WARN Federal Register', term, type(exc).__name__, str(exc)[:120])
    return entries


def japan_environment() -> list[dict]:
    """Japan MOE official press list: publish date is read from the preceding date heading."""
    url = 'https://www.env.go.jp/press/'
    soup = BeautifulSoup(fetch(url).decode('utf-8', errors='replace'), 'html.parser')
    results = []
    day = ''
    for tag in soup.find_all(['h2', 'h3', 'h4', 'dt', 'a']):
        text = tag.get_text(' ', strip=True)
        match = re.search(r'(20\d{2})年(\d{1,2})月(\d{1,2})日', text)
        if match and tag.name != 'a':
            try: day = dt.date(*map(int, match.groups())).isoformat()
            except ValueError: day = ''
        if tag.name != 'a' or not day:
            continue
        link = urllib.parse.urljoin(url, tag.get('href', ''))
        if not link.startswith('https://www.env.go.jp/press/') or link.rstrip('/') == url.rstrip('/'):
            continue
        if len(text) < 15:
            continue
        item = article(url=link, title=text, date=day, source='일본 환경성', region='일본',
                      category='국제 정책', verification='일본 환경성 공식 보도자료')
        if item: results.append(item)
    RUN_HEALTH['ok'].append('일본 환경성')
    return results


def discover_rss_link(page: str, *, domain: str) -> str:
    """Find a real institution-published feed, never synthesize feed addresses."""
    soup = BeautifulSoup(fetch(page).decode('utf-8', errors='replace'), 'html.parser')
    for anchor in soup.select('a[href],link[rel="alternate"]'):
        value = anchor.get('href', '')
        link = urllib.parse.urljoin(page, value)
        if urllib.parse.urlsplit(link).netloc.endswith(domain) and re.search(r'(rss|feed|\.xml)', value, re.I) and link != page:
            return link
    raise ValueError('No official linked feed found')


def germany_environment() -> list[dict]:
    page = 'https://www.bundesumweltministerium.de/service/hilfe-und-nutzungshinweise/rss-newsfeed'
    url = discover_rss_link(page, domain='bundesumweltministerium.de')
    data = parse_syndication(fetch(url), source='독일 연방환경부(BMUKN)', region='독일', category='국제 정책')
    RUN_HEALTH['ok'].append('독일 연방환경부')
    return data


def france_environment() -> list[dict]:
    """Best-effort official ministry newsroom. If dates are not unambiguous, omit."""
    url = 'https://www.ecologie.gouv.fr/actualites'
    soup = BeautifulSoup(fetch(url).decode('utf-8', errors='replace'), 'html.parser')
    result = []
    months = {'janvier':1,'février':2,'mars':3,'avril':4,'mai':5,'juin':6,
              'juillet':7,'août':8,'septembre':9,'octobre':10,'novembre':11,'décembre':12}
    for block in soup.select('article, .views-row'):
        a = block.select_one('a[href]')
        if not a: continue
        title = clean_text(a.get_text(' ', strip=True), 260)
        date_tag = block.select_one('time[datetime]')
        date = date_of(date_tag.get('datetime', '')) if date_tag else ''
        if not date:
            m = re.search(r'\b(\d{1,2})\s+(' + '|'.join(months) + r')\s+(20\d{2})', block.get_text(' ', strip=True), re.I)
            if m:
                try: date = dt.date(int(m.group(3)), months[m.group(2).lower()], int(m.group(1))).isoformat()
                except ValueError: continue
        if not date: continue
        link = urllib.parse.urljoin(url, a.get('href', ''))
        if not urllib.parse.urlsplit(link).netloc.endswith('ecologie.gouv.fr'): continue
        item = article(url=link, title=title, date=date, source='프랑스 생태전환부',
                       region='프랑스', category='국제 정책', verification='프랑스 정부 공식 뉴스')
        if item: result.append(item)
    RUN_HEALTH['ok'].append('프랑스 생태전환부')
    return result


def check_links(entries: list[dict]) -> None:
    """Best-effort direct document page link availability; block or timeout is not 'broken'."""
    for item in entries[:min(int(os.getenv('MAX_LINK_CHECKS', '8')), 16)]:
        url = item.get('url')
        if not url: continue
        try:
            req = urllib.request.Request(url, method='HEAD', headers={'User-Agent': USER_AGENT})
            with urllib.request.urlopen(req, timeout=4) as response:
                if 200 <= response.status < 400:
                    item['link_status'] = '원문 연결 확인'
        except Exception:
            # Some official portals block HEAD or rate-limit. Do not label invalid.
            item['link_status'] = '원문 URL 제공 · 접근 여부 미검증'


def crossref_date(work: dict) -> str:
    """Prefer online/print publication; never interpret DOI registration as publication."""
    for key in ('published', 'published-online', 'published-print', 'issued'):
        parts = work.get(key, {}).get('date-parts', [])
        if parts and parts[0]:
            x = (parts[0] + [1, 1])[:3]
            try:
                return dt.date(*map(int, x)).isoformat()
            except ValueError:
                continue
    return ''


def crossref_work(work: dict) -> dict | None:
    title = clean_text((work.get('title') or [''])[0], 260)
    doi = (work.get('DOI') or '').strip().lower()
    # Prefer real LCA/PCF-relevant titles, not arbitrary fuzzy-query matches.
    if not title or not doi or not (re.search(r'(life[ -]?cycle|lca\b|environmental footprint|carbon footprint|product carbon|biogenic carbon|prospective|consequential|waste management|recycling|producer responsibility|end-of-life vehicle)', title, re.I) and relevant(title)):
        return None
    if work.get('type') not in ('journal-article', 'proceedings-article', 'posted-content', 'report'):
        return None
    publisher = (work.get('container-title') or ['Crossref'])[0] or 'Crossref'
    abstract = clean_text(work.get('abstract', ''), 800)
    entry = article(url=f'https://doi.org/{urllib.parse.quote(doi, safe="/.")}',
                    title=title, date=crossref_date(work), source=publisher,
                    region='국제 학술', category='연구보고서' if work.get('type') == 'report' else 'LCA 논문', snippet=abstract, doi=doi,
                    verification='Crossref DOI 메타데이터')
    if entry:
        entry['tags'] = tags_from(title + ' ' + abstract, title=title)
    return entry


def crossref_papers() -> list[dict]:
    found = []
    seen = set()
    for query in RESEARCH_QUERIES:
        args = urllib.parse.urlencode({
            'query.bibliographic': query, 'rows': 20,
            'filter': f'from-pub-date:{CUTOFF.isoformat()}',
            'sort': 'published', 'order': 'desc',
        })
        url = 'https://api.crossref.org/works?' + args
        try:
            payload = json.loads(fetch(url, timeout=35).decode('utf-8'))
            for item in payload.get('message', {}).get('items', []):
                rec = crossref_work(item)
                if rec and rec['id'] not in seen:
                    found.append(rec)
                    seen.add(rec['id'])
            RUN_HEALTH['ok'].append('Crossref: ' + query)
            print('OK Crossref:', query)
        except Exception as exc:
            RUN_HEALTH['errors'].append('Crossref: ' + query)
            print('WARN Crossref', query, type(exc).__name__, str(exc)[:150])
    return found



def enrich_with_openai(entries: list[dict]) -> dict:
    """Optional Korean synthesis. Source extraction remains intact on any failure."""
    runtime = {'status': 'disabled_no_key', 'attempted': 0, 'accepted': 0, 'rejected': 0}
    key = os.getenv('OPENAI_API_KEY', '').strip()
    if not key:
        print('Structured briefs skipped: OPENAI_API_KEY secret not configured.')
        return runtime
    limit = max(0, min(int(os.getenv('MAX_AI_PER_RUN', '6')), 15))
    runtime['status'] = 'enabled' if limit else 'disabled_limit'
    pending = [a for a in entries if not isinstance(a.get('analysis'), dict) or
               a['analysis'].get('status') in ('source_extract', 'metadata_only')]
    pending.sort(key=lambda a: (a.get('priority_score', 0), a.get('date', '')), reverse=True)
    model = os.getenv('OPENAI_MODEL', 'gpt-4.1-mini')
    today = dt.datetime.now(UTC).date().isoformat()
    for a in pending[:limit]:
        source = read_source(a, fetcher=fetch)
        if not source or source['coverage'] == 'preview':
            # Do not synthesize deep analyses from a title or a feed preview.
            print('Structured brief insufficient source:', a.get('id'))
            continue
        source = bounded_source(source)
        if sum(len(e['quote']) for e in source['evidence']) < 100:
            continue
        ctx = {k: a.get(k) for k in ('title', 'date', 'source', 'region', 'category', 'doi')}
        ctx.update({'evidence_basis': source['evidence_basis'], 'coverage': source['coverage'],
                    'source_paragraphs': source['evidence']})
        payload = {
            'model': model, 'temperature': 0.1, 'max_completion_tokens': 5000,
            'response_format': {'type': 'json_schema', 'json_schema': {
                'name': 'grounded_lca_brief', 'strict': True, 'schema': BRIEF_SCHEMA}},
            'messages': [{'role': 'system', 'content': INSTRUCTION},
                         {'role': 'user', 'content': json.dumps(ctx, ensure_ascii=False)}],
        }
        req = urllib.request.Request('https://api.openai.com/v1/chat/completions',
            data=json.dumps(payload, ensure_ascii=False).encode('utf-8'),
            headers={'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json',
                     'User-Agent': USER_AGENT}, method='POST')
        runtime['attempted'] += 1
        try:
            with urllib.request.urlopen(req, timeout=55) as response:
                api = json.load(response)
            choice = api['choices'][0]
            if choice.get('finish_reason') != 'stop' or choice.get('message', {}).get('refusal'):
                raise ValueError('incomplete or refused AI response')
            content = normalize_brief(json.loads(choice['message']['content']), source,
                                      generated_at=today, model=model)
            a['analysis'] = content
            a['review_status'] = 'AI 한국어 예비 분석 · 인용 검사 통과 · 의미 검토 필요'
            a['summary'] = clean_text(content['key_takeaways'][0], 450)
            a['insight'] = ''  # research hypotheses belong in the labeled report section
            runtime['accepted'] += 1
            print('OK grounded brief:', a.get('id'))
        except urllib.error.HTTPError as err:
            runtime['rejected'] += 1
            print('WARN AI API HTTP:', err.code, 'item:', a.get('id'))
            if err.code in (401, 403, 429):
                runtime['status'] = 'blocked_api_error'
                break
        except (ValueError, KeyError, TypeError, IndexError, urllib.error.URLError, TimeoutError, OSError) as err:
            runtime['rejected'] += 1
            # Never print raw model text, HTTP bodies, credentials or source instructions.
            print('WARN AI report rejected:', a.get('id'), type(err).__name__)
    print('Structured briefs:', json.dumps(runtime))
    return runtime


def retry_due(value: str, today: dt.date) -> bool:
    try:
        return (today - dt.date.fromisoformat(value)).days >= 3
    except (TypeError, ValueError):
        return True


def enrich_from_official_sources(entries: list[dict]) -> None:
    """Proactively read accessible official pages and scholarly abstracts.

    This extraction works without an API key and avoids an empty detail page.
    AI reports may later replace source_extract briefs. The page displays this
    provisional nature clearly so excerpts cannot masquerade as verified research.
    """
    max_items = max(0, min(int(os.getenv("MAX_SOURCE_READ_PER_RUN", "12")), 35))
    if not max_items:
        return
    today = dt.datetime.now(UTC).date()
    pending = [a for a in entries
               if (not isinstance(a.get("analysis"), dict)
                   or a["analysis"].get("status") == "metadata_only"
                   or (a["analysis"].get("status") == "source_extract"
                       and a["analysis"].get("analysis_version", 0) < BRIEF_VERSION))
               and (not a.get("source_last_attempt")
                    or a.get("source_attempt_version", 0) < BRIEF_VERSION
                    or retry_due(a["source_last_attempt"], today))]
    pending.sort(key=lambda a: (a.get("priority_score", 0), a.get("date", "")), reverse=True)
    attempted = success = 0
    for item in pending[:max_items]:
        attempted += 1
        item["source_last_attempt"] = today.isoformat()
        item["source_attempt_version"] = BRIEF_VERSION
        try:
            result = source_extract_brief(item, fetcher=fetch)
            if not result:
                print("Source not extractable:", item.get("id"))
                continue
            item["analysis"] = result
            item["review_status"] = "원문 구절 분류 · 한국어 심층 분석 미실행"
            success += 1
        except Exception as err:
            print("WARN source extraction:", item.get("id"), type(err).__name__)
    print("Source briefs:", success, "of", attempted)


def load_existing() -> list[dict]:
    if not DATA_PATH.exists():
        return []
    obj = json.loads(DATA_PATH.read_text(encoding='utf-8'))
    return obj.get('articles', []) if isinstance(obj, dict) else obj


def collect() -> dict:
    RUN_HEALTH['ok'].clear()
    RUN_HEALTH['errors'].clear()
    old = load_existing()
    existing = {v.get('id') or stable_id(v['url']) for v in old}
    candidates = []
    for name, fn in [('MCEE', discover_mcee), ('UNFCCC', discover_unfccc), ('Government Atom', official_feeds),
                     ('European Commission', eu_feeds), ('United States', federal_register),
                     ('Japan', japan_environment), ('Germany', germany_environment),
                     ('France', france_environment), ('Crossref', crossref_papers)]:
        try:
            res = fn()
            print(name + ':', len(res), 'relevant metadata items')
            candidates.extend(res)
        except Exception as exc:
            RUN_HEALTH['errors'].append(name)
            print('WARN source', name, type(exc).__name__, str(exc)[:150])
    unique = {}
    for a in candidates:
        if a['id'] not in existing:
            unique[a['id']] = a
    profile = load_profile()
    for item in list(unique.values()) + old:
        # Recompute priorities when new personal-interest settings are committed.
        item.update(compute_priority(item, profile=profile))
        item['document_type'] = item.get('document_type') or document_kind(item.get('title', ''), item.get('category', ''))
        item['tags'] = list(dict.fromkeys((item.get('tags') or []) + tags_from(item.get('title', '') + ' ' + item.get('source_excerpt', ''), title=item.get('title', ''))))[:14]
    new = sorted(unique.values(), key=lambda x: (x.get('priority_score', 0), x['date']), reverse=True)[:MAX_NEW]
    check_links(new)
    merged = sorted(old + new, key=lambda x: (x.get('date', ''), x.get('id', '')), reverse=True)
    enrich_from_official_sources(merged)
    ai_runtime = enrich_with_openai(merged)
    result = {
        'updated_at': dt.datetime.now(UTC).replace(microsecond=0).isoformat(),
        'collector': 'GitHub Actions / official government sources + Crossref',
        'profile_version': profile.get('profile_version'),
        'new_items': len(new),
        'source_health': RUN_HEALTH.copy(),
        'analysis_runtime': {'brief_version': BRIEF_VERSION, 'ai': ai_runtime},
        'articles': merged,
    }
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    DATA_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('Archived:', len(merged), 'new:', len(new))
    return result


if __name__ == '__main__':
    try:
        collect()
    except Exception as err:
        print('ERROR:', type(err).__name__, str(err)[:250], file=sys.stderr)
        sys.exit(1)
