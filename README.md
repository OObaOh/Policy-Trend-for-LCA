# Policy Trend for LCA · Carbon & LCA Intelligence Hub

공개 정책·규제·기술·LCA 논문 **자동 수집과 개인 연구 관련성 표시**를 결합한 GitHub Pages 사이트입니다.

- **GitHub 저장소:** https://github.com/OObaOh/Policy-Trend-for-LCA
- **예상 공개 주소:** https://oobaoh.github.io/Policy-Trend-for-LCA/ (**Pages 활성화 후에만 접속 가능**)

## 지원 기능

- 약 **매일 한국시간 오전 9:13** GitHub Actions로 자동 실행 (`schedule`은 지연·누락될 수 있음).
- 한국 기후에너지환경부·UNFCCC·EU 집행위원회, 영국 DESNZ/Defra, 미국 Federal Register 공식 관보, 일본 환경성, 독일 연방환경부 및 프랑스 정부 공개 페이지 등에서 관련 공표정보 탐색.
- Crossref에서 **DOI가 있는 논문 및 보고서의 메타데이터**를 추가 탐색. 데이터 수집원 또는 피드 형식 변경에 따라 일부 국가의 자동 갱신이 실패할 수 있으므로 Actions의 수집 성공·실패 로그 확인 필요.
- EPR, ESPR·DPP, ELV, PPWR, 폐기물 처리·관리, 순환경제, 재생 플라스틱, WTW, 수소도시, 자동차부품, allocation·Dynamic/Prospective/Consequential LCA, CoC·PDS·PCF 등 폭넓은 주제 탐색.
- 기존 `Research Themes` 고정 버튼 대신 자료의 제목·피드 발췌문에서 발견되는 **동적 키워드**를 표시. 새 약어/법령명도 자동으로 나타날 수 있으나 모든 새 개념을 정확히 파악한다는 보장은 없음.
- **개인 관심도 필독 / 우선 검토 / 참고** 분류, `필독 · 미열람` 단축 버튼, 국가·자료유형·열람여부 검색.
- 각 카드의 **원문/DOI** 버튼은 공표된 기관 페이지 또는 DOI 공식 랜딩 페이지를 새 탭에서 엽니다. 유료 논문의 전문 접근 권한은 보장하지 않음.
- 원문 버튼을 클릭하면 **그 브라우저에만 열람 표시** 저장. `열람 완료 표시`·`미열람으로 변경`도 가능. 다른 기기나 브라우저와 기록이 동기화되지는 않음.
- 개별 키워드 옆 ☆를 누르면 **직접 지정한 관심 주제**로 저장되어 그 브라우저에서 관련 자료의 표시 우선순위를 높임.

## 개인 맞춤 주목도: 정확한 의미

이 값은 **정책 또는 정부에 대한 긍정/부정 평가나 법적 중요도를 말하는 게 아닙니다.**
사용자의 대화에서 드러난 연구 관심사와 문서 제목·공개 서지정보·기관 발표 요약의 **관련성**을 비교하는 읽기 순서 추천값입니다.

- 분석에 쓰이는 관심 프로필: [`config/interests.json`](config/interests.json).
- 연결된 ChatGPT 대화를 자동 조회하거나 민감한 이용 기록을 GitHub에 게시하지 않습니다. 관심 프로필은 현재 설정된 정적 가중치이며, **새 관심사는 이 파일을 편집하거나 사이트 키워드 ☆를 사용**해야 반영됩니다.
- 계산 코드: [`scripts/topics.py`](scripts/topics.py). 단어에 가중치를 주고 직접 관련성, 부가 설명, 여러 주제의 결합을 반영합니다.
- **필독:** 계산 점수 24 이상 / **우선 검토:** 12 이상 / **참고:** 그 밖의 자료.
- `필독`은 이용자 관심 주제에 *우선 확인할 가치가 있다는 추천*이며 실제 법적 효력, 학술적 신뢰도, 환경개선 효과를 판단한 것이 아닙니다.
- 관심 프로필의 편집내용이 공개 저장소에 노출되므로 비밀이나 개인 식별정보를 넣지 마세요.

## 운영자가 처음 한 번 해야 하는 일

1. 저장소 **Settings → Pages → Build and deployment → Source → GitHub Actions**로 변경합니다.
2. 저장소 **Settings → Actions → General → Workflow permissions → Read and write permissions**로 설정합니다. (권한이 이미 충분하면 변경할 필요 없음.)
3. 저장소의 **Actions → Collect intelligence and publish site → Run workflow**를 실행합니다.
4. 해당 작업의 `publish`가 성공한 뒤 **Settings → Pages**에서 배포 URL을 확인합니다. 일반적으로 `https://oobaoh.github.io/Policy-Trend-for-LCA/`입니다.
5. 첫 실행에서 각 수집원 접속성공/실패를 Actions 로그로 확인합니다. **모든 국가의 전체 법률을 전수 검색하는 시스템은 아닙니다.**

`GITHUB_TOKEN`으로 작성된 데이터 커밋은 별도 `push` 작업을 재실행시키지 않기 때문에, 본 워크플로는 **수집→데이터 커밋→같은 실행에서 즉시 Pages 배포**를 진행합니다.

## AI 요약 사용 (선택 사항)

**API 키 없이도** 공식 발표/논문의 제목·날짜·출처·DOI 및 주목도·동적 키워드 수집은 작동합니다.
AI 요약과 예비 LCA 연구 인사이트 생성은 별도의 **OpenAI API 비용**과 설정이 필요합니다.

- GitHub 저장소 **Settings → Secrets and variables → Actions → New repository secret**에서 `OPENAI_API_KEY` 추가.
- 키를 이 저장소나 대화에 직접 입력하지 마세요.
- `MAX_AI_PER_RUN` 기본 10건, `OPENAI_MODEL` 기본 `gpt-4.1-mini`.
- **보도자료나 논문의 공개 제목·피드 발췌문 수준에서만 분석**합니다. 유료 논문 전체를 읽거나 시행령 전체를 법률적으로 교차 검증하지 않습니다. 신뢰가 필요한 사실은 반드시 링크 원문에서 확인하세요.

## 구조

| 경로 | 기능 |
|---|---|
| `site/index.html`, `site/assets/` | 웹 대시보드 (모바일 지원) |
| `site/data/articles.json` | 누적된 출처 메타데이터 및 우선순위 |
| `config/interests.json` | 개인 연구 관심 주제, 가중치 |
| `scripts/topics.py` | 신규 키워드 추출·관련도 계산 |
| `scripts/collect.py` | 정부 공개 페이지 / 공식 피드 / Crossref / 선택적 AI 요약 |
| `.github/workflows/publish.yml` | 매일 수집·저장 및 GitHub Pages 자동 배포 |
| `tests/test_collect.py` | 외부 네트워크 없이 실행하는 수집·분류 회귀 테스트 |

## 설치 및 확인

```bash
python -m pip install -r requirements.txt pytest
python -m pytest -q
python -m http.server 8000 --directory site
# http://localhost:8000
```

네트워크를 이용한 수집은 `python scripts/collect.py` 실행. 링크의 유효성 검증은 최선의 시도이므로 일부 기관의 차단 및 유료 논문 접근 불가는 실패로 단정하지 않습니다.

*마지막 갱신: 2026-10-10 / v1.2*


## v1.3 — 정책·규제·논문별 내부 분석 보고서

- 카드 제목 또는 `요약·연구주제 보기 →` 선택 시 `site/detail.html?id=<자료ID>` 형식의 내부 보고서로 이동합니다. 기존 공식 원문·DOI 링크는 별도 버튼으로 유지됩니다.
- 보고서 목차는 **핵심 사항 / LCA 논문주제 제안 / 배경 / 목적 / 주요 내용 / 결론 / 한국 및 산업계 시사점 / 출처와 검증 한계**입니다.
- 연구 아이디어는 단순 LCA 수행·비교를 피하고, 할당·시스템경계·데이터 품질·시간적 전력믹스·회피배출·폐기물 제도 등 방법론 문제를 우선 검토합니다. 제안은 해당 문헌의 결론이나 이미 검증된 연구 공백이 아닙니다.
- 상세 내용의 자동 분석에는 GitHub **Settings → Secrets and variables → Actions → New repository secret**에서 `OPENAI_API_KEY`를 추가해야 합니다. **API 키를 공개 파일이나 채팅에 입력하지 마세요.** ChatGPT 구독료와 별개로 OpenAI API 요금이 발생할 수 있습니다.
- 분석기는 신규 자료뿐 아니라 기존 아카이브의 미분석 항목도 점진적으로 처리하며, 실행당 기본 최대 **6건**에 한정합니다. 배치 처리는 며칠에 걸릴 수 있습니다.
- 가능한 경우 **공개 기관 본문 일부 또는 Crossref 초록**을 일시적으로 분석 근거로 이용합니다. 전문이 없거나 근거가 빈약하면 내용을 생성하지 않고 **원문 확인 필요**로 표시합니다.
- API 연결 전에도 웹사이트의 분석 페이지·기존 자료·원문 링크는 표시되지만, 배경·목적·결론과 구체적인 신규 LCA 논문 아이디어는 자동으로 채워지지 않을 수 있습니다.
- 원문 열람 상태는 기존과 동일하게 **해당 브라우저 기준**이며, 내부 상세페이지를 열었다는 이유만으로 원문을 읽었다고 표시하지 않습니다.
