(() => {
'use strict';
const $ = id => document.getElementById(id);
const el = (tag, cls='', val) => {
  const n=document.createElement(tag);
  if(cls)n.className=cls;
  if(val!==undefined)n.textContent=String(val);
  return n;
};
const fallback='해당 자료는 사이트의 자동 원문 조사 대기열에 있습니다. 조사 결과가 확보되면 상세 보고서에 반영됩니다.';
const text=(x,defaultValue=fallback)=>typeof x==='string'&&x.trim()?x.trim():defaultValue;
function paragraph(id,s,empty=''){const box=$(id); const section=box.closest('.report-section'); if(section)section.hidden=!Boolean(s||empty); box.replaceChildren(); box.append(el('p',s?'':'report-empty',s||empty));}
function bullets(id,arr,alt=fallback,numeric=false){
  const dest=$(id);dest.replaceChildren();
  const list=Array.isArray(arr)?arr.filter(x=>typeof x==='string'&&x.trim()).slice(0,8):[];
  const section=dest.closest('.report-section');if(section)section.hidden=list.length===0&&!alt;
  if(!list.length){if(alt)dest.append(el('p','report-empty',alt));return;}
  const ul=el('ul',numeric?'report-number-list':'report-bullet-list');
  list.forEach(item=>ul.append(el('li','',item)));dest.append(ul);
}
const storageKey='carbon-lca-visited-v2';
const itemKey=a=>a.id||a.doi||a.url;
function read(a){try {return JSON.parse(localStorage.getItem(storageKey)||'[]').includes(itemKey(a));}catch{return false;}}
function updateRead(a,value){
  try{const arr=JSON.parse(localStorage.getItem(storageKey)||'[]');const set=new Set(Array.isArray(arr)?arr:[]);
    if(value)set.add(itemKey(a));else set.delete(itemKey(a));
    localStorage.setItem(storageKey,JSON.stringify([...set]));
  }catch{}
}
function display(a,runtime={}){
  const b=a.analysis&&typeof a.analysis==='object'?a.analysis:{};
  const available=b.status==='ai_preliminary';
  const extracted=b.status==='source_extract';
  const grounded=Number(b.analysis_version)>=2&&Array.isArray(b.evidence);
  const evidenceRows=grounded?b.evidence:[];
  const evidenceById=new Map(evidenceRows.map(row=>[row.id,row]));
  function refs(dest,ids){
    if(!Array.isArray(ids))return;
    ids.filter(id=>evidenceById.has(id)).forEach(id=>{
      const link=el('a','evidence-ref','[근거 '+(evidenceRows.findIndex(e=>e.id===id)+1)+']');
      link.href='#evidence-'+encodeURIComponent(id);dest.append(link);
    });
  }
  function fieldRefs(id,path){
    const dest=$(id);refs(dest,b.field_evidence?.[path]);
    if(b.claim_types?.[path]==='interpretation')dest.prepend(el('span','claim-label','분석자의 해석 · '));
  }
  function listRefs(id,path){
    $(id).querySelectorAll('li').forEach((li,i)=>{
      refs(li,b.field_evidence?.[path+'.'+i]);
      if(b.claim_types?.[path+'.'+i]==='interpretation')li.prepend(el('span','claim-label','분석자의 해석 · '));
    });
  }
  const basis=b.evidence_basis||(a.source_excerpt?(a.doi?'출판사 공개 초록 발췌':'기관 공개 발췌'):'제목·서지정보만 확보');
  document.title=a.title+' | Carbon & LCA Intelligence Hub';
  $('report-title').textContent=a.title;
  $('report-intro').textContent=extracted?'공개 원문의 발췌와 분류 결과입니다. 원문 내용, 연구 가설, 일반 주제 템플릿을 구분해 표시합니다.':text(a.summary,'정책·연구자료의 공표 정보를 수집했습니다. 아래 항목은 확인된 사실과 검토가 필요한 내용을 구분해 보여줍니다.');
  const labels=$('report-kickers');labels.replaceChildren();
  [a.category||'연구동향',a.region||'지역 미확인',a.priority||'참고'].forEach(s=>labels.append(el('span','report-chip',s)));
  const meta=$('report-metadata');meta.replaceChildren();
  [a.date||'발표일 미확인',a.source||'기관 미확인',a.document_type||'자료 유형 미확인',a.doi?'DOI: '+a.doi:'기관 발표 페이지'].forEach(s=>meta.append(el('span','',s)));
  let url='';
  try {const x=new URL(a.url);if(x.protocol==='https:'||x.protocol==='http:')url=x.href;}catch{}
  const primary=$('report-source'),footer=$('report-source-footer');
  if(url){
    primary.href=url;footer.href=url;
    primary.textContent=a.doi?'논문 DOI 원문 확인 ↗':'기관 원문 확인 ↗';
    const handler=()=>{updateRead(a,true);refreshRead();};
    primary.addEventListener('click',handler);footer.addEventListener('click',handler);
  }else{primary.removeAttribute('href');footer.removeAttribute('href');primary.textContent='원문 링크 확인 필요';}
  function refreshRead(){$('report-read-button').textContent=read(a)?'원문 미열람으로 변경':'원문 열람 완료 표시';}
  refreshRead();
  $('report-read-button').addEventListener('click',()=>{updateRead(a,!read(a));refreshRead();});
  $('report-copy-button').addEventListener('click',async()=>{
    try{await navigator.clipboard.writeText(location.href);$('report-copy-button').textContent='링크 복사됨 ✓';}
    catch{$('report-copy-button').textContent='주소 표시줄에서 링크 복사';}
  });
  const stage=b.status==='editorial_preliminary'?'편집 검토자의 한국어 예비 분석 · 조문별 검증 별도':available?(grounded?'AI 한국어 예비 분석 · 인용 참조 검사':'기존 AI 예비 분석 · 문단별 근거 미연결'):extracted?(grounded?'원문 구절 분류 · 한국어 심층 분석 미실행':'이전 방식의 원문 발췌 · 재추출 대상'):'원문 근거 미확보 · 심층 분석 미실행';
  $('report-quality').replaceChildren(el('strong','',stage),el('span','','분석 근거: '+basis+'. LCA 논문주제는 확정된 연구 결과가 아닌 연구 제안입니다.'));
  if(runtime.ai?.status==='disabled_no_key')$('report-quality').append(el('span','','이번 수집에서 외부 AI 분석 미실행: API 키 미설정. 기존 분석은 생성 당시 상태로 표시됩니다.'));
  else if(runtime.ai?.status==='blocked_api_error')$('report-quality').append(el('span','','이번 수집에서 외부 AI API 오류 발생. 기존 원문 발췌와 분석을 유지했습니다.'));
  bullets('key-points-content',b.key_takeaways,a.summary?'이미 확보한 핵심 내용: '+a.summary:fallback,true);
  listRefs('key-points-content','key_takeaways');
  if(extracted){
    $('report-key-points').querySelector('h2').textContent='핵심 원문 구절 · 비번역 발췌';
    $('report-content').querySelector('h2').textContent='주요 내용 · 원문 구절';
    $('report-conclusion').querySelector('h2').textContent='원문에 명시된 결론·후속 계획';
  }
  const ideas=$('research-content');ideas.replaceChildren();
  const legacyTemplate=extracted&&!grounded;
  const proposals=legacyTemplate?[]:(Array.isArray(b.research_ideas)?b.research_ideas:[]);
  const templates=legacyTemplate?b.research_ideas:b.template_suggestions;
  if(proposals.some(i=>i&&i.title)){
    proposals.filter(i=>i&&i.title).slice(0,3).forEach((idea,i)=>{
      const card=el('article','research-card');card.append(el('h3','',String(i+1)+'. '+idea.title));
      const origin=idea.origin==='rule_based_hypothesis'?'원문 특징과 연결한 규칙 기반 가설':idea.origin==='ai_source_hypothesis'?'AI가 제안한 원문 기반 가설':'기존 연구 제안 · 문단별 근거 미연결';
      card.append(el('p','report-caption',origin+' · 선행연구·신규성 미검증'));
      const dl=el('dl');
      [['원문과의 연결',idea.source_connection],['연구 질문',idea.research_question],['LCA 방법론적 쟁점',idea.methodology],['선행연구 검토 과제',idea.novelty],['데이터 확보·제약',idea.data]].forEach(pair=>{
        dl.append(el('dt','',pair[0]),el('dd','',text(pair[1],'추가 검토 필요')));
      });card.append(dl);refs(card,idea.evidence_ids);ideas.append(card);
    });
  }else ideas.append(el('p','report-empty','이 자료의 근거와 연결된 구체적 연구 질문은 아직 생성되지 않았습니다.'));
  if(Array.isArray(templates)&&templates.length){
    const box=el('details','template-suggestions');
    box.append(el('summary','','일반 주제 템플릿 · 원문 분석과 별개'));
    box.append(el('p','report-caption','제목·태그로 선택한 고정 템플릿입니다. 해당 문헌에서 도출한 연구 공백이나 결론이 아닙니다.'));
    templates.filter(i=>i&&i.title).forEach(idea=>{
      box.append(el('h3','',idea.title),el('p','',idea.research_question||''));
    });ideas.append(box);
  }
  const missing=grounded?'원문에서 이 항목을 명확히 분류할 근거를 확보하지 못했습니다. 내용을 생성하지 않았습니다.':'';
  paragraph('background-content',b.background,missing);fieldRefs('background-content','background');
  paragraph('purpose-content',b.purpose,missing);fieldRefs('purpose-content','purpose');
  bullets('main-content',b.main_points,a.source_excerpt?'공식 발표문·논문 초록 발췌: '+a.source_excerpt:'');
  listRefs('main-content','main_points');
  paragraph('conclusion-content',b.conclusion,missing);fieldRefs('conclusion-content','conclusion');
  const impact=$('implications-content');impact.replaceChildren();
  $('report-implications').hidden=!(b.korea_implications||b.industry_implications);
  const domestic=a.region==='한국';
  const research=a.category==='LCA 논문'||a.category==='연구보고서';
  $('implication-title').textContent=domestic?'국내 산업계에 미치는 영향':(research?'국내 연구·산업 적용 시사점':'우리나라 및 산업계에 미치는 영향');
  function addImpact(label,value,path,empty){
    impact.append(el('h3','report-impact-label',label));
    const p=el('p',value?'':'report-empty',text(value,empty));
    if(b.claim_types?.[path]==='interpretation')p.prepend(el('span','claim-label','분석자의 해석 · '));
    refs(p,b.field_evidence?.[path]);impact.append(p);
  }
  if(!domestic){
    addImpact('우리나라 적용·연계 시사점',b.korea_implications,'korea_implications','국내 적용에 관한 분석 근거를 확보하지 못했습니다.');
  }
  addImpact(research?'연구 및 산업 현장 적용':'산업계에 미치는 영향',b.industry_implications,'industry_implications','산업 영향에 관한 분석 근거를 확보하지 못했습니다.');
  const evidence=$('evidence-content');evidence.replaceChildren();
  ['출처: '+(a.source||'미확인')+' · '+(a.date||'날짜 미확인')+' · '+(a.verification||'원문 메타데이터'),
  '분석 수준: '+stage+' · 근거: '+basis,
  '한계: '+text(b.limitations,'기관 발표문 또는 논문 전체 본문을 검증한 전문가 보고서가 아닙니다. 공식 원문 확인이 필요합니다.'),
  b.generated_at?'분석 생성일: '+b.generated_at:'',
  grounded?'문단 근거는 아래 원문 발췌로 연결됩니다. 인용 참조 검사는 문장 의미의 일치나 법적 효력을 보장하지 않습니다.':'',
  b.source_provenance?.retrieved_at?'원문 조회: '+b.source_provenance.retrieved_at:'',
  a.doi?'DOI: '+a.doi:''].filter(Boolean).forEach(x=>evidence.append(el('p','',x)));
  evidenceRows.forEach((row,i)=>{
    const block=el('div','evidence-quote');block.id='evidence-'+encodeURIComponent(row.id);
    block.append(el('h3','report-impact-label','근거 '+(i+1)+' · '+row.locator));
    block.append(el('blockquote','',row.quote));
    try{const u=new URL(row.url);if(['https:','http:'].includes(u.protocol)){
      const link=el('a','source-ext-link','해당 근거 출처 ↗');link.href=u.href;link.target='_blank';link.rel='noopener noreferrer';block.append(link);
    }}catch{}
    evidence.append(block);
  });
  document.querySelectorAll('.toc-sticky>a[href^="#report-"]').forEach(link=>{
    const section=document.getElementById(link.getAttribute('href').slice(1));
    if(section)link.hidden=section.hidden;
  });
  if(Array.isArray(b.evidence_links)&&b.evidence_links.length){
    const heading=el('h3','report-impact-label','추가 확인된 공식 출처');
    const links=el('ul','report-bullet-list');
    b.evidence_links.slice(0,6).forEach(item=>{
      try{
        const u=new URL(item.url);
        if(u.protocol!=='https:')return;
        const li=el('li');const link=el('a','source-ext-link',item.title||u.hostname);
        link.href=u.href;link.target='_blank';link.rel='noopener noreferrer';
        li.append(link);links.append(li);
      }catch{}
    });
    if(links.children.length)evidence.append(heading,links);
  }
  $('loading').hidden=true;$('report').hidden=false;
}
const id=new URLSearchParams(location.search).get('id');
if(!id||id.length>160){$('loading').textContent='자료 ID가 없습니다. 아카이브에서 항목을 다시 선택해 주세요.';return;}
fetch('./data/articles.json?v='+Date.now(),{cache:'no-store'})
  .then(r=>{if(!r.ok)throw Error('archive unavailable');return r.json();})
  .then(data=>{const list=Array.isArray(data)?data:data.articles||[];const found=list.find(a=>String(a.id||a.doi||a.url)===id);
    if(found)display(found,data.analysis_runtime||{});
    else $('loading').textContent='해당 자료가 아카이브에 없습니다. 메인에서 다시 선택해 주세요.';
  }).catch(()=>{$('loading').textContent='자료를 불러오지 못했습니다. 페이지를 새로고침해 주세요.';});
})();
