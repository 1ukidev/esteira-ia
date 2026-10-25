'use strict';

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];

const COLORS = {
  vermelho: '#ef4444', laranja: '#f97316', amarelo: '#facc15', verde: '#22c55e', azul: '#3b82f6',
  roxo: '#a855f7', rosa: '#ec4899', branco: '#f1f5f9', cinza: '#94a3b8', preto: '#1e293b',
};
const COCO_PT = {
  person: 'pessoa', bottle: 'garrafa', cup: 'copo', 'cell phone': 'celular', book: 'livro',
  scissors: 'tesoura', apple: 'maçã', banana: 'banana', orange: 'laranja (fruta)', mouse: 'mouse',
  remote: 'controle', keyboard: 'teclado', laptop: 'notebook', 'teddy bear': 'pelúcia',
  'sports ball': 'bola', spoon: 'colher', fork: 'garfo', knife: 'faca', bowl: 'tigela',
  toothbrush: 'escova', clock: 'relógio', vase: 'vaso', 'wine glass': 'taça', donut: 'rosquinha',
  carrot: 'cenoura', car: 'carrinho', backpack: 'mochila', handbag: 'bolsa', umbrella: 'guarda-chuva',
  sandwich: 'sanduíche', cake: 'bolo', 'hair drier': 'secador', tie: 'gravata', 'potted plant': 'planta', 'traffic light': 'semáforo',
};
const IGNORED = new Set(['dining table', 'bed', 'couch', 'tv', 'refrigerator', 'oven']);
const TF_SCRIPTS = [
  'https://cdn.jsdelivr.net/npm/@tensorflow/tfjs@4.22.0/dist/tf.min.js',
  'https://cdn.jsdelivr.net/npm/@tensorflow-models/coco-ssd@2.2.3/dist/coco-ssd.min.js',
];
const MAX_PARTS = 12;

const ui = {
  grid: [80, 60],
  settings: null,
  state: null,
  trails: new Map(),
  sonar: [],
  rates: [],
  lastRateSample: 0,
  countsKey: '',
  flash: 0,
  dragging: false,
  ai: { model: null, on: false, local: [] },
};

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

function el(tag, props = {}, ...children) {
  const node = Object.assign(document.createElement(tag), props);
  node.append(...children);
  return node;
}

function colorOf(label) {
  if (COLORS[label]) return COLORS[label];
  let hash = 0;
  for (const ch of label) hash = (hash * 31 + ch.charCodeAt(0)) >>> 0;
  return `hsl(${hash % 360} 75% 62%)`;
}

async function api(path, body) {
  const options = body === undefined ? {} : {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  };
  const res = await fetch(path, options);
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail.error || res.statusText);
  }
  return res.status === 204 ? null : res.json();
}

let toastTimer;
function toast(message, error = false) {
  const node = $('#toast');
  node.textContent = message;
  node.className = `toast show${error ? ' error' : ''}`;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (node.className = 'toast'), 2600);
}

function log(text, level = 'info') {
  const time = new Date().toLocaleTimeString('pt-BR');
  const list = $('#log');
  list.prepend(el('li', { className: level }, el('time', { textContent: time }), el('span', { textContent: text })));
  while (list.children.length > 60) list.lastChild.remove();
}

function formatUptime(seconds) {
  const pad = (n) => String(n).padStart(2, '0');
  return `${pad(Math.floor(seconds / 3600))}:${pad(Math.floor(seconds / 60) % 60)}:${pad(seconds % 60)}`;
}

/* ---------- ajustes ---------- */

async function save(changes) {
  try {
    const { applied } = await api('/api/settings', changes);
    Object.assign(ui.settings, applied);
    reflectSettings();
    $('#saved').textContent = 'salvo ✓';
    setTimeout(() => ($('#saved').textContent = ''), 1500);
  } catch (err) {
    toast(`Não foi possível salvar: ${err.message}`, true);
  }
}

function reflectSettings() {
  const s = ui.settings;
  for (const key of ['sensitivity', 'min_area']) {
    $(`#${key}`).value = s[key];
    $(`#out-${key}`).textContent = s[key];
  }
  for (const key of ['sorter', 'sound', 'vflip', 'hmirror']) $(`#${key}`).checked = s[key];
  for (const key of ['servo_rest', 'servo_push', 'push_delay', 'push_ms', 'xclk_mhz']) $(`#${key}`).value = s[key];
  for (const button of $$('#direction button')) button.classList.toggle('on', Number(button.dataset.dir) === s.direction);
  renderRejectTags();
}

function renderRejectTags() {
  const s = ui.settings;
  const seen = Object.keys(ui.state?.counts ?? {});
  const options = [...new Set([...Object.keys(COLORS), ...seen, ...s.reject])];
  $('#reject').replaceChildren(...options.map((name) => {
    const on = s.reject.includes(name);
    const tag = el('button', { className: `tag${on ? ' on' : ''}`, type: 'button' },
      el('span', { className: 'dot', style: `background:${colorOf(name)}` }), name);
    tag.onclick = () => save({ reject: on ? s.reject.filter((n) => n !== name) : [...s.reject, name] });
    return tag;
  }));
}

function bindControls() {
  for (const key of ['sensitivity', 'min_area']) {
    const input = $(`#${key}`);
    input.oninput = () => ($(`#out-${key}`).textContent = input.value);
    input.onchange = () => save({ [key]: Number(input.value) });
  }
  for (const key of ['sorter', 'sound', 'vflip', 'hmirror']) {
    $(`#${key}`).onchange = (e) => save({ [key]: e.target.checked });
  }
  for (const key of ['servo_rest', 'servo_push', 'push_delay', 'push_ms']) {
    $(`#${key}`).onchange = (e) => save({ [key]: Number(e.target.value) });
  }
  $('#xclk_mhz').onchange = async (e) => {
    const requested = Number(e.target.value);
    toast('Reiniciando a câmera…');
    await save({ xclk_mhz: requested });
    if (ui.settings.xclk_mhz !== requested) toast(`${requested} MHz não funcionou; mantido em ${ui.settings.xclk_mhz} MHz`, true);
  };
  for (const button of $$('#direction button')) {
    button.onclick = () => save({ direction: Number(button.dataset.dir) });
  }
  for (const button of $$('[data-post]')) {
    button.onclick = async () => {
      if (button.dataset.confirm && !confirm(button.dataset.confirm)) return;
      try {
        await api(button.dataset.post, {});
        toast(`${button.textContent} ✓`);
      } catch (err) {
        toast(err.message, true);
      }
    };
  }
  for (const button of $$('[data-test]')) {
    button.onclick = () => api('/api/test', { device: button.dataset.test }).catch((err) => toast(err.message, true));
  }

  const trip = () => api('/api/estop', { active: true }).catch((err) => toast(err.message, true));
  $('#estop').onclick = trip;
  document.addEventListener('keydown', (e) => e.key === 'Escape' && trip());
  $('#rearm').onclick = () => api('/api/estop', { active: false }).catch((err) => toast(err.message, true));
  $('#ai-toggle').onclick = toggleAI;
  bindLineDrag();
}

/* ---------- estado ao vivo ---------- */

function connectEvents() {
  const source = new EventSource('/events');
  const link = $('#link');
  const setLink = (online) => {
    link.classList.toggle('ok', online);
    link.lastChild.textContent = online ? 'online' : 'reconectando';
  };
  source.onopen = () => setLink(true);
  source.onerror = () => setLink(false);
  source.addEventListener('state', (e) => render(JSON.parse(e.data)));
  source.addEventListener('count', (e) => onCount(JSON.parse(e.data)));
  source.addEventListener('estop', (e) => $('#alarm').hidden = !JSON.parse(e.data).active);
  source.addEventListener('log', (e) => {
    const { text, level } = JSON.parse(e.data);
    log(text, level);
  });
  source.addEventListener('hello', (e) => {
    const { history } = JSON.parse(e.data);
    $('#parts').replaceChildren();
    if (!history.length) $('#parts').append(el('p', { className: 'empty', textContent: 'Nenhuma peça contada ainda.' }));
    history.forEach((event) => addPart(event, false));
  });
}

function render(state) {
  const previous = ui.state;
  ui.state = state;

  $('#fps').textContent = `${state.fps.toFixed(1)} fps`;
  $('#uptime').textContent = formatUptime(state.up);
  $('#hud-tracks').textContent = `${state.tracks.length} ${state.tracks.length === 1 ? 'objeto' : 'objetos'}`;
  $('#hud-motion').textContent = `movimento ${Math.round(state.coverage * 100)}%`;
  $('#hud-vfps').textContent = `visão ${state.vfps.toFixed(1)} fps`;
  $('#clients').textContent = `${state.clients} conexões · ${(state.mem / 1024 / 1024).toFixed(1)} MB livres${state.rssi ? ` · ${state.rssi} dBm` : ''}`;
  $('#alarm').hidden = !state.estop;

  setKpi('#k-total', state.total, previous?.total);
  setKpi('#k-rate', state.rate);
  setKpi('#k-rejected', state.rejected, previous?.rejected);
  $('#k-reject-pct').textContent = `${state.total ? Math.round((100 * state.rejected) / state.total) : 0}% do total`;
  $('#k-height').textContent = state.sonar ? state.sonar.h.toFixed(1) : '—';
  sampleRate(state.rate);

  updateTrails(state.tracks);
  renderClasses(state.counts);
  renderSonar(state.sonar);
  renderIo(state.io);
}

function setKpi(selector, value, previous) {
  const node = $(selector);
  node.textContent = value;
  if (previous !== undefined && previous !== value) {
    const card = node.parentElement;
    card.classList.remove('bump');
    void card.offsetWidth;
    card.classList.add('bump');
  }
}

function sampleRate(rate) {
  const now = Date.now();
  if (now - ui.lastRateSample < 2000) return;
  ui.lastRateSample = now;
  ui.rates = [...ui.rates, rate].slice(-60);
  const canvas = $('#k-spark');
  const ctx = canvas.getContext('2d');
  const max = Math.max(4, ...ui.rates);
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.beginPath();
  ui.rates.forEach((value, i) => {
    const x = (i / 59) * canvas.width;
    const y = canvas.height - 2 - (value / max) * (canvas.height - 4);
    i ? ctx.lineTo(x, y) : ctx.moveTo(x, y);
  });
  ctx.strokeStyle = '#38d9f5';
  ctx.lineWidth = 2;
  ctx.stroke();
}

function updateTrails(tracks) {
  const alive = new Set();
  for (const [id, x, y, w, h] of tracks) {
    alive.add(id);
    const trail = ui.trails.get(id) ?? [];
    trail.push([x + w / 2, y + h / 2]);
    ui.trails.set(id, trail.slice(-10));
  }
  for (const id of ui.trails.keys()) if (!alive.has(id)) ui.trails.delete(id);
}

function renderClasses(counts) {
  const key = JSON.stringify(counts) + ui.settings?.reject;
  if (key === ui.countsKey) return;
  ui.countsKey = key;
  const entries = Object.entries(counts).sort((a, b) => b[1] - a[1]);
  if (!entries.length) {
    $('#classes').replaceChildren(el('li', { className: 'empty', textContent: 'Aguardando objetos…' }));
    return;
  }
  const max = entries[0][1];
  $('#classes').replaceChildren(...entries.map(([name, count]) => {
    const color = colorOf(name);
    const label = el('span', { className: 'name' }, el('span', { className: 'dot', style: `background:${color}` }), name);
    if (ui.settings?.reject.includes(name)) label.append(el('em', { textContent: 'rejeita' }));
    const meter = el('span', { className: 'meter' }, el('i', { style: `width:${(100 * count) / max}%;background:${color}` }));
    return el('li', {}, label, el('span', { className: 'mono', textContent: count }), meter);
  }));
  renderRejectTags();
}

function renderSonar(sonar) {
  if (!sonar) {
    $('#sonar-text').textContent = 'sem leitura';
    return;
  }
  $('#sonar-text').textContent = `${sonar.cm.toFixed(1)} cm · esteira ${sonar.base.toFixed(1)} cm`;
  const px = Math.min(80, sonar.h * 6);
  const object = $('#object');
  object.setAttribute('y', 100 - px);
  object.setAttribute('height', px);

  ui.sonar = [...ui.sonar, sonar].slice(-150);
  const canvas = $('#sonar-chart');
  const ctx = canvas.getContext('2d');
  const { width, height } = canvas;
  const top = Math.max(...ui.sonar.map((s) => s.base)) * 1.15 || 1;
  const yOf = (cm) => height - 6 - (cm / top) * (height - 12);
  const xOf = (i) => width - ((ui.sonar.length - 1 - i) / 149) * width;
  ctx.clearRect(0, 0, width, height);

  ctx.setLineDash([4, 4]);
  ctx.strokeStyle = '#4b5b6c';
  ctx.beginPath();
  ui.sonar.forEach((s, i) => (i ? ctx.lineTo(xOf(i), yOf(s.base)) : ctx.moveTo(xOf(i), yOf(s.base))));
  ctx.stroke();
  ctx.setLineDash([]);

  ctx.fillStyle = 'rgba(182, 241, 74, 0.25)';
  ui.sonar.forEach((s, i) => {
    if (s.h > 1) ctx.fillRect(xOf(i), yOf(s.base), width / 149 + 1, yOf(s.cm) - yOf(s.base));
  });

  ctx.strokeStyle = '#38d9f5';
  ctx.lineWidth = 2;
  ctx.beginPath();
  ui.sonar.forEach((s, i) => (i ? ctx.lineTo(xOf(i), yOf(s.cm)) : ctx.moveTo(xOf(i), yOf(s.cm))));
  ctx.stroke();
}

function renderIo(io) {
  const lit = io.rgb !== '#000000';
  $('#io-rgb i').style.cssText = lit ? `background:${io.rgb};box-shadow:0 0 18px ${io.rgb}` : '';
  $('#needle').style.transform = `rotate(${io.servo - 90}deg)`;
  $('#io-servo').textContent = `${io.servo}°`;
}

/* ---------- peças contadas ---------- */

function onCount(event) {
  addPart(event, true);
  ui.flash = performance.now();
  const extras = [event.height > 0 ? `${event.height} cm` : null, event.reject ? 'rejeitada' : null].filter(Boolean);
  log(`#${event.n} ${event.label}${extras.length ? ` · ${extras.join(' · ')}` : ''}`, event.reject ? 'alert' : 'count');
}

function addPart(event, capture) {
  const parts = $('#parts');
  parts.querySelector('.empty')?.remove();

  const thumb = el('canvas', { width: 160, height: 160 });
  const ctx = thumb.getContext('2d');
  const feed = $('#feed');
  if (capture && event.box && feed.naturalWidth) {
    const [gw, gh] = ui.grid;
    const sx = feed.naturalWidth / gw;
    const sy = feed.naturalHeight / gh;
    const [x, y, w, h] = event.box;
    const side = Math.max(w * sx, h * sy) * 1.4;
    const cx = (x + w / 2) * sx;
    const cy = (y + h / 2) * sy;
    ctx.drawImage(feed, cx - side / 2, cy - side / 2, side, side, 0, 0, 160, 160);
  } else {
    const gradient = ctx.createRadialGradient(80, 70, 10, 80, 80, 110);
    gradient.addColorStop(0, event.rgb);
    gradient.addColorStop(1, '#0b1016');
    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, 160, 160);
  }

  const meta = [`#${event.n}`, event.height > 0 ? `${event.height} cm` : null, formatUptime(event.t)].filter(Boolean).join(' · ');
  const card = el('article', { className: `part${event.reject ? ' reject' : ''}` }, thumb,
    el('div', {},
      el('b', {}, el('span', { className: 'dot', style: `background:${event.rgb}` }), event.label),
      el('small', { textContent: meta })));
  parts.prepend(card);
  while (parts.children.length > MAX_PARTS) parts.lastChild.remove();
  $('#parts-count').textContent = `${parts.children.length} recentes`;
}

/* ---------- sobreposição do vídeo ---------- */

function draw(now) {
  const canvas = $('#overlay');
  const ctx = canvas.getContext('2d');
  const dpr = window.devicePixelRatio || 1;
  const width = Math.round(canvas.clientWidth * dpr);
  const height = Math.round(canvas.clientHeight * dpr);
  if (canvas.width !== width || canvas.height !== height) Object.assign(canvas, { width, height });
  ctx.clearRect(0, 0, width, height);

  const [gw, gh] = ui.grid;
  const sx = width / gw;
  const sy = height / gh;
  const state = ui.state;

  if (ui.settings) drawLine(ctx, ui.settings.line * width, height, dpr, now);

  const ai = ui.ai.on ? ui.ai.local : state?.ai ?? [];
  ctx.lineWidth = 1.5 * dpr;
  ctx.font = `${11 * dpr}px ui-monospace, monospace`;
  for (const { label, score, box } of ai) {
    const [x, y, w, h] = [box[0] * width, box[1] * height, box[2] * width, box[3] * height];
    ctx.setLineDash([6 * dpr, 4 * dpr]);
    ctx.strokeStyle = '#38d9f5';
    ctx.strokeRect(x, y, w, h);
    ctx.setLineDash([]);
    chip(ctx, `${label} ${Math.round(score * 100)}%`, x, y + h, '#38d9f5', dpr, true);
  }

  for (const [id, gx, gy, gw2, gh2, color, label] of state?.tracks ?? []) {
    const trail = ui.trails.get(id) ?? [];
    ctx.strokeStyle = color;
    ctx.globalAlpha = 0.55;
    ctx.lineWidth = 2 * dpr;
    ctx.beginPath();
    trail.forEach(([tx, ty], i) => (i ? ctx.lineTo(tx * sx, ty * sy) : ctx.moveTo(tx * sx, ty * sy)));
    ctx.stroke();
    ctx.globalAlpha = 1;

    const [x, y, w, h] = [gx * sx, gy * sy, gw2 * sx, gh2 * sy];
    ctx.lineWidth = 2.5 * dpr;
    ctx.strokeStyle = color;
    corners(ctx, x, y, w, h, Math.min(w, h) * 0.3);
    chip(ctx, `#${id} ${label}`, x, y, color, dpr);
  }
  requestAnimationFrame(draw);
}

function drawLine(ctx, x, height, dpr, now) {
  const flash = Math.max(0, 1 - (now - ui.flash) / 600);
  ctx.save();
  ctx.strokeStyle = flash ? `rgba(255,255,255,${0.5 + flash / 2})` : 'rgba(182,241,74,0.9)';
  ctx.lineWidth = (2 + flash * 4) * dpr;
  ctx.setLineDash([10 * dpr, 8 * dpr]);
  ctx.lineDashOffset = -now / 40;
  ctx.beginPath();
  ctx.moveTo(x, 0);
  ctx.lineTo(x, height);
  ctx.stroke();
  ctx.setLineDash([]);
  ctx.fillStyle = 'rgba(182,241,74,0.95)';
  const dir = ui.settings.direction;
  const arrows = dir === 0 ? [-1, 1] : [dir];
  for (const d of arrows) {
    const y = 18 * dpr;
    ctx.beginPath();
    ctx.moveTo(x + d * 4 * dpr, y - 7 * dpr);
    ctx.lineTo(x + d * 14 * dpr, y);
    ctx.lineTo(x + d * 4 * dpr, y + 7 * dpr);
    ctx.fill();
  }
  ctx.restore();
}

function corners(ctx, x, y, w, h, len) {
  ctx.beginPath();
  for (const [px, py, dx, dy] of [[x, y, 1, 1], [x + w, y, -1, 1], [x, y + h, 1, -1], [x + w, y + h, -1, -1]]) {
    ctx.moveTo(px + dx * len, py);
    ctx.lineTo(px, py);
    ctx.lineTo(px, py + dy * len);
  }
  ctx.stroke();
}

function chip(ctx, text, x, y, color, dpr, below = false) {
  const pad = 4 * dpr;
  const h = 16 * dpr;
  const w = ctx.measureText(text).width + pad * 2;
  const top = below ? Math.min(y, ctx.canvas.height - h) : Math.max(0, y - h);
  const left = Math.max(0, Math.min(x, ctx.canvas.width - w));
  ctx.fillStyle = color;
  ctx.fillRect(left, top, w, h);
  ctx.fillStyle = '#0a0e13';
  ctx.fillText(text, left + pad, top + h - 4.5 * dpr);
}

function bindLineDrag() {
  const canvas = $('#overlay');
  const lineX = () => (ui.settings?.line ?? 0.5) * canvas.clientWidth;
  const near = (e) => Math.abs(e.offsetX - lineX()) < 18;
  const update = (e) => {
    ui.settings.line = Math.min(0.95, Math.max(0.05, e.offsetX / canvas.clientWidth));
  };
  canvas.onpointerdown = (e) => {
    if (!ui.settings || !near(e)) return;
    ui.dragging = true;
    canvas.setPointerCapture(e.pointerId);
    update(e);
  };
  canvas.onpointermove = (e) => {
    canvas.style.cursor = ui.dragging || near(e) ? 'ew-resize' : 'default';
    if (ui.dragging) update(e);
  };
  canvas.onpointerup = () => {
    if (!ui.dragging) return;
    ui.dragging = false;
    save({ line: Number(ui.settings.line.toFixed(3)) });
  };
}

/* ---------- IA no navegador (COCO-SSD) ---------- */

function loadScript(src) {
  return new Promise((resolve, reject) => {
    const script = el('script', { src, async: true });
    script.onload = resolve;
    script.onerror = () => reject(new Error(`falha ao carregar ${src}`));
    document.head.append(script);
  });
}

async function toggleAI() {
  const button = $('#ai-toggle');
  const status = $('#ai-status');
  if (ui.ai.on) {
    ui.ai.on = false;
    button.setAttribute('aria-pressed', 'false');
    status.textContent = 'COCO-SSD desligado';
    return;
  }
  try {
    if (!ui.ai.model) {
      status.textContent = 'baixando modelo…';
      for (const src of TF_SCRIPTS) await loadScript(src);
      ui.ai.model = await cocoSsd.load({ base: 'lite_mobilenet_v2' });
    }
    ui.ai.on = true;
    button.setAttribute('aria-pressed', 'true');
    runAI();
  } catch (err) {
    status.textContent = 'IA indisponível (precisa de internet)';
    toast(err.message, true);
  }
}

async function runAI() {
  const feed = $('#feed');
  const scratch = el('canvas');
  const ctx = scratch.getContext('2d', { willReadFrequently: true });
  const status = $('#ai-status');
  while (ui.ai.on) {
    const started = performance.now();
    if (feed.naturalWidth) {
      const { naturalWidth: w, naturalHeight: h } = feed;
      if (scratch.width !== w || scratch.height !== h) Object.assign(scratch, { width: w, height: h });
      ctx.drawImage(feed, 0, 0);
      const predictions = await ui.ai.model.detect(scratch, 8, 0.45);
      const detections = predictions
        .filter((p) => !IGNORED.has(p.class))
        .map((p) => ({
          label: COCO_PT[p.class] ?? p.class,
          score: Number(p.score.toFixed(2)),
          box: [p.bbox[0] / w, p.bbox[1] / h, p.bbox[2] / w, p.bbox[3] / h].map((v) => Number(v.toFixed(3))),
        }));
      ui.ai.local = detections;
      const elapsed = Math.round(performance.now() - started);
      status.textContent = `${detections.length} detecções · ${elapsed} ms`;
      api('/api/ai', { detections }).catch(() => {});
    }
    await sleep(Math.max(100, 350 - (performance.now() - started)));
  }
  ui.ai.local = [];
}

/* ---------- inicialização ---------- */

function startFeed(camera) {
  const feed = $('#feed');
  $('#stage').style.aspectRatio = `${camera.width} / ${camera.height}`;
  feed.onerror = () => setTimeout(() => (feed.src = `/stream?t=${Date.now()}`), 2000);
  feed.src = '/stream';
}

async function init() {
  try {
    const info = await api('/api/settings');
    ui.grid = info.grid;
    ui.settings = info.settings;
    reflectSettings();
    if (info.network) {
      const { host, ip, mode, ssid } = info.network;
      $('#net').textContent = `${host}.local · ${ip}${mode === 'ap' ? ` · rede ${ssid}` : ''}`;
    }
    if (info.camera) startFeed(info.camera);
    else $('#nocam').hidden = false;
    $('#snap').hidden = !info.camera;
    connectEvents();
    bindControls();
    requestAnimationFrame(draw);
  } catch (err) {
    toast('Dispositivo inacessível, tentando de novo…', true);
    setTimeout(init, 3000);
  }
}

init();
