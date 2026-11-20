/* Review workspace: play moments, keep / discard, trim, render kept clips. */
(() => {
const $ = s => document.querySelector(s);
const JOB = window.JOB_ID;
const S = { timer: null, job: null, tab: 'new', sort: 'best', cur: null, listSig: '', keptSig: '', pv: null, settingsInit: false };
const FMT = { horizontal: '16:9', vertical_blur: '9:16 blur', vertical_crop: '9:16 crop', vertical_facecam: '9:16 webcam' };
const REASON_CLS = { 'Loud moment': '', 'Sudden reaction': 'r', 'Non-stop action': 'a', 'High action': 'a', 'Most replayed': 'm' };
const FLAG_TXT = { static: 'Static screen?', camera: 'Not gameplay?' };
const fmtT = s => { s = Math.max(0, Math.round(s)); const h = Math.floor(s/3600), m = Math.floor(s%3600/60), x = s%60;
  return h ? `${h}:${String(m).padStart(2,'0')}:${String(x).padStart(2,'0')}` : `${m}:${String(x).padStart(2,'0')}`; };
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
async function api(path, body) {
  const r = await fetch(path, body === undefined ? {} : { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  if (r.status === 401) { location.href = '/login?next=' + encodeURIComponent(location.pathname); throw new Error('Please log in.'); }
  const d = await r.json().catch(() => ({}));
  if (!r.ok) { const e = new Error(d.error || `Something went wrong (${r.status}).`); e.upgrade = d.upgrade; throw e; }
  return d;
}
let toastT;
function toast(msg, upgrade) {
  const t = $('#toast'); t.innerHTML = esc(msg) + (upgrade ? ' <a href="/pricing">See plans →</a>' : '');
  t.style.display = 'block'; clearTimeout(toastT); toastT = setTimeout(() => t.style.display = 'none', upgrade ? 9000 : 5000);
}
const moments = () => (S.job?.clips || []);
const byId = id => moments().find(c => c.id === id);
const dur = c => c.end - c.start;

// ---------- polling ----------
async function poll() {
  clearTimeout(S.timer);
  let job;
  try { job = await api(`/api/jobs/${JOB}`); } catch (e) { S.timer = setTimeout(poll, 3000); return; }
  const first = !S.job || S.job.stage !== job.stage;
  S.job = job; render(first);
  if (!['error', 'cancelled'].includes(job.stage)) S.timer = setTimeout(poll, ['review', 'done'].includes(job.stage) ? 2000 : 1000);
}
function render(stageChanged) {
  const j = S.job;
  $('#j-title').textContent = j.info.title || j.url;
  const w = j.window[1] > 0 ? `${fmtT(j.window[1] - j.window[0])} scanned` : '';
  $('#j-meta').textContent = [j.info.platform, j.info.uploader, w].filter(Boolean).join(' · ');
  const working = !['review', 'done', 'error', 'cancelled'].includes(j.stage);
  $('#j-progress').style.display = working || j.stage === 'error' || j.stage === 'cancelled' ? '' : 'none';
  $('#j-bar').style.width = `${Math.round(j.progress * 100)}%`;
  const st = $('#j-status'); st.textContent = j.message; st.className = 'status' + (j.stage === 'error' ? ' err' : '');
  $('#cancel').style.display = working ? '' : 'none';
  $('#j-notes').innerHTML = j.notes.map(n => `<div class="note">${esc(n)}</div>`).join('');
  const reviewing = j.mode === 'fast' && j.stage === 'review';
  $('#review').style.display = reviewing ? 'grid' : 'none';
  if (!S.settingsInit) { $('#k-fmt').value = j.settings.format; $('#k-caps').checked = j.captions; S.settingsInit = true; }
  if (reviewing) {
    renderList();
    if (!S.cur) { const v = visible(); if (v.length) select(v[0].id); }
    else updateInfo();
  }
  drawChart();
  renderKept();
}

// ---------- list ----------
function visible(tab = S.tab) {
  const hide = $('#hideflag').checked && tab === 'new';
  const v = moments().filter(c => c.state === tab && !(hide && c.flag));
  v.sort(S.sort === 'time' ? (a, b) => a.start - b.start : (a, b) => a.rank - b.rank);
  return v;
}
function renderList() {
  const all = moments();
  const cnt = t => all.filter(c => c.state === t).length;
  $('#n-new').textContent = `(${cnt('new')})`; $('#n-kept').textContent = `(${cnt('kept')})`; $('#n-discarded').textContent = `(${cnt('discarded')})`;
  const flagged = all.filter(c => c.state === 'new' && c.flag).length;
  $('#n-flag').textContent = flagged ? `(${flagged})` : '';
  const v = visible();
  const sig = S.tab + S.sort + $('#hideflag').checked + v.map(c => c.id + c.state + (c.flag || '') + c.start + c.end + (c.status || '')).join();
  if (sig === S.listSig) { markCur(); return; }
  S.listSig = sig;
  if (!v.length) { $('#list').innerHTML = `<div class="empty">${S.tab === 'new' ? 'Nothing left to review here. 🎉' : 'None yet.'}</div>`; return; }
  $('#list').innerHTML = v.map(c => `
    <div class="item ${c.state}" data-id="${c.id}" role="button" tabindex="0">
      <span class="n">#${c.rank}</span>
      <div><div class="tm">${esc(c.label)}</div><div class="sub">${Math.round(dur(c))}s · ${esc(c.reason)}${c.flag ? ` · <span style="color:#ff9a9a">${FLAG_TXT[c.flag]}</span>` : ''}</div></div>
      <span class="st">${c.state === 'kept' ? (c.status === 'done' ? '✓' : '…') : ''}</span>
    </div>`).join('');
  markCur();
}
function markCur() { document.querySelectorAll('.item').forEach(el => el.classList.toggle('cur', el.dataset.id === S.cur)); }
$('#list').onclick = e => { const it = e.target.closest('.item'); if (it) select(it.dataset.id); };
$('#tabs').onclick = e => { const b = e.target.closest('button'); if (!b) return; S.tab = b.dataset.t;
  document.querySelectorAll('#tabs button').forEach(x => x.classList.toggle('on', x === b)); S.listSig = ''; renderList();
  const v = visible(); if (v.length && !v.some(c => c.id === S.cur)) select(v[0].id); };
$('#sort').onclick = e => { const b = e.target.closest('button'); if (!b) return; S.sort = b.dataset.s;
  document.querySelectorAll('#sort button').forEach(x => x.classList.toggle('on', x === b)); S.listSig = ''; renderList(); };
$('#hideflag').onchange = () => { S.listSig = ''; renderList(); };

// ---------- player ----------
const vid = $('#vid');
const pvCache = {};
function loadPreview(id) {
  const c = byId(id); const key = `${id}|${c?.start}|${c?.end}`;
  if (!pvCache[key]) pvCache[key] = api(`/api/jobs/${JOB}/moments/${id}/preview`, {}).catch(e => { delete pvCache[key]; throw e; });
  return pvCache[key];
}
async function select(id) {
  S.cur = id; markCur(); updateInfo();
  const el = document.querySelector(`.item[data-id="${id}"]`); if (el) el.scrollIntoView({ block: 'nearest' });
  if (!byId(id)) return;
  $('#p-wait').querySelector('span').textContent = 'Loading preview…';
  $('#p-wait').style.display = 'flex'; vid.pause();
  try {
    const pv = await loadPreview(id);
    if (S.cur !== id) return;
    S.pv = pv;
    if (vid.dataset.src !== pv.url) { vid.src = pv.url; vid.dataset.src = pv.url; }
    vid.currentTime = pv.start;
    vid.play().catch(() => {});
    $('#p-wait').style.display = 'none';
  } catch (e) { if (S.cur === id) $('#p-wait').querySelector('span').textContent = e.message; return; }
  const v = visible(); const i = v.findIndex(x => x.id === id);
  v.slice(i + 1, i + 4).forEach(x => loadPreview(x.id).catch(() => {}));  // warm up the next few
}
function updateInfo() {
  const c = byId(S.cur); if (!c) return;
  $('#p-num').textContent = `#${c.rank}`; $('#p-len').textContent = `${Math.round(dur(c))}s`;
  $('#p-time').textContent = c.label;
  const r = $('#p-reason'); r.textContent = c.reason; r.className = 'chip ' + (REASON_CLS[c.reason] ?? '');
  const f = $('#p-flag'); f.style.display = c.flag ? '' : 'none'; f.textContent = FLAG_TXT[c.flag] || '';
  const s = $('#p-state'); s.style.display = c.state === 'new' ? 'none' : '';
  s.textContent = c.state === 'kept' ? 'Kept' : 'Discarded'; s.className = 'chip ' + (c.state === 'kept' ? 'ok' : 'warn');
}
vid.addEventListener('timeupdate', () => {
  const p = S.pv; if (!p || !p.end) return;
  const t = vid.currentTime;
  $('#scrub-i').style.width = `${Math.min(100, Math.max(0, (t - p.start) / (p.end - p.start) * 100))}%`;
  if (t >= p.end) { vid.currentTime = p.start; if (!$('#autoplay').checked) vid.pause(); }
});
vid.addEventListener('click', () => vid.paused ? vid.play() : vid.pause());
$('#scrub').onclick = e => { const p = S.pv; if (!p) return; const r = e.currentTarget.getBoundingClientRect();
  vid.currentTime = p.start + (e.clientX - r.left) / r.width * (p.end - p.start); vid.play().catch(() => {}); };
function step(d) {
  const v = visible(); if (!v.length) return;
  let i = v.findIndex(c => c.id === S.cur);
  i = i < 0 ? 0 : Math.min(v.length - 1, Math.max(0, i + d));
  select(v[i].id);
}
$('#prev').onclick = () => step(-1); $('#next').onclick = () => step(1);
async function decide(state) {
  const c = byId(S.cur); if (!c) return;
  const v = visible(); const i = v.findIndex(x => x.id === c.id);
  const nextId = (v[i + 1] || v[i - 1] || {}).id;
  const target = c.state === state ? 'new' : state;  // pressing again undoes
  const prev = { state: c.state, status: c.status };
  c.state = target; if (target === 'kept') c.status = 'queued';
  S.listSig = ''; renderList(); renderKept(); updateInfo();
  try { Object.assign(c, await api(`/api/jobs/${JOB}/moments/${c.id}`, { state: target })); }
  catch (e) { Object.assign(c, prev); S.listSig = ''; renderList(); renderKept(); updateInfo(); toast(e.message, e.upgrade); return; }
  if (S.tab === 'new' && target !== 'new' && nextId) select(nextId); else updateInfo();
}
$('#keep').onclick = () => decide('kept'); $('#drop').onclick = () => decide('discarded');
async function nudge(which, d) {
  const c = byId(S.cur); if (!c) return;
  const ws = S.job.window[0];
  const s = c.start + ws + (which === 's' ? d : 0), e = c.end + ws + (which === 'e' ? d : 0);
  try { Object.assign(c, await api(`/api/jobs/${JOB}/moments/${c.id}`, { start: s, end: e })); }
  catch (err) { toast(err.message); return; }
  S.listSig = ''; renderList(); updateInfo();
  const pv = await loadPreview(c.id); S.pv = pv;
  if (vid.dataset.src !== pv.url) { vid.src = pv.url; vid.dataset.src = pv.url; }
  vid.currentTime = which === 'e' ? Math.max(pv.start, pv.end - 3) : pv.start; vid.play().catch(() => {});
}
document.querySelector('.trimrow').onclick = e => { const b = e.target.closest('[data-n]'); if (!b) return;
  const [w, d] = b.dataset.n.split(','); nudge(w, +d); };
addEventListener('keydown', e => {
  if (!S.job || S.job.stage !== 'review' || e.target.matches('input,select,textarea') || e.metaKey || e.ctrlKey || e.altKey) return;
  if ($('#cam-modal').style.display === 'flex') return;
  const k = e.key;
  if (k === 'k' || k === 'K') decide('kept');
  else if (k === 'x' || k === 'X' || k === 'd' || k === 'D') decide('discarded');
  else if (k === 'ArrowRight' || k === 'j') step(1);
  else if (k === 'ArrowLeft') step(-1);
  else if (k === ' ') vid.paused ? vid.play() : vid.pause();
  else if (k === '[') nudge('s', -2); else if (k === ']') nudge('s', 2);
  else if (k === ';') nudge('e', -2); else if (k === "'") nudge('e', 2);
  else return;
  e.preventDefault();
});

// ---------- chart ----------
function drawChart() {
  const j = S.job; const wrap = $('#chartwrap'); if (!j.timeline.length) { wrap.style.display = 'none'; return; }
  wrap.style.display = 'block';
  const cv = $('#chart'), dpr = devicePixelRatio || 1, W = cv.clientWidth, H = 64;
  cv.width = W * dpr; cv.height = H * dpr; const g = cv.getContext('2d'); g.scale(dpr, dpr);
  const tl = j.timeline, max = Math.max(...tl, 1), span = j.window[1] - j.window[0], bw = W / tl.length;
  g.fillStyle = '#3a3448';
  tl.forEach((v, i) => { const h = Math.max(1.5, v / max * (H - 12)); g.fillRect(i * bw, H - h, Math.max(1, bw - (bw > 3 ? 1 : 0)), h); });
  for (const c of j.clips) {
    if (c.state === 'discarded') continue;
    const x = c.start / span * W, w = Math.max(2, dur(c) / span * W);
    g.fillStyle = c.id === S.cur ? '#ff4f8b' : c.state === 'kept' ? '#3ddc84' : '#ffffff30';
    g.fillRect(x, 0, w, c.id === S.cur || c.state === 'kept' ? 7 : 3);
  }
  $('#c-start').textContent = fmtT(j.window[0]); $('#c-end').textContent = fmtT(j.window[1]);
  cv.onclick = e => { if (j.mode !== 'fast') return; const t = e.offsetX / W * span;
    const pool = j.clips.filter(c => c.state !== 'discarded');
    const c = pool.reduce((b, c) => !b || Math.abs((c.start + c.end) / 2 - t) < Math.abs((b.start + b.end) / 2 - t) ? c : b, null);
    if (!c) return;
    if (c.state !== S.tab) { S.tab = c.state; document.querySelectorAll('#tabs button').forEach(x => x.classList.toggle('on', x.dataset.t === S.tab)); }
    if (c.flag && $('#hideflag').checked) $('#hideflag').checked = false;
    S.listSig = ''; renderList(); select(c.id); };
}
addEventListener('resize', () => S.job && drawChart());

// ---------- kept ----------
function renderKept() {
  const j = S.job; const kept = j.clips.filter(c => c.state === 'kept').sort((a, b) => a.start - b.start);
  $('#kept').style.display = kept.length ? 'block' : 'none';
  const ready = kept.filter(c => c.status === 'done').length;
  $('#k-count').textContent = `${ready} of ${kept.length} ready`;
  const zip = $('#zip'); zip.href = ready ? `/api/jobs/${j.id}/kept.zip` : '#'; zip.setAttribute('aria-disabled', ready ? 'false' : 'true');
  zip.style.pointerEvents = ready ? '' : 'none';
  const sig = kept.map(c => `${c.id}|${c.status}|${c.file || ''}|${c.error || ''}`).join();
  if (sig === S.keptSig) return; S.keptSig = sig;
  const grid = $('#k-grid'); const ids = new Set(kept.map(c => c.id));
  [...grid.children].forEach(el => { if (!ids.has(el.dataset.id)) el.remove(); });
  kept.forEach((c, i) => {
    let el = grid.querySelector(`[data-id="${c.id}"]`);
    const key = `${c.status}|${c.file || ''}|${c.error || ''}`;
    if (!el) { el = document.createElement('div'); el.className = 'clip'; el.dataset.id = c.id; }
    if (grid.children[i] !== el) grid.insertBefore(el, grid.children[i] || null);
    if (el.dataset.key === key) return;
    el.dataset.key = key;
    const vert = (c.format || '').startsWith('vertical');
    const busy = ['queued', 'downloading', 'captioning', 'rendering', 'pending'].includes(c.status);
    const wait = { queued: 'Queued…', pending: 'Queued…', downloading: 'Fetching HD…', captioning: 'Writing captions…', rendering: 'Making clip…' }[c.status];
    el.innerHTML = `
      <div class="media ${vert ? 'v' : 'h'}">${c.status === 'done'
        ? `<video controls preload="metadata" playsinline poster="/files/${j.id}/${c.thumb}" src="/files/${j.id}/${c.file}"></video>`
        : busy ? `<div class="wait"><div class="spin"></div>${wait}</div>` : `<div class="wait">${c.status === 'error' ? 'Couldn’t make this clip' : 'Not made yet'}</div>`}</div>
      <div class="body">
        <div class="meta"><span class="time">${esc(c.label)}</span><span class="muted">${FMT[c.format] || ''}${c.captioned ? ' · CC' : ''}</span></div>
        ${c.error ? `<div class="cerr">${esc(c.error)}</div>` : ''}
        <div class="actions">
          <a class="dl ${c.status === 'done' ? '' : 'off'}" href="/files/${j.id}/${c.file}?download=1">Download</a>
          <button data-a="remake" ${busy ? 'disabled' : ''}>Re-make</button>
          ${c.format === 'vertical_facecam' ? `<button data-a="cam" ${busy ? 'disabled' : ''}>Webcam</button>` : ''}
          ${j.mode === 'fast' ? `<button data-a="drop" title="Discard" aria-label="Discard clip">✕</button>` : ''}
        </div>
      </div>`;
  });
}
$('#k-grid').onclick = async e => {
  const b = e.target.closest('button'); if (!b) return; const id = b.closest('.clip').dataset.id; const c = byId(id);
  try {
    if (b.dataset.a === 'drop') { c.state = 'discarded'; S.keptSig = ''; renderKept(); await api(`/api/jobs/${JOB}/moments/${id}`, { state: 'discarded' }); }
    if (b.dataset.a === 'remake') { b.disabled = true; await api(`/api/jobs/${JOB}/clips/${id}/recut`, { start: c.source_start, end: c.source_end, format: $('#k-fmt').value }); }
    if (b.dataset.a === 'cam') openCamEditor(c);
  } catch (err) { toast(err.message, err.upgrade); }
  poll();
};
$('#k-fmt').onchange = () => api(`/api/jobs/${JOB}/settings`, { format: $('#k-fmt').value }).catch(e => toast(e.message));
$('#k-caps').onchange = () => api(`/api/jobs/${JOB}/settings`, { captions: $('#k-caps').checked })
  .catch(e => { $('#k-caps').checked = false; toast(e.message, e.upgrade); });
$('#cancel').onclick = () => api(`/api/jobs/${JOB}/cancel`, {}).then(poll).catch(e => toast(e.message));
$('#delete').onclick = async () => {
  if (!confirm('Delete this project and all its clips? This can’t be undone.')) return;
  try { await api(`/api/jobs/${JOB}/delete`, {}); location.href = '/app'; } catch (e) { toast(e.message); }
};

// ---------- webcam box editor ----------
const cam = { clip: null, rect: null, drag: null };
function openCamEditor(c) {
  cam.clip = c; cam.rect = S.job.facecam?.rect ? { ...S.job.facecam.rect } : null;
  $('#cam-img').removeAttribute('src'); $('#cam-box').style.display = 'none';
  $('#cam-loading').style.display = 'flex'; $('#cam-modal').style.display = 'flex';
  $('#cam-img').onload = () => { $('#cam-loading').style.display = 'none'; drawCamBox(); };
  $('#cam-img').onerror = () => { $('#cam-loading').textContent = "Couldn't load a frame for this clip."; };
  $('#cam-img').src = `/api/jobs/${JOB}/clips/${c.id}/frame?t=${Date.now()}`;
}
function drawCamBox() {
  const box = $('#cam-box'); if (!cam.rect) { box.style.display = 'none'; return; }
  Object.assign(box.style, { display: 'block', left: cam.rect.x * 100 + '%', top: cam.rect.y * 100 + '%', width: cam.rect.w * 100 + '%', height: cam.rect.h * 100 + '%' });
}
const camPt = e => { const r = $('#cam-stage').getBoundingClientRect();
  return { x: Math.min(1, Math.max(0, (e.clientX - r.left) / r.width)), y: Math.min(1, Math.max(0, (e.clientY - r.top) / r.height)) }; };
$('#cam-stage').addEventListener('pointerdown', e => { e.preventDefault(); cam.drag = camPt(e); $('#cam-stage').setPointerCapture(e.pointerId); });
$('#cam-stage').addEventListener('pointermove', e => { if (!cam.drag) return; const p = camPt(e), a = cam.drag;
  cam.rect = { x: Math.min(a.x, p.x), y: Math.min(a.y, p.y), w: Math.abs(p.x - a.x), h: Math.abs(p.y - a.y) }; drawCamBox(); });
$('#cam-stage').addEventListener('pointerup', () => { cam.drag = null; });
$('#cam-cancel').onclick = () => { $('#cam-modal').style.display = 'none'; };
$('#cam-save').onclick = async () => {
  const r = cam.rect; if (!r || r.w < 0.03 || r.h < 0.03) { toast('Drag a box around the webcam first.'); return; }
  const rect = { x: +r.x.toFixed(4), y: +r.y.toFixed(4), w: +r.w.toFixed(4), h: +r.h.toFixed(4) };
  const targets = $('#cam-all').checked ? S.job.clips.filter(x => x.state === 'kept' && x.status === 'done' && (x.format === 'vertical_facecam' || x.id === cam.clip.id)) : [cam.clip];
  $('#cam-save').disabled = true;
  try {
    for (const t of targets) await api(`/api/jobs/${JOB}/clips/${t.id}/recut`, { start: t.source_start, end: t.source_end, format: 'vertical_facecam', facecam_rect: rect });
    $('#cam-modal').style.display = 'none'; poll();
  } catch (err) { toast(err.message); }
  finally { $('#cam-save').disabled = false; }
};

poll();
})();
