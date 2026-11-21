"""Real MCEE regression plus adversarial model responses. Entirely offline."""
import copy
import io
import json
from pathlib import Path
import sys
import urllib.error

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import collect
from auto_brief import (BRIEF_VERSION, extract_paragraphs, read_source,
                        research_ideas, source_extract_brief)
from grounded_analysis import normalize_brief, bounded_source, SCALARS

FIXTURES = Path(__file__).parent / 'fixtures'


@pytest.fixture
def record():
    return json.loads((FIXTURES / 'waste_energy_20261014_before.json').read_text())


@pytest.fixture
def page():
    return (FIXTURES / 'waste_energy_20261014.html').read_bytes()


def test_real_case_removes_file_names_footnotes_and_promo(record, page):
    before = record['analysis']
    assert '.hwpx' in before['key_takeaways'][0]  # captured production failure
    brief = source_extract_brief(record, fetcher=lambda *a, **k: page)
    joined = ' '.join(brief['key_takeaways'] + brief['main_points'])
    assert all(word not in joined for word in ('첨부파일', '.hwpx', '.pdf', 'www.icipec.org'))
    assert all('500여' not in line for line in brief['key_takeaways'])
    assert all(word in ' '.join(brief['key_takeaways']) for word in ('가연성', '유기성', '환경안전성'))
    assert brief['analysis_version'] == BRIEF_VERSION
    assert '직매립' in brief['background'] and '바이오가스 생산목표제' in brief['background']
    assert '논의할 예정' in brief['purpose']
    assert '향후 관련 연구를 지속할 계획' in brief['conclusion']
    assert '감축효과를 검증' not in brief['conclusion']


def test_every_extracted_field_and_question_has_recoverable_evidence(record, page):
    brief = source_extract_brief(record, fetcher=lambda *a, **k: page)
    rows = {row['id']: row for row in brief['evidence']}
    paragraphs = extract_paragraphs(page)
    for path, ids in brief['field_evidence'].items():
        if '.' in path:
            field, index = path.split('.')
            value = brief[field][int(index)]
        else:
            value = brief[path]
        assert value == '\n'.join(rows[i]['quote'] for i in ids)
        assert all(rows[i]['quote'] in paragraphs for i in ids)
        assert all(rows[i]['url'] == record['url'] for i in ids)
    idea = brief['research_ideas'][0]
    assert idea['origin'] == 'rule_based_hypothesis'
    assert all(i in rows for i in idea['evidence_ids'])
    assert all(t in idea['research_question'] for t in idea['source_terms'])
    assert '신규성 미검증' in idea['novelty']
    assert brief['template_suggestions'][0]['origin'] == 'topic_template'
    assert brief['template_suggestions'][0]['title'] == record['analysis']['research_ideas'][0]['title']


def test_title_alone_or_unrelated_body_never_generates_waste_question(record):
    assert research_ideas(record) == []
    evidence = [{'id': 'p1', 'quote': '해당 자료는 자동차부품 관련 전과정평가 데이터를 다루는 연구입니다.'}]
    assert research_ideas(record, evidence) == []


def test_document_root_wins_over_attachment_and_navigation(page):
    body = page.replace(b'<main ', b'<nav><p>' + ('폐기물 탄소중립 메뉴 목록 ' * 20).encode() + b'</p></nav><main ')
    paragraphs = extract_paragraphs(body)
    assert all('메뉴 목록' not in p and '첨부파일' not in p for p in paragraphs)


@pytest.mark.parametrize('body', [
    '<html><head><title>Access denied</title></head><body><p>' + 'Waste energy unavailable. ' * 20 + '</p></body></html>',
    '<main><p>첨부파일 폐기물에너지화_보도자료.pdf(421 KB)</p></main>',
    '<main><p>내용이 짧습니다.</p></main>',
])
def test_unavailable_pages_do_not_become_reports(record, body):
    assert source_extract_brief(record, fetcher=lambda *a, **k: body.encode()) is None


def test_preview_does_not_fill_missing_document_sections(record):
    record['source_excerpt'] = '가연성 및 유기성 폐기물의 에너지화 기술을 논의하는 토론회에 관한 간략 미리보기이며 ' * 3
    brief = source_extract_brief(record, fetcher=lambda *a, **k: b'<html></html>')
    assert brief['source_provenance']['coverage'] == 'preview'
    assert brief['background'] == brief['purpose'] == brief['conclusion'] == ''
    assert brief['research_ideas'] == []


def test_crossref_abstract_is_labeled_and_has_publisher_api_provenance():
    rec = {'doi': '10.1000/example', 'title': 'Test LCA paper', 'url': 'https://doi.org/10.1000/example'}
    abstract = '<p>We compare waste treatment allocation methods using life cycle assessment.</p><p>Results depend on energy substitution assumptions and the selected system boundary.</p>'
    source = read_source(rec, fetcher=lambda *a, **k: json.dumps({'message': {'abstract': abstract}}).encode())
    assert source['coverage'] == 'abstract'
    assert source['source_url'] == 'https://api.crossref.org/works/10.1000/example'


def test_migration_refreshes_legacy_and_preserves_editorial_and_ai(monkeypatch, record, page):
    editorial = {**copy.deepcopy(record), 'id': 'editorial', 'analysis': {'status': 'editorial_preliminary', 'background': '기존 검토'}}
    ai = {**copy.deepcopy(record), 'id': 'ai', 'analysis': {'status': 'ai_preliminary', 'background': '기존 분석'}}
    old = copy.deepcopy(record)
    entries = [record, editorial, ai]
    monkeypatch.setattr(collect, 'fetch', lambda *a, **k: page)
    collect.enrich_from_official_sources(entries)
    assert record['analysis']['analysis_version'] == BRIEF_VERSION
    for k, v in old.items():
        if k not in ('analysis', 'source_last_attempt', 'review_status'):
            assert record[k] == v
    assert editorial['analysis']['background'] == '기존 검토'
    assert ai['analysis']['background'] == '기존 분석'


def test_failed_upgrade_preserves_archive_and_obeys_retry_backoff(monkeypatch, record):
    before = copy.deepcopy(record['analysis'])
    calls = []
    def unavailable(*args, **kwargs):
        calls.append(1)
        raise TimeoutError()
    monkeypatch.setattr(collect, 'fetch', unavailable)
    collect.enrich_from_official_sources([record])
    collect.enrich_from_official_sources([record])
    assert len(calls) == 1
    assert record['analysis'] == before


def model_output(source):
    anchor = next(e['id'] for e in source['evidence'] if '가연성' in e['quote'])
    recovery = next(e['id'] for e in source['evidence'] if '환경안전성' in e['quote'])
    claim = lambda text, ids: {'text': text, 'evidence_ids': ids, 'kind': 'source_fact'}
    result = {k: claim('', []) for k in SCALARS}
    result.update({
        'purpose': claim('가연성·유기성 폐기물 에너지화 기술과 탄소중립 대응 방안을 논의할 예정이다.', [anchor]),
        'key_takeaways': [claim('가연성·유기성 폐기물 에너지화 기술을 논의할 예정이다.', [anchor])],
        'main_points': [claim('에너지·물질 회수와 환경안전성을 함께 고려한다.', [recovery])],
        'research_ideas': [{
            'title': '폐기물 에너지화 회수편익의 귀속 연구',
            'research_question': '가연성·유기성 폐기물 에너지화의 할당 규칙이 환경영향에 미치는 영향은 무엇인가?',
            'methodology': '할당 및 대체편익 민감도 분석', 'source_connection': '원문의 가연성·유기성 에너지화 논의를 산정규칙과 연결한 가설',
            'novelty': '선행연구 중복성 검토 필요', 'data': '공정 데이터 공개 여부 조사 필요',
            'evidence_ids': [anchor], 'source_terms': ['가연성', '유기성'],
        }], 'limitations': '공개 보도자료만 분석. 법령 본문 교차검증 미실행.',
    })
    return result


def test_valid_mock_ai_contract_is_cited_but_not_semantically_certified(record, page):
    source = read_source(record, fetcher=lambda *a, **k: page)
    brief = normalize_brief(model_output(source), source, generated_at='2026-10-14', model='mock-only')
    assert brief['status'] == 'ai_preliminary'
    assert brief['validation']['semantic_entailment'] == 'not_verified'
    assert brief['section_status']['conclusion'] == 'not_found'
    assert brief['research_ideas'][0]['origin'] == 'ai_source_hypothesis'


@pytest.mark.parametrize('failure', ['missing_id', 'unknown_id', 'new_number', 'english', 'generic_question', 'malformed_list', 'extra_field'])
def test_unverifiable_ai_output_is_rejected(record, page, failure):
    source = read_source(record, fetcher=lambda *a, **k: page)
    output = model_output(source)
    if failure == 'missing_id': output['purpose']['evidence_ids'] = []
    if failure == 'unknown_id': output['purpose']['evidence_ids'] = ['nonexistent']
    if failure == 'new_number': output['purpose']['text'] = '온실가스를 99.99% 감축하였다.'
    if failure == 'english': output['purpose']['text'] = 'Waste conversion is effective.'
    if failure == 'generic_question': output['research_ideas'][0]['research_question'] = '탄소정책의 정합성을 어떻게 평가하는가?'
    if failure == 'malformed_list': output['main_points'] = '문자열'
    if failure == 'extra_field': output['fabricated'] = '추가 결론'
    with pytest.raises(ValueError):
        normalize_brief(output, source, generated_at='2026-10-14', model='mock-only')


def test_no_key_makes_no_model_or_source_requests(monkeypatch, record):
    before = copy.deepcopy(record)
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    def forbidden(*a, **k): raise AssertionError('network called without key')
    monkeypatch.setattr(collect, 'read_source', forbidden)
    monkeypatch.setattr(collect.urllib.request, 'urlopen', forbidden)
    runtime = collect.enrich_with_openai([record])
    assert runtime == {'status': 'disabled_no_key', 'attempted': 0, 'accepted': 0, 'rejected': 0}
    assert record == before


@pytest.mark.parametrize('scenario', ['valid', 'refusal', 'truncated', 'bad_evidence', 'quota'])
def test_mock_api_path_and_failures_preserve_source_report(monkeypatch, record, page, scenario):
    source = read_source(record, fetcher=lambda *a, **k: page)
    record['analysis'] = source_extract_brief(record, fetcher=lambda *a, **k: page)
    before = copy.deepcopy(record['analysis'])
    monkeypatch.setenv('OPENAI_API_KEY', 'test-placeholder')
    monkeypatch.setattr(collect, 'read_source', lambda *a, **k: source)
    output = model_output(source)
    if scenario == 'bad_evidence': output['purpose']['evidence_ids'] = ['not-in-source']
    def fake_api(request, timeout):
        payload = json.loads(request.data)
        assert 'source_paragraphs' in json.loads(payload['messages'][1]['content'])
        assert timeout <= 60
        if scenario == 'quota':
            raise urllib.error.HTTPError(request.full_url, 429, 'quota', {}, None)
        return io.BytesIO(json.dumps({'choices': [{'finish_reason': 'length' if scenario == 'truncated' else 'stop',
            'message': {'content': json.dumps(output), 'refusal': 'refused' if scenario == 'refusal' else None}}]}).encode())
    monkeypatch.setattr(collect.urllib.request, 'urlopen', fake_api)
    runtime = collect.enrich_with_openai([record])
    assert runtime['attempted'] == 1
    if scenario == 'valid':
        assert runtime['accepted'] == 1 and record['analysis']['status'] == 'ai_preliminary'
    else:
        assert runtime['rejected'] == 1 and record['analysis'] == before


def test_source_budget_never_splits_a_quote(record, page):
    source = read_source(record, fetcher=lambda *a, **k: page)
    bounded = bounded_source(source, len(source['evidence'][0]['quote']) + 10)
    assert bounded['evidence'] == source['evidence'][:1]
