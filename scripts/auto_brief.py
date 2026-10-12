"""Grounded, no-key fallback for public source text.

This module does NOT claim to translate or synthesize like an LLM. It retrieves
public body paragraphs, selects relevant statements, and builds a separately
labeled extractive brief. Original prose remains marked as excerpts.
"""
from __future__ import annotations

import re
import urllib.parse
from bs4 import BeautifulSoup

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

def extract_paragraphs(html: bytes) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    for part in soup.select("script,style,noscript,nav,footer,header,aside,form,svg,iframe"):
        part.decompose()
    selectors = ("main article","article","main",".article-content",
                 ".region-content","#mainContent","#content","body")
    root = None
    for selector in selectors:
        node = soup.select_one(selector)
        if node and len(node.get_text(" ", strip=True)) >= 300:
            root = node
            break
    if root is None:
        return []
    arr = []
    seen = set()
    # Avoid nested list elements if parent text is already a paragraph.
    for p in root.select("p, h2, h3, li"):
        if p.name == "li" and p.find(["p","ul","ol"]):
            continue
        raw = clean_sentence(p.get_text(" ", strip=True), 850)
        if len(raw) < 45 or NOISE.search(raw) or raw in seen:
            continue
        if sum(ch.isalpha() for ch in raw) < 35:
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

def research_ideas(record: dict) -> list[dict]:
    topic = choose_topic(record)
    item = IDEAS.get(topic)
    if not item:
        return []
    return [dict(zip(("title","research_question","methodology","novelty","data"), item))]

def source_extract_brief(record: dict, *, fetcher, clean=None) -> dict | None:
    """No-model extraction from openly published source, never synthetic legal facts."""
    url = record.get("url","")
    paragraphs: list[str] = []
    basis = ""
    if record.get("doi"):
        # Only the publisher-supplied abstract, never a paywalled full text.
        try:
            doi = urllib.parse.quote(record["doi"], safe="/")
            data = __import__("json").loads(fetcher(
                "https://api.crossref.org/works/" + doi, timeout=16))
            abstract = (data.get("message") or {}).get("abstract", "")
            if abstract:
                abstract = BeautifulSoup(abstract, "html.parser").get_text(" ", strip=True)
                paragraphs = [clean_sentence(s, 550) for s in
                    re.split(r"(?<=[.!?])\s+(?=[A-Z가-힣])", abstract)
                    if len(s) >= 50]
                basis = "Crossref에 등록된 출판사 제공 초록 발췌"
        except Exception:
            pass
    elif is_official(url):
        try:
            body = fetcher(url, timeout=17)
            paragraphs = extract_paragraphs(body)
            basis = "공식 기관 공개 웹페이지 본문 자동 발췌"
        except Exception:
            pass
    if not paragraphs and len(record.get("source_excerpt","")) >= 90:
        paragraphs = [record["source_excerpt"]]
        basis = "기관 공개 미리보기 발췌"
    if not paragraphs:
        return None
    title = record.get("title","").casefold()
    tokens = {x for x in re.split(r"[^\w가-힣]+", title) if len(x) >= 5}
    def score(s: str) -> int:
        low=s.casefold()
        hit=sum(2 for word in tokens if word in low)
        topic=choose_topic(record)
        hit+=sum(2 for word in TOPIC_WORDS.get(topic,[]) if word.casefold() in low)
        return hit
    indexed=list(enumerate(paragraphs))
    indexed.sort(key=lambda pair: (score(pair[1]), -pair[0]), reverse=True)
    selected=sorted(indexed[:6], key=lambda pair: pair[0])
    lines=[clean_sentence(value, 350) for _, value in selected]
    if not lines or sum(len(x) for x in lines)<100:
        return None
    first=lines[0]
    note="원문 핵심 구절 자동 발췌(비번역). 전체 문맥을 확정적으로 재구성한 AI 요약은 아님."
    return {
        "status":"source_extract",
        "evidence_basis":basis,
        "key_takeaways":lines[:3],
        "research_ideas":research_ideas(record),
        "background":"",
        "purpose":"",
        "main_points":lines[:5],
        "conclusion":"",
        "korea_implications":"",
        "industry_implications":"",
        "limitations":note,
        "evidence_sections":"발표기관 공개 본문/초록",
    }
