(() => {
  'use strict';
  const $ = (id) => document.getElementById(id);
  const state = { articles: [], category: 'all', query: '', days: 'all', sort: 'priority', shown: 8,
    priority: 'all', read: 'all', region: 'all', type: 'all', allKeywords: false };
  const groups = { '국내 정책': 'domestic', '국제 정책': 'global', '저탄소 기술': 'tech', 'LCA 논문': 'paper', '연구보고서': 'report' };
  const STORAGE_READ = 'carbon-lca-visited-v2';
  const STORAGE_FAV = 'carbon-lca-interests-v2';
  const safeGet = (key) => {
    try { const value = JSON.parse(localStorage.getItem(key) || '[]'); return Array.isArray(value) ? value : []; }
    catch { return []; }
  };
  const readSet = new Set(safeGet(STORAGE_READ));
  const favorites = new Set(safeGet(STORAGE_FAV));
  const save = (key, values) => { try { localStorage.setItem(key, JSON.stringify([...values])); } catch {} };
  const node = (tag, cls, label) => {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (label !== undefined) n.textContent = String(label);
    return n;
  };
  const validUrl = (url) => {
    try { const x = new URL(url); return ['https:', 'http:'].includes(x.protocol) ? x.href : ''; }
    catch { return ''; }
  };
  const escTag = (tag) => String(tag || '').trim();
  const getTags = (article) => Array.isArray(article.tags) ? article.tags.filter(x => typeof x === 'string') : [];
  function readKey(article) { return article.id || article.doi || article.url; }
  function visited(article) { return readSet.has(readKey(article)); }
  function markVisited(article, value = true) {
    if (value) readSet.add(readKey(article)); else readSet.delete(readKey(article));
    save(STORAGE_READ, readSet);
    requestAnimationFrame(refresh);
  }
  function safeLink(url, label, cls, article) {
    const href = validUrl(url);
    if (!href) return node('span', cls || '', '원문 연결 확인 필요');
    const a = node('a', cls || '', label);
    a.href = href;
    a.target = '_blank';
    a.rel = 'noopener noreferrer';
    a.title = `기관/논문 원문으로 이동: ${new URL(href).hostname}`;
    if (article) a.addEventListener('click', () => markVisited(article));
    return a;
  }
  function localDate(date) {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(date || '')) return '날짜 미확인';
    const d = new Date(date + 'T12:00:00Z');
    return Number.isNaN(d.getTime()) ? date : new Intl.DateTimeFormat('ko-KR', {
      year: 'numeric', month: '2-digit', day: '2-digit', timeZone: 'Asia/Seoul'
    }).format(d);
  }
  function recent(date, days) {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(date || '')) return false;
    const today = new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Seoul',
      year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date());
    const delta = (Date.parse(today + 'T00:00:00Z') - Date.parse(date + 'T00:00:00Z')) / 86400000;
    return delta >= 0 && delta < days;
  }
  function computedPriority(a) {
    const base = Math.max(0, Math.min(100, Number(a.priority_score) || 0));
    const favoriteHits = getTags(a).filter(t => favorites.has(t));
    const score = Math.min(100, base + (favoriteHits.length ? 24 + (favoriteHits.length - 1) * 5 : 0));
    const level = score >= 24 ? '필독' : score >= 12 ? '우선 검토' : '참고';
    return {score, level, reasons: [...(a.priority_reasons || []), ...favoriteHits.map(t => `${t} · 직접 지정`)]
      .filter((v, i, arr) => arr.indexOf(v) === i).slice(0, 3)};
  }
  function priorityRank(level) { return {'필독': 3, '우선 검토': 2, '참고': 1}[level] || 0; }
  function compareByPriority(a, b) {
    const pa = computedPriority(a), pb = computedPriority(b);
    return priorityRank(pb.level) - priorityRank(pa.level)
      || Number(!visited(b)) - Number(!visited(a))
      || pb.score - pa.score
      || (b.date || '').localeCompare(a.date || '');
  }
  function labelCategory(cat) { return node('span', `category ${groups[cat] || 'domestic'}`, cat || '기타'); }
  function previewText(a) {
    return (a.analysis?.key_takeaways?.[0] || '') || a.summary || (a.doi ? 'Crossref DOI·서지정보가 등록됐습니다. 방법론과 결과는 논문 원문을 확인해 주세요.'
      : '기관 공개 발표 제목과 원문 링크를 수집했습니다. 시행일·적용 범위 등은 해당 원문 확인이 필요합니다.');
  }
  function labelPriority(entry) {
    const p = computedPriority(entry);
    const label = node('span', `priority-badge priority-${priorityRank(p.level)}`, p.level === '필독' ? '✦ 필독' : p.level);
    label.title = `개인 연구 관련성: ${p.score}/100 · ${p.reasons.join(' · ') || '추가 관심 키워드 선택 가능'}`;
    return label;
  }
  function unreadTag(entry) { return node('span', visited(entry) ? 'seen-tag' : 'unread-tag', visited(entry) ? '원문 열어봄' : '● 미열람'); }
  function detailLink(entry, label, cls = '') {
    const a = node('a', cls, label);
    a.href = './detail.html?id=' + encodeURIComponent(readKey(entry));
    a.title = '사이트 내부 요약과 LCA 연구주제 먼저 읽기';
    return a;
  }
  function sourceLink(entry, text = '원문 바로가기 ↗') { return safeLink(entry.url, text, 'source-link', entry); }
  function renderStats() {
    const a = state.articles;
    $('stat-total').textContent = a.length.toLocaleString('ko-KR');
    $('stat-week').textContent = a.filter(x => recent(x.date, 7)).length.toLocaleString('ko-KR');
    $('stat-policy').textContent = a.filter(x => ['국내 정책', '국제 정책'].includes(x.category)).length.toLocaleString('ko-KR');
    const mustUnread = a.filter(x => computedPriority(x).level === '필독' && !visited(x)).length;
    $('stat-must').textContent = mustUnread.toLocaleString('ko-KR');
    $('queue-must-count').textContent = mustUnread;
    $('queue-high-count').textContent = a.filter(x => computedPriority(x).level === '우선 검토' && !visited(x)).length;
    $('nav-all').textContent = a.length;
    $('nav-domestic').textContent = a.filter(x => x.category === '국내 정책').length;
    $('nav-global').textContent = a.filter(x => x.category === '국제 정책').length;
    $('nav-tech').textContent = a.filter(x => x.category === '저탄소 기술').length;
    $('nav-paper').textContent = a.filter(x => x.category === 'LCA 논문').length;
    $('nav-report').textContent = a.filter(x => x.category === '연구보고서').length;
    $('today-text').textContent = new Intl.DateTimeFormat('ko-KR', {
      timeZone: 'Asia/Seoul', year: 'numeric', month: 'long', day: 'numeric'
    }).format(new Date());
  }
  function renderSpotlight() {
    const container = $('spotlight-grid'); container.replaceChildren();
    const inWindow = state.articles.filter(x => recent(x.date, 90));
    const eligible = (inWindow.length ? inWindow : state.articles).slice().sort(compareByPriority);
    const chosen = eligible.slice(0, 3);
    if (!chosen.length) {
      container.append(node('div', 'empty-state', '아직 등록된 동향이 없습니다. GitHub Actions 수집 실행 후 이 영역에 관심도가 높은 자료가 표시됩니다.'));
      return;
    }
    const first = chosen[0];
    const hero = node('article', 'spot-primary');
    const hlabel = node('div', 'spot-labels');
    hlabel.append(labelPriority(first), unreadTag(first)); hero.append(hlabel);
    const heading = node('h3'); heading.append(detailLink(first, first.title)); hero.append(heading);
    hero.append(node('p', '', previewText(first)));
    const reasons = computedPriority(first).reasons;
    if (reasons.length) hero.append(node('p', 'priority-reasons', '관심 일치 · ' + reasons.join(' / ')));
    const bottom = node('div', 'spot-bottom');
    bottom.append(node('span', '', `${localDate(first.date)} · ${first.region || ''} · ${first.source || '출처'}`));
    bottom.append(sourceLink(first)); hero.append(bottom);
    container.append(hero);
    const side = node('div', 'spot-side');
    chosen.slice(1).forEach(a => {
      const item = node('article', 'spot-small');
      const top = node('div', 'spot-labels'); top.append(labelPriority(a), unreadTag(a)); item.append(top);
      const h = node('h3'); h.append(detailLink(a, a.title)); item.append(h);
      const b = node('div', 'spot-bottom'); b.append(node('span', '', localDate(a.date))); b.append(sourceLink(a, '출처 보기 ↗'));
      item.append(b); side.append(item);
    });
    if (chosen.length === 1) side.append(node('div', 'empty-state', '새 자료를 계속 수집하고 있습니다.'));
    container.append(side);
  }
  function renderKeywordList(container, entries) {
    container.replaceChildren();
    const shown = entries.slice(0, state.allKeywords ? 60 : (container.id === 'mobile-theme-tags' ? 10 : 18));
    if (!shown.length) { container.append(node('span', 'mini-loading', '수집된 키워드가 아직 없습니다.')); return; }
    shown.forEach(({term, count}) => {
      const wrap = node('span', 'keyword-row');
      const search = node('button', 'theme' + (state.query === term ? ' chosen' : ''), `${term} · ${count}`);
      search.type = 'button'; search.title = `${term} 자료만 보기`;
      search.addEventListener('click', () => {
        state.query = term; state.category = 'all'; state.shown = 8;
        $('search-input').value = term;
        renderArchive(); $('archive').scrollIntoView({behavior:'smooth'});
        renderKeywords();
      });
      const star = node('button', 'keyword-star' + (favorites.has(term) ? ' favored' : ''), favorites.has(term) ? '★' : '☆');
      star.type = 'button'; star.title = favorites.has(term) ? `${term} 관심 해제` : `${term} 나의 관심 키워드로 추가`;
      star.setAttribute('aria-label', star.title);
      star.addEventListener('click', () => {
        if (favorites.has(term)) favorites.delete(term); else favorites.add(term);
        save(STORAGE_FAV, favorites); refresh();
      });
      wrap.append(search, star); container.append(wrap);
    });
  }
  function renderKeywords() {
    const counts = new Map();
    state.articles.forEach(a => getTags(a).forEach(tag => {
      const t = escTag(tag); if (t) counts.set(t, (counts.get(t) || 0) + 1);
    }));
    const sorted = [...counts].map(([term, count]) => ({term, count})).sort((a, b) =>
      Number(favorites.has(b.term)) - Number(favorites.has(a.term)) || b.count - a.count || a.term.localeCompare(b.term, 'ko'));
    renderKeywordList($('theme-tags'), sorted);
    renderKeywordList($('mobile-theme-tags'), sorted);
    $('all-keywords').textContent = state.allKeywords ? '키워드 접기 ↑' : `모든 키워드 보기 (${sorted.length}개) ↓`;
  }
  function articleCard(entry) {
    const item = node('article', 'article-card');
    if (!visited(entry)) item.classList.add('unvisited');
    const top = node('div', 'article-top');
    top.append(labelPriority(entry), labelCategory(entry.category), unreadTag(entry));
    item.append(top);
    const title = node('h3'); title.append(detailLink(entry, entry.title)); item.append(title);
    const meta = node('div', 'article-meta');
    meta.append(node('span', '', entry.region || '지역 미확인'));
    meta.append(node('span', '', entry.document_type || (entry.doi ? '논문' : '기관 발표')));
    meta.append(node('span', '', entry.doi ? 'DOI 등록' : (entry.verification || '원문 검토 필요')));
    item.append(meta);
    item.append(node('p', 'summary', previewText(entry)));
    const p = computedPriority(entry);
    if (p.reasons.length) item.append(node('p', 'interest-match', '✦ 왜 추천하나요?  ' + p.reasons.join(' · ')));
    if (entry.insight) item.append(node('p', 'insight', 'LCA 연구 쟁점 · ' + entry.insight));
    if (getTags(entry).length) {
      const tags = node('div', 'article-tags');
      getTags(entry).slice(0, 5).forEach(t => {
        const b = node('button', 'card-tag' + (favorites.has(t) ? ' favored' : ''), `#${t}`);
        b.type = 'button'; b.title = `${t} 키워드 찾기`;
        b.addEventListener('click', () => { state.query = t; $('search-input').value = t; state.shown = 8; renderArchive(); });
        tags.append(b);
      });
      item.append(tags);
    }
    const bottom = node('div', 'article-bottom');
    bottom.append(node('span', '', localDate(entry.date)));
    bottom.append(node('span', 'divider-dot'));
    bottom.append(node('span', 'publisher', entry.source || '원문 기관'));
    const href = validUrl(entry.url);
    if (href) bottom.append(node('span', 'source-domain', new URL(href).hostname));
    const seenToggle = node('button', 'read-toggle', visited(entry) ? '미열람으로 변경' : '열람 완료 표시');
    seenToggle.type = 'button';
    seenToggle.addEventListener('click', () => markVisited(entry, !visited(entry)));
    bottom.append(seenToggle);
    bottom.append(detailLink(entry, '요약·연구주제 보기 →', 'detail-link'));
    bottom.append(sourceLink(entry, entry.doi ? '논문 DOI ↗' : '기관 원문 ↗'));
    item.append(bottom);
    return item;
  }
  function getFiltered() {
    const q = state.query.toLocaleLowerCase();
    const list = state.articles.filter(a => {
      if (state.category !== 'all' && a.category !== state.category) return false;
      if (state.days !== 'all' && !recent(a.date, Number(state.days))) return false;
      if (state.priority !== 'all' && computedPriority(a).level !== state.priority) return false;
      if (state.read === 'unread' && visited(a)) return false;
      if (state.read === 'read' && !visited(a)) return false;
      if (state.region !== 'all' && a.region !== state.region) return false;
      if (state.type !== 'all' && (a.document_type || (a.doi ? '논문' : '기관 발표')) !== state.type) return false;
      return !q || [a.title, a.source, a.category, a.region, a.document_type, a.summary, a.insight,
        ...(a.priority_reasons || []), ...getTags(a)].join(' ').toLocaleLowerCase().includes(q);
    });
    return list.sort((a, b) => state.sort === 'priority' ? compareByPriority(a, b)
      : state.sort === 'oldest' ? (a.date || '').localeCompare(b.date || '')
      : (b.date || '').localeCompare(a.date || ''));
  }
  function renderArchive() {
    const items = getFiltered();
    $('result-count').replaceChildren(node('strong', '', items.length), document.createTextNode('건의 자료가 검색되었습니다.'));
    const list = $('article-list'); list.replaceChildren();
    if (!items.length) {
      const div = node('div', 'empty-state');
      div.append(node('strong', '', '해당 조건의 자료가 없습니다.'));
      div.append(node('span', '', '키워드·국가·기간·열람 상태 필터를 조정해 보세요.'));
      list.append(div);
    } else items.slice(0, state.shown).forEach(a => list.append(articleCard(a)));
    $('more-btn').hidden = items.length <= state.shown;
    document.querySelectorAll('[data-cat]').forEach(btn => {
      const active = btn.dataset.cat === state.category;
      btn.classList.toggle('active', active);
      btn.setAttribute('aria-pressed', active ? 'true' : 'false');
    });
  }
  function updateSelect(id, vals) {
    const select = $(id);
    const selected = select.value;
    while (select.options.length > 1) select.remove(1);
    vals.forEach(value => select.append(new Option(value, value)));
    if ([...select.options].some(option => option.value === selected)) select.value = selected;
  }
  function refresh() { renderStats(); renderSpotlight(); renderKeywords(); renderArchive(); }
  function applyQueue(priority) {
    state.priority = priority; state.read = 'unread'; state.category = 'all';
    state.query = ''; state.days = 'all'; state.region = 'all'; state.type = 'all'; state.sort = 'priority'; state.shown = 8;
    ['priority-filter', 'read-filter', 'date-filter', 'region-filter', 'type-filter', 'sort-filter']
      .forEach(id => $(id).value = ({'priority-filter':priority, 'read-filter':'unread', 'date-filter':'all',
        'region-filter':'all', 'type-filter':'all', 'sort-filter':'priority'})[id]);
    $('search-input').value = '';
    renderArchive(); $('archive').scrollIntoView({behavior:'smooth'});
  }
  function initListeners() {
    document.querySelectorAll('[data-cat]').forEach(btn => btn.addEventListener('click', () => {
      state.category = btn.dataset.cat; state.shown = 8; renderArchive();
      if (btn.classList.contains('side-link')) $('archive').scrollIntoView({behavior:'smooth'});
    }));
    $('queue-must').addEventListener('click', () => applyQueue('필독'));
    $('queue-high').addEventListener('click', () => applyQueue('우선 검토'));
    $('all-keywords').addEventListener('click', () => { state.allKeywords = !state.allKeywords; renderKeywords(); });
    $('search-input').addEventListener('input', e => { state.query = e.target.value.trim(); state.shown = 8; renderArchive(); });
    for (const [id, field] of [['date-filter', 'days'], ['sort-filter', 'sort'],
      ['priority-filter', 'priority'], ['read-filter', 'read'], ['region-filter', 'region'], ['type-filter', 'type']]) {
      $(id).addEventListener('change', e => { state[field] = e.target.value; state.shown = 8; renderArchive(); });
    }
    $('more-btn').addEventListener('click', () => { state.shown += 8; renderArchive(); });
  }
  initListeners();
  fetch('./data/articles.json?v=' + Date.now(), {cache:'no-store'})
    .then(response => { if (!response.ok) throw new Error(`HTTP ${response.status}`); return response.json(); })
    .then(data => {
      state.articles = (Array.isArray(data) ? data : data.articles || [])
        .filter(a => a && a.title && a.date && validUrl(a.url));
      const stamp = !Array.isArray(data) && data.updated_at ? new Date(data.updated_at) : null;
      $('top-status').textContent = stamp && !Number.isNaN(stamp.valueOf())
        ? `최근 점검 ${new Intl.DateTimeFormat('ko-KR', {timeZone:'Asia/Seoul', month:'2-digit', day:'2-digit', hour:'2-digit', minute:'2-digit'}).format(stamp)} KST`
        : '공식자료 아카이브';
      updateSelect('region-filter', [...new Set(state.articles.map(a => a.region).filter(Boolean))].sort((a,b)=>a.localeCompare(b, 'ko')));
      updateSelect('type-filter', [...new Set(state.articles.map(a => a.document_type || (a.doi ? '논문' : '기관 발표')))].sort((a,b)=>a.localeCompare(b, 'ko')));
      refresh();
    }).catch(error => {
      console.error('Archive loading failed:', error);
      $('top-status').textContent = '데이터 확인 실패';
      $('spotlight-grid').replaceChildren(node('div', 'empty-state', '데이터 파일 접근에 실패했습니다. 배포 설정 또는 원본 파일을 확인해 주세요.'));
      $('article-list').replaceChildren(node('div', 'empty-state', '아카이브를 불러오지 못했습니다.'));
      $('result-count').textContent = '자료를 불러오지 못했습니다.';
    });
})();
