"""Grounded, no-key fallback for public source text.

This module does NOT claim to translate or synthesize like an LLM.
Research backlog can be triggered manually for initial archive completion. It retrieves
public body paragraphs, selects relevant statements, and builds a separately
labeled extractive brief. Original prose remains marked as excerpts.
"""
from __future__ import annotations

import re
import datetime as dt
import hashlib
import json
import urllib.parse
from bs4 import BeautifulSoup

BRIEF_VERSION = 2

OFFICIAL_DOMAINS = (
    "mcee.go.kr", "moe.go.kr", "unfccc.int", "gov.uk",
    "ec.europa.eu", "europa.eu", "federalregister.gov",
    "env.go.jp", "bundesumweltministerium.de", "ecologie.gouv.fr",
)
NOISE = re.compile(
    r"^(cookie|accept|privacy|javascript|contact|accessibility|newsletter|"
    r"published on|print page|footer|share|copyright|find out more|"
    r"back to|read more|unsubscribe|sign up|information about|"
    r"this website|follow us|to english|報道発表資料|この記事を印刷|"
    r"publication date|author|select your language)$", re.I
)
TOPIC_WORDS = {
    "ELV": ("폐자동차", "end-of-life vehicle", "automotive", "recycled plastic",
            "vehicle design", "recovery", "차량"),
    "재생원료·자원순환": ("recycl", "재생", "재활용", "資源循環",
                      "waste", "폐기물", "circular", "abfall", "recyclage"),
    "탄소·배출량": ("carbon", "온실가스", "greenhouse", "emission", "탄소",
                "co2", "emissions", "温室効果ガス", "klima"),
    "수소": ("hydrogen", "수소", "wasserstoff"),
    "자동차": ("automotive", "vehicle", "cars", "vehicles", "자동차"),
    "포장": ("packaging", "ppwr", "포장재", "pack"),
    "LCA": ("life cycle assessment", "lca", "전과정평가", "carbon footprint"),
}
IDEAS = {
    "ELV": (
        "폐자동차 규제의 재생원료 인정방식과 자동차부품 PCF 간 정합성",
        "재생원료 함량·CoC 증빙 방식이 다른 경우 자동차부품의 환경부하를 어떤 규칙으로 귀속해야 하는가?",
        "재생함량법과 cut-off·시스템 확장에 따른 할당 규칙 및 이중계상 위험 검토",
        "규제 목표와 제품단위 PCF 산정기준의 연결이라는 방법론적 연구 가설. 선행연구 검증 필요",
        "ELV 규정·PCR·재생원료 공개 통계와 소재별 LCI. 실제 공급망 물량 자료는 제약",
    ),
    "포장": (
        "포장재 재생원료 의무와 Circular Footprint Formula 간 정합성",
        "의무 재생함량과 회수·재활용 편익의 귀속을 동시에 적용할 때 이중계상을 피할 수 있는가?",
        "PEF/CFF·재생함량법·시스템 확장 비교와 재활용률·품질손실 민감도 평가",
        "포장재 적합성 지표와 PCF 결과가 충돌하는 조건 검증 가설. 중복 문헌 확인 필요",
        "PPWR 원문, 소재별 공개 LCI, 포장재 폐기물 및 재활용 통계",
    ),
    "수소": (
        "수소 공급경로의 시간적 대표성과 시스템경계가 PCF에 미치는 영향",
        "동일 수소 공급경로의 월별·시간별 전력 계수 적용이 탄소강도 및 인증경계의 일관성을 어떻게 바꾸는가?",
        "시간별 전력믹스·전력 매칭·WTW/WtG 경계 및 DQR 비교",
        "시간해상도와 인증경계의 결합 효과 검증 가설. 선행연구·제도 정합성 추가 확인",
        "KPX 전력믹스, 수전해 LCI, 공개 연료전지·수소기술 기술문헌",
    ),
    "자동차": (
        "자동차 공급망 제품단위 탄소발자국의 데이터 품질과 배분규칙 연구",
        "품목별 원재료 구성과 공정 할당·데이터 품질 차이가 자동차부품 PCF 불확실성을 얼마나 설명하는가?",
        "Catena-X·ISO 14067·DQR 요구사항 및 할당법 비교·민감도 분석",
        "제품 PCF의 데이터 출처·검증체계와 방법론의 연결을 탐색하는 가설",
        "공개 IMDS 예시, 소재별 LCI, 공급망 양식, 국가별 전력배출계수",
    ),
    "재생원료·자원순환": (
        "재자원화 환경편익 산정에서 폐기물 지위와 환경부하 귀속의 영향",
        "폐기물의 원료 전환과 대체편익 반영 범위가 정책단위 감축실적과 제품단위 PCF 간 결과를 어떻게 변화시키는가?",
        "Attributional/Consequential LCA, cut-off·할당·회피배출 규칙을 결합한 시나리오",
        "정책 효과와 제품 탄소발자국의 산정목적·경계 차이에서 발생하는 연구 가설",
        "공식 정책 문서, 공개 재활용 통계와 공정 LCI. 민간 현장 수율은 확인 필요",
    ),
    "탄소·배출량": (
        "온실가스 감축정책 지표와 LCA 환경편익 산정의 경계 정합성",
        "정책상 감축실적의 기준선과 제품 전과정 산정의 기준선 차이는 어떻게 비교가능성을 제한하는가?",
        "시스템경계·기준선·할당 및 불확실성에 관한 방법론 대조",
        "정책 지표와 제품 지표의 목적·범위 차이를 규명하는 연구 가설",
        "공개 규정·배출계수·LCI DB 및 제도 운영 자료",
    ),
}

def is_official(url: str) -> bool:
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "https":
        return False
    host = (parsed.hostname or "").lower()
    return any(host == domain or host.endswith("." + domain)
               for domain in OFFICIAL_DOMAINS)

def clean_sentence(value: str, limit: int=480) -> str:
    return " ".join(value.split())[:limit]

def is_substantive(value: str) -> bool:
    """Reject interface text and footnotes before scoring, not after selection."""
    if len(value) < 45 or sum(ch.isalpha() for ch in value) < 30:
        return False
    if NOISE.search(value):
        return False
    if re.match(r"^(?:첨부\s*파일|붙임\b|담당\s*부서|목록\s*보기|[＊*▷※])", value):
        return False
    if re.search(r"\.(?:hwpx?|pdf|docx?|xlsx?|zip)(?:\b|\()", value, re.I) and (
            re.search(r"\b(?:KB|MB|다운로드|미리보기)\b", value, re.I) or
            len(value.split()) < 8):
        return False
    return True


def extract_paragraphs(html: bytes) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.get_text(' ', strip=True) if soup.title else ''
    if re.search(r'access denied|just a moment|captcha|접근.*차단|서비스.*점검', title, re.I):
        return []
    for part in soup.select("script,style,noscript,nav,footer,header,aside,form,svg,iframe"):
        part.decompose()
    # A specific document body must precede a broad main/body container. MCEE's
    # attachment list is a sibling of .articleDetail, not part of the article.
    selectors = (".articleDetail", ".article-content", "[itemprop='articleBody']",
                 "main article","article","main",
                 ".region-content","#mainContent","#content","body")
    root = None
    for selector in selectors:
        node = soup.select_one(selector)
        if node and len(node.get_text(" ", strip=True)) >= 90:
            root = node
            break
    if root is None:
        return []
    for part in root.select('.articleInfo,.attachments,.attachment,.file-list,[download]'):
        part.decompose()
    arr = []
    seen = set()
    # Avoid nested list elements if parent text is already a paragraph.
    for p in root.select("p, h2, h3, li"):
        if p.name == "li" and p.find(["p","ul","ol"]):
            continue
        raw = ' '.join(p.get_text(" ", strip=True).split())
        # Keep complete paragraphs as citable evidence; do not cut a sentence at
        # an arbitrary character boundary or let a container swallow the body.
        if not is_substantive(raw) or len(raw) > 1800 or raw in seen:
            continue
        seen.add(raw)
        arr.append(raw)
        if len(arr) >= 120:
            break
    return arr

def choose_topic(record: dict) -> str:
    text = (record.get("title","") + " " + record.get("source_excerpt","")).casefold()
    tags = set(record.get("tags", []))
    if "ELV·폐자동차" in tags or ("elv" in text and "vehicle" in text):
        return "ELV"
    if "PPWR·포장재" in tags or "ppwr" in text or "packaging" in text:
        return "포장"
    if "수소 생산·공급" in tags or "수소도시" in tags or "수소철도·수소버스" in tags or "수소" in text or "hydrogen" in text:
        return "수소"
    if "자동차 LCA" in tags or "자동차부품 PCF" in tags:
        return "자동차"
    scored = []
    for topic, terms in TOPIC_WORDS.items():
        score = sum(2 if v.casefold() in record.get("title","").casefold()
                    else 1 for v in terms if v.casefold() in text)
        if score:
            scored.append((score, topic))
    return max(scored)[1] if scored else ""

def template_suggestions(record: dict) -> list[dict]:
    """Topic-only prompts. These are never presented as source analysis."""
    topic = choose_topic(record)
    item = IDEAS.get(topic)
    if not item:
        return []
    return [{**dict(zip(("title","research_question","methodology","novelty","data"), item)),
             "origin": "topic_template", "evidence_ids": [],
             "source_connection": "제목·태그 기반 고정 템플릿. 해당 자료에서 도출·검증한 연구 질문 아님."}]


def read_source(record: dict, *, fetcher) -> dict | None:
    """One cleaned source path shared by rule extraction and optional AI analysis."""
    url = record.get("url","")
    paragraphs: list[str] = []
    basis = ""
    coverage = ""
    source_url = url
    if record.get("doi"):
        # Only the publisher-supplied abstract, never a paywalled full text.
        try:
            doi = urllib.parse.quote(record["doi"], safe="/")
            source_url = "https://api.crossref.org/works/" + doi
            data = json.loads(fetcher(source_url, timeout=16))
            abstract = (data.get("message") or {}).get("abstract", "")
            if abstract:
                abstract = BeautifulSoup(abstract, "html.parser").get_text(" ", strip=True)
                paragraphs = [s.strip() for s in
                    re.split(r"(?<=[.!?])\s+(?=[A-Z가-힣])", abstract)
                    if is_substantive(s.strip()) and len(s) <= 1800]
                basis = "Crossref에 등록된 출판사 제공 초록 발췌"
                coverage = "abstract"
        except Exception:
            pass
    elif is_official(url):
        try:
            body = fetcher(url, timeout=17)
            paragraphs = extract_paragraphs(body)
            basis = "공식 기관 공개 웹페이지 본문 자동 발췌"
            coverage = "official_html"
        except Exception:
            pass
    preview = ' '.join((record.get("source_excerpt") or '').split())
    if not paragraphs and is_substantive(preview) and len(preview) >= 90:
        paragraphs = [preview]
        basis = "기관 공개 미리보기 발췌"
        coverage = "preview"
        source_url = url
    if not paragraphs:
        return None
    digest = hashlib.sha256('\n'.join(paragraphs).encode()).hexdigest()
    return {"evidence_basis": basis, "coverage": coverage, "source_url": source_url,
            "retrieved_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
            "content_sha256": digest,
            "evidence": [{"id": "p-" + hashlib.sha256(p.encode()).hexdigest()[:12],
                          "quote": p, "url": source_url,
                          "locator": f"정제 본문 문단 {i+1}", "coverage": coverage}
                         for i, p in enumerate(dict.fromkeys(paragraphs))]}


def research_ideas(record: dict, evidence: list[dict] | None = None) -> list[dict]:
    """Source-triggered rules, explicitly hypotheses rather than literature findings.

    At least two technical anchors must occur in actual extracted body evidence.
    No title/tag-only fallthrough to the old generic topic templates.
    """
    evidence = evidence or []
    anchors = [e for e in evidence if '가연성' in e['quote'] and
               '유기성' in e['quote'] and '에너지화' in e['quote']]
    recovery = [e for e in evidence if '물질 회수' in e['quote'] and '환경안전성' in e['quote']]
    if not anchors or not recovery:
        return []
    return [{
        "origin": "rule_based_hypothesis",
        "title": "가연성·유기성 폐기물 에너지화의 회수편익 귀속과 환경안전성 평가",
        "research_question": "가연성·유기성 폐기물의 에너지·물질 회수편익을 산정할 때 대체 에너지 기준선과 다기능 공정의 할당 선택이 기후변화 및 환경안전성 관련 영향범주의 상충관계를 어떻게 바꾸는가?",
        "methodology": "폐기물 처리 기능과 에너지·물질 생산 기능의 기능단위·시스템경계 설정, 할당/시스템 확장 및 대체 에너지 기준선에 대한 민감도 분석.",
        "source_connection": "원문의 가연성·유기성 폐기물 에너지화 논의와 에너지·물질 회수·환경안전성의 통합 검토를 연결한 규칙 기반 가설. 원문이 LCA 또는 특정 공정 성능을 검증한 것은 아님.",
        "evidence_ids": list(dict.fromkeys([anchors[0]['id'], recovery[0]['id']])),
        "source_terms": ["가연성", "유기성", "환경안전성"],
        "novelty": "신규성 미검증. 폐기물 에너지화의 다기능성·대체편익·다중 영향범주 선행연구 조사 필요.",
        "data": "이 발췌만으로 공정별 수율·배출량·LCI의 충분성을 확인하지 못함. 처리 공정, 회수 에너지·물질, 대체 계통, 배출물 자료의 공개 여부를 별도로 조사해야 함.",
    }]


def source_extract_brief(record: dict, *, fetcher, clean=None, source=None) -> dict | None:
    """No-key evidence classification; never claims to be Korean deep analysis."""
    source = source or read_source(record, fetcher=fetcher)
    if not source or sum(len(e['quote']) for e in source['evidence']) < 100:
        return None
    evidence = source['evidence']
    cues = {
        'background': r'^(최근|특히 우리나라|배경|Background\b)|\bcontext\b',
        'purpose': r'(목적|위해|이에 ).*(논의|분석|평가|검토)|^(목적|Purpose\b|Objectives?\b)|\b(?:aims? to|objective of)\b',
        'conclusion': r'향후.*계획|^(결론[ :：]|Conclusions?\b)|\bwe conclude\b',
    }
    # Preview text is too short to classify the document's rhetorical structure.
    classified = {name: [e for e in evidence if re.search(pattern, e['quote'], re.I)][:2]
                  if source['coverage'] != 'preview' else [] for name, pattern in cues.items()}
    def score(e):
        value = e['quote'].casefold()
        technical = ('에너지화', '유기성', '가연성', '환경안전성', '회수', '목표제', '직매립',
                     'allocation', 'life cycle', 'recycl', 'emission', '시행', '의무', 'result')
        return sum(2 for word in technical if word in value) - (
            3 if re.search(r'500여|참석|인사말|이라고 밝혔다|[“”]', value) else 0)
    ranked = sorted(enumerate(evidence), key=lambda pair: (score(pair[1]), -pair[0]), reverse=True)
    key = [e for _, e in ranked[:3]]
    main = [e for _, e in sorted(ranked[:5])]
    brief = {"status": "source_extract", "analysis_version": BRIEF_VERSION,
             "method": "rule_extract", "evidence_basis": source['evidence_basis'],
             "source_provenance": {k: v for k, v in source.items() if k != 'evidence'},
             "key_takeaways": [e['quote'] for e in key],
             "main_points": [e['quote'] for e in main],
             "research_ideas": research_ideas(record, evidence),
             "template_suggestions": template_suggestions(record),
             "korea_implications": "", "industry_implications": "",
             "limitations": "원문 구절을 규칙으로 분류한 비번역 발췌. 한국어 심층 해석·법령 교차검증 미실행. 결론은 원문에 명시된 결론·후속 계획만 표시하며 연구 제안의 신규성·실현 가능성은 미검증.",
             "field_evidence": {}, "section_status": {}}
    for name, rows in classified.items():
        brief[name] = '\n'.join(e['quote'] for e in rows)
        brief['field_evidence'][name] = [e['id'] for e in rows]
        brief['section_status'][name] = 'extracted' if rows else 'not_found'
    for name, rows in [('key_takeaways', key), ('main_points', main)]:
        for i, e in enumerate(rows):
            brief['field_evidence'][f'{name}.{i}'] = [e['id']]
    used = {eid for ids in brief['field_evidence'].values() for eid in ids}
    used.update(eid for idea in brief['research_ideas'] for eid in idea['evidence_ids'])
    brief['evidence'] = [e for e in evidence if e['id'] in used]
    return brief
