/* Headless browser checks of the report's user-visible evidence distinctions. */
const {test, before, after}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {chromium}=require('playwright');
const root=path.resolve(__dirname,'..');
const realArchive=JSON.parse(fs.readFileSync(path.join(root,'site/data/articles.json')));
const real=realArchive.articles.find(a=>a.id==='97f4b4d803947e');
const legacy=JSON.parse(fs.readFileSync(path.join(__dirname,'fixtures/waste_energy_20261014_before.json')));
let browser;
before(async()=>{browser=await chromium.launch({headless:true,args:['--no-sandbox'],executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH||undefined});});
after(async()=>{if(browser)await browser.close();});

async function openReport(article){
  const context=await browser.newContext();
  const page=await context.newPage();
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.route('http://lca.test/**',async route=>{
    const pathname=new URL(route.request().url()).pathname;
    if(pathname==='/data/articles.json')return route.fulfill({json:{articles:[article],analysis_runtime:{ai:{status:'disabled_no_key'}}}});
    const filename=path.join(root,'site',pathname);
    if(!filename.startsWith(path.join(root,'site')+path.sep)||!fs.existsSync(filename))return route.fulfill({status:404,body:''});
    const type=pathname.endsWith('.js')?'text/javascript':pathname.endsWith('.css')?'text/css':'text/html';
    return route.fulfill({body:fs.readFileSync(filename),contentType:type+'; charset=utf-8'});
  });
  await page.goto('http://lca.test/detail.html?id='+article.id);
  await page.waitForSelector('#report:visible');
  return {context,page,errors};
}

test('real report distinguishes extraction, source-linked hypothesis and topic template',async()=>{
  const {context,page,errors}=await openReport(real);
  try{
    const key=await page.locator('#key-points-content').innerText();
    assert(!/첨부파일|\.hwpx|\.pdf|500여/.test(key));
    assert.match(key,/가연성/);assert.match(key,/환경안전성/);
    assert.match(await page.locator('#report-quality').innerText(),/심층 분석 미실행/);
    assert.match(await page.locator('#report-quality').innerText(),/API 키 미설정/);
    assert.match(await page.locator('.research-card').innerText(),/규칙 기반 가설/);
    const templates=page.locator('.template-suggestions');
    assert.equal(await templates.getAttribute('open'),null);
    await templates.locator('summary').click();
    assert.match(await templates.innerText(),/고정 템플릿/);
    assert.match(await page.locator('#conclusion-content').innerText(),/향후 관련 연구를 지속할 계획/);
    assert.equal(await page.locator('#report-source').getAttribute('href'),real.url);
    const cite=page.locator('#purpose-content .evidence-ref').first();
    const target=await cite.getAttribute('href');await cite.click();
    assert.match(await page.locator(target+' blockquote').innerText(),/가연성 및 유기성/);
    assert.equal(await page.locator('#report-read-button').innerText(),'원문 열람 완료 표시');
    assert.deepEqual(errors,[]);
  }finally{await context.close();}
});

test('legacy fixed ideas move into a separate template disclosure',async()=>{
  const {context,page,errors}=await openReport(legacy);
  try{
    assert.equal(await page.locator('.research-card').count(),0);
    assert.equal(await page.locator('.template-suggestions').count(),1);
    assert.match(await page.locator('#report-quality').innerText(),/재추출 대상/);
    assert.deepEqual(errors,[]);
  }finally{await context.close();}
});

test('archive cards identify raw excerpts as excerpts',async()=>{
  const {context,page,errors}=await openReport(real);
  try{
    await page.goto('http://lca.test/index.html');
    await page.waitForSelector('.article-card .summary');
    assert.match(await page.locator('.article-card .summary').first().innerText(),/^원문 발췌 · /);
    assert.deepEqual(errors,[]);
  }finally{await context.close();}
});

test('missing evidence is explicit and source text cannot execute HTML',async()=>{
  const article=structuredClone(real);
  article.analysis.background='';article.analysis.field_evidence.background=[];
  article.analysis.evidence[0].quote='<img src=x onerror="window.injected=true"> 원문 문자열';
  const {context,page,errors}=await openReport(article);
  try{
    assert.match(await page.locator('#background-content').innerText(),/내용을 생성하지 않았습니다/);
    assert.equal(await page.locator('#evidence-content img').count(),0);
    assert.equal(await page.evaluate(()=>window.injected),undefined);
    assert.deepEqual(errors,[]);
  }finally{await context.close();}
});
