"""Offline collector regression tests: no internet or API key required."""
import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import collect


def test_canonical_drops_tracking_and_session():
    value = collect.canonical('http://mcee.go.kr/m/mob/board/read.do;jsessionid=abc123?boardId=100&utm_source=a&menuId=156')
    assert value == 'https://mcee.go.kr/m/mob/board/read.do?boardId=100&menuId=156'


def test_metadata_requires_real_date_and_relevance():
    rec = collect.article(url='https://example.org/notice', title='2030 탄소중립 로드맵 발표',
                          date=collect.TODAY.isoformat(), source='정부기관', region='한국',
                          category='국내 정책')
    assert rec and rec['id'] and rec['category'] == '국내 정책'
    assert collect.article(url='https://example.org/a', title='단순 인사발령',
                           date=collect.TODAY.isoformat(), source='X', region='한국', category='국내 정책') is None
    assert collect.article(url='https://example.org/b', title='탄소 감축 발표',
                           date='2040-01-01', source='X', region='한국', category='국내 정책') is None
    assert collect.article(url='javascript:alert(1)', title='탄소 감축 발표',
                           date=collect.TODAY.isoformat(), source='X', region='한국', category='국내 정책') is None


def test_feed_parses_atom_official_source():
    xml = (f'''<feed xmlns="http://www.w3.org/2005/Atom"><entry>
       <title>New carbon border adjustment rules</title><link href="https://www.gov.uk/government/news/carbon-border-rules"/>
       <published>{collect.TODAY.isoformat()}T08:00:00+00:00</published>
       <summary>Government rules for carbon reporting</summary>
       </entry></feed>''').encode()
    recs = collect.parse_syndication(xml, source='UK GOV', region='영국', category='국제 정책')
    assert len(recs) == 1
    assert recs[0]['url'].endswith('/carbon-border-rules')
    assert recs[0]['source'] == 'UK GOV'


def test_feed_parses_rss():
    xml = f'''<rss version="2.0"><channel><item><title>Hydrogen lifecycle emissions</title>
      <link>https://sample.gov/news/hydrogen</link><pubDate>{collect.TODAY.strftime('%a, %d %b %Y')} 10:00:00 GMT</pubDate>
      <description>Life cycle assessment of hydrogen systems</description></item></channel></rss>'''.encode()
    recs = collect.parse_syndication(xml, source='Official', region='EU', category='국제 정책')
    assert len(recs) == 1
    assert recs[0]['category'] == '저탄소 기술'


def test_mcee_ignores_unrelated_press_items(monkeypatch):
    page = f'''<html><body><ul>
        <li><a href="/m/mob/board/read.do?boardId=77&amp;boardMasterId=939&amp;menuId=156">제목국가 탄소배출 감소 전망 게시자 담당자 작성일{collect.TODAY.isoformat()}</a></li>
        <li><a href="/m/mob/board/read.do?boardId=78&amp;boardMasterId=939&amp;menuId=156">제목단순 회의실 안내 게시자 담당자 작성일{collect.TODAY.isoformat()}</a></li>
        </ul></body></html>'''
    monkeypatch.setattr(collect, 'fetch', lambda *_args, **_kwargs: page.encode())
    found = collect.discover_mcee()
    assert len(found) == 1
    assert found[0]['title'] == '국가 탄소배출 감소 전망'
    assert 'boardId=77' in found[0]['url']


def test_crossref_metadata_needs_research_title():
    paper = {
        'title': ['Prospective life cycle assessment of hydrogen production'],
        'DOI': '10.1234/example', 'type': 'journal-article',
        'published': {'date-parts': [[collect.TODAY.year, collect.TODAY.month, collect.TODAY.day]]},
        'container-title': ['Journal of Test Research'],
    }
    item = collect.crossref_work(paper)
    assert item and item['category'] == 'LCA 논문'
    assert item['doi'] == '10.1234/example'
    unrelated = {**paper, 'title': ['A study of unrelated social development']}
    assert collect.crossref_work(unrelated) is None


def test_duplicate_articles_are_not_readded(monkeypatch, tmp_path):
    output = tmp_path / 'articles.json'
    monkeypatch.setattr(collect, 'DATA_PATH', output)
    test_entry = collect.article(url='https://example.org/carbon-update',
        title='New carbon neutrality strategy', date=collect.TODAY.isoformat(),
        source='Test Agency', region='EU', category='국제 정책')
    assert test_entry
    monkeypatch.setattr(collect, 'discover_mcee', lambda: [test_entry])
    monkeypatch.setattr(collect, 'discover_unfccc', lambda: [test_entry])
    monkeypatch.setattr(collect, 'official_feeds', lambda: [])
    monkeypatch.setattr(collect, 'eu_feeds', lambda: [])
    monkeypatch.setattr(collect, 'crossref_papers', lambda: [])
    monkeypatch.setattr(collect, 'federal_register', lambda: [])
    monkeypatch.setattr(collect, 'japan_environment', lambda: [])
    monkeypatch.setattr(collect, 'germany_environment', lambda: [])
    monkeypatch.setattr(collect, 'france_environment', lambda: [])
    monkeypatch.setattr(collect, 'check_links', lambda _: None)
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    first = collect.collect()
    second = collect.collect()
    assert first['new_items'] == 1
    assert second['new_items'] == 0
    assert len(second['articles']) == 1
    assert json.loads(output.read_text())['articles'][0]['id'] == test_entry['id']


def test_priority_ranks_specific_research_relevance():
    from topics import compute_priority
    direct = {'title': 'Dynamic life cycle assessment of allocation in automotive parts',
              'source_excerpt': 'Product carbon footprint and Catena-X PDS', 'summary': ''}
    general = {'title': 'General climate funding announcement', 'source_excerpt': '', 'summary': ''}
    a = compute_priority(direct)
    b = compute_priority(general)
    assert a['priority'] == '필독'
    assert a['priority_score'] > b['priority_score']
    assert 'Dynamic LCA' in a['priority_reasons']


def test_new_keywords_not_limited_to_existing_research_themes():
    from topics import tags_from
    tags = tags_from('New QWER Regulation on waste management and recycling', title='New QWER Regulation on waste management')
    assert 'QWER' in tags
    assert '폐기물관리·처리' in tags


def test_japanese_press_recycling_topic_eligible():
    rec = collect.article(url='https://www.env.go.jp/press/press_05636.html',
                          title='資源循環の促進のための再資源化事業による温室効果ガス排出量の削減',
                          date=collect.TODAY.isoformat(), source='일본 환경성', region='일본',
                          category='국제 정책')
    assert rec is not None
    assert '순환경제·재활용' in rec['tags']


def test_regulatory_report_type_separation():
    rec = collect.article(url='https://www.federalregister.gov/documents/2026/10/09/example',
                          title='Final rule for industrial waste treatment regulation',
                          date=collect.TODAY.isoformat(), source='US Register', region='미국',
                          category='국제 정책')
    assert rec and rec['document_type'] == '법령·규제'


def test_existing_items_recompute_if_profile_changes(monkeypatch, tmp_path):
    output = tmp_path / 'articles.json'
    monkeypatch.setattr(collect, 'DATA_PATH', output)
    entry = collect.article(url='https://example.org/elv-news', title='New ELV producer responsibility rules',
                            date=collect.TODAY.isoformat(), source='EU', region='EU', category='국제 정책')
    assert entry
    output.write_text(json.dumps({'articles':[entry]}, ensure_ascii=False), encoding='utf-8')
    for name in ['discover_mcee', 'discover_unfccc', 'official_feeds', 'eu_feeds',
                 'federal_register', 'japan_environment', 'germany_environment',
                 'france_environment', 'crossref_papers']:
        monkeypatch.setattr(collect, name, lambda: [])
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    result = collect.collect()
    assert len(result['articles']) == 1
    assert result['articles'][0]['priority'] == '필독'
    assert result['articles'][0]['priority_reasons']


def test_auto_source_reader_extracts_official_facts_without_api_key():
    from auto_brief import source_extract_brief
    sample = {
        "id": "abc", "title": "EU automotive ELV recycled plastic targets",
        "url": "https://environment.ec.europa.eu/news/fake-test",
        "tags": ["ELV·폐자동차"], "source_excerpt": "", "doi": "",
        "category": "국제 정책", "region": "EU",
    }
    text = b"""<html><body><nav>menu</nav><main><article>
    <p>The new End-of-Life Vehicles Regulation sets obligations for vehicle design,
    recycled plastic and reprocessing of materials at the end of a vehicle's service life.</p>
    <p>Producers are expected to ensure traceability of recycled content across suppliers,
    and the rules seek to reduce dependence on virgin materials.</p>
    <p>New recovery requirements focus on better collection, dismantling and reuse
    of automotive components, with monitoring by competent authorities.</p>
    </article></main></body></html>"""
    result = source_extract_brief(sample, fetcher=lambda url, timeout: text)
    assert result["status"] == "source_extract"
    assert len(result["key_takeaways"]) >= 1
    assert result["research_ideas"] == []  # no source-specific rule for this body
    assert result["template_suggestions"][0]["origin"] == "topic_template"
    assert result["background"] == ""  # never invent motives not in evidence
    assert "직접 원문을 보라" not in result["limitations"]


def test_auto_reader_blocks_nonofficial_hosts():
    from auto_brief import source_extract_brief
    a = {"url": "https://unknown.example.org/article", "title": "Waste management",
         "source_excerpt": "", "doi": ""}
    assert source_extract_brief(a, fetcher=lambda *args, **kwargs: b"<p>text</p>") is None


def test_hydrogen_title_alone_only_selects_labeled_template():
    from auto_brief import research_ideas, template_suggestions
    record = {"title": "수소도시의 수소 생산 온실가스 배출", "tags": ["수소 생산·공급"]}
    assert research_ideas(record) == []
    value = template_suggestions(record)
    assert value[0]['origin'] == 'topic_template' and value[0]['evidence_ids'] == []
