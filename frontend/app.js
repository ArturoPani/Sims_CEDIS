// ═══════════════════════════════════════════════════════════════
//  CEDIS Sim — Lógica principal del frontend
// ═══════════════════════════════════════════════════════════════

// ── Configuración ───────────────────────────────────────────────
const API = '';
const CELL_SIZE = 3;       // píxeles por celda en la imagen de fondo
const POLL_MS = 2000;
const COLORS = { 0: '#1a1a2e', 1: '#2c3e50', 2: '#e65100', 3: '#263238' };
const ROBOT_COLORS = {
  INACTIVO: '#666', A_RECOGER: '#00e676', A_ESTACION: '#ff9100', RETORNO: '#aa00ff'
};

let grid = null;
let gridW = 0, gridH = 0;
let canvas, ctx;
let bgImage = null;
let robotsDB = [];
let lastEstado = null;
let pollingId = null;

// ── Zoom & Pan ──────────────────────────────────────────────────
let zoom = 1;
const ZOOM_MIN = 0.3;
const ZOOM_MAX = 8;
const ZOOM_STEP = 1.15;
let panX = 0, panY = 0;
let isDragging = false;
let dragStartX = 0, dragStartY = 0;
let panStartX = 0, panStartY = 0;

// ── Interpolación suave ─────────────────────────────────────────
let prevPositions = {};    // robot_id → {x, y, estado, pedido_id, ...}
let currPositions = {};    // robot_id → {x, y, estado, pedido_id, ...}
let lerpStart = 0;         // timestamp del último poll
const LERP_DURATION = POLL_MS * 0.85;  // interpolar en 85% del intervalo

// ═══════════════════════════════════════════════════════════════
//  INICIALIZACIÓN
// ═══════════════════════════════════════════════════════════════
window.addEventListener('DOMContentLoaded', async () => {
  canvas = document.getElementById('gridCanvas');
  ctx = canvas.getContext('2d');
  resizeCanvas();
  window.addEventListener('resize', () => { resizeCanvas(); renderFrame(lastEstado?.robots || []); });

  await cargarLayout();
  await cargarRobotsDB();
  iniciarPolling();
  requestAnimationFrame(animationLoop);

  // ── Eventos de mouse para pan ─────────────────────────────────
  canvas.addEventListener('mousedown', (e) => {
    if (e.button !== 0) return;
    isDragging = true;
    dragStartX = e.clientX;
    dragStartY = e.clientY;
    panStartX = panX;
    panStartY = panY;
    canvas.classList.add('dragging');
  });
  window.addEventListener('mousemove', (e) => {
    if (isDragging) {
      panX = panStartX + (e.clientX - dragStartX);
      panY = panStartY + (e.clientY - dragStartY);
      renderFrame(lastEstado?.robots || []);
    }
    mostrarTooltip(e);
  });
  window.addEventListener('mouseup', () => {
    isDragging = false;
    canvas.classList.remove('dragging');
  });
  canvas.addEventListener('mouseleave', () => document.getElementById('tooltip').style.display = 'none');

  // ── Zoom con rueda ────────────────────────────────────────────
  canvas.addEventListener('wheel', (e) => {
    e.preventDefault();
    const rect = canvas.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;

    const oldZoom = zoom;
    if (e.deltaY < 0) zoom = Math.min(ZOOM_MAX, zoom * ZOOM_STEP);
    else              zoom = Math.max(ZOOM_MIN, zoom / ZOOM_STEP);

    const scale = zoom / oldZoom;
    panX = mx - scale * (mx - panX);
    panY = my - scale * (my - panY);

    updateZoomLabel();
    renderFrame(lastEstado?.robots || []);
  }, { passive: false });
});

function resizeCanvas() {
  const panel = document.getElementById('panelCenter');
  canvas.width = panel.clientWidth;
  canvas.height = panel.clientHeight;
}

function updateZoomLabel() {
  document.getElementById('zoomLabel').textContent = `${Math.round(zoom * 100)}%`;
}

function esc() { return document.getElementById('selEscenario').value; }

// ── Zoom buttons ────────────────────────────────────────────────
function zoomIn() {
  const cx = canvas.width / 2, cy = canvas.height / 2;
  const oldZoom = zoom;
  zoom = Math.min(ZOOM_MAX, zoom * ZOOM_STEP);
  const scale = zoom / oldZoom;
  panX = cx - scale * (cx - panX);
  panY = cy - scale * (cy - panY);
  updateZoomLabel();
  renderFrame(lastEstado?.robots || []);
}

function zoomOut() {
  const cx = canvas.width / 2, cy = canvas.height / 2;
  const oldZoom = zoom;
  zoom = Math.max(ZOOM_MIN, zoom / ZOOM_STEP);
  const scale = zoom / oldZoom;
  panX = cx - scale * (cx - panX);
  panY = cy - scale * (cy - panY);
  updateZoomLabel();
  renderFrame(lastEstado?.robots || []);
}

function zoomFit() {
  if (!bgImage) return;
  const pw = canvas.width;
  const ph = canvas.height;
  const imgW = bgImage.width;
  const imgH = bgImage.height;
  zoom = Math.min(pw / imgW, ph / imgH) * 0.95;
  panX = (pw - imgW * zoom) / 2;
  panY = (ph - imgH * zoom) / 2;
  updateZoomLabel();
  renderFrame(lastEstado?.robots || []);
}

function zoomReset() {
  zoom = 1;
  panX = 0; panY = 0;
  updateZoomLabel();
  renderFrame(lastEstado?.robots || []);
}

// ═══════════════════════════════════════════════════════════════
//  LAYOUT
// ═══════════════════════════════════════════════════════════════
async function cargarLayout() {
  try {
    const r = await fetch(`${API}/layout?escenario=${esc()}`);
    const data = await r.json();
    grid = data.grid;
    gridH = data.alto;
    gridW = data.ancho;
    renderGridBackground();
    zoomFit();
    document.getElementById('simInfo').textContent = `Layout: ${gridW}×${gridH}`;
    setStatus(true);
  } catch (e) {
    document.getElementById('simInfo').textContent = 'Error cargando layout';
    setStatus(false);
  }
}

function renderGridBackground() {
  const offscreen = document.createElement('canvas');
  offscreen.width = gridW * CELL_SIZE;
  offscreen.height = gridH * CELL_SIZE;
  const octx = offscreen.getContext('2d');
  for (let y = 0; y < gridH; y++) {
    for (let x = 0; x < gridW; x++) {
      octx.fillStyle = COLORS[grid[y][x]] || COLORS[3];
      octx.fillRect(x * CELL_SIZE, y * CELL_SIZE, CELL_SIZE, CELL_SIZE);
    }
  }
  bgImage = offscreen;
}

// ═══════════════════════════════════════════════════════════════
//  ROBOTS CRUD
// ═══════════════════════════════════════════════════════════════
async function cargarRobotsDB() {
  try {
    const r = await fetch(`${API}/robots?escenario=${esc()}`);
    robotsDB = await r.json();
    renderListaRobots();
  } catch (e) { console.error(e); }
}

function renderListaRobots() {
  const el = document.getElementById('listaRobots');
  if (!robotsDB.length) { el.innerHTML = '<em>Sin robots registrados</em>'; return; }
  el.innerHTML = robotsDB.map(r =>
    `<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px;">
      <span>${r.nombre} (${r.spawn_x},${r.spawn_y})</span>
      <button class="danger" onclick="eliminarRobot(${r.robot_id})" style="padding:2px 8px;">✕</button>
    </div>`
  ).join('');
}

async function crearRobot() {
  const nombre = document.getElementById('inRobotNombre').value || `Robot-${Date.now() % 1000}`;
  const spawn_x = parseInt(document.getElementById('inSpawnX').value) || 0;
  const spawn_y = parseInt(document.getElementById('inSpawnY').value) || 0;
  try {
    await fetch(`${API}/robots`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ nombre, escenario: esc(), spawn_x, spawn_y })
    });
    document.getElementById('inRobotNombre').value = '';
    document.getElementById('inSpawnX').value = '';
    document.getElementById('inSpawnY').value = '';
    await cargarRobotsDB();
  } catch (e) { alert('Error creando robot: ' + e); }
}

async function eliminarRobot(id) {
  try {
    await fetch(`${API}/robots/${id}`, { method: 'DELETE' });
    await cargarRobotsDB();
  } catch (e) { alert('Error eliminando robot: ' + e); }
}

// ═══════════════════════════════════════════════════════════════
//  PEDIDOS
// ═══════════════════════════════════════════════════════════════
async function generarPedidos() {
  const seed = parseInt(document.getElementById('inSeed').value) || 42;
  const cantidad = parseInt(document.getElementById('inCantidad').value) || 20;
  const burst = document.getElementById('chkBurst').checked;
  try {
    const r = await fetch(`${API}/pedidos/generar`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ escenario: esc(), seed, cantidad, burst })
    });
    const data = await r.json();
    document.getElementById('infoPedidos').innerHTML =
      `<span style="color:#00e676;">✓ ${data.pedidos_generados} pedidos generados (seed=${seed})</span>`;
  } catch (e) { alert('Error generando pedidos: ' + e); }
}

// ═══════════════════════════════════════════════════════════════
//  SIMULACIÓN
// ═══════════════════════════════════════════════════════════════
async function iniciarSim() {
  yaGuardado = false;   // reset para nueva simulación
  const ticks = parseInt(document.getElementById('inTicks').value) || 2000;
  const seg = parseFloat(document.getElementById('inSpeed').value) || 0.01;
  const seed = parseInt(document.getElementById('inSeed').value) || 42;
  try {
    const r = await fetch(`${API}/simulacion/iniciar`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ escenario: esc(), seed, ticks, seg_por_tick: seg })
    });
    const data = await r.json();
    if (r.ok) {
      document.getElementById('infoSim').innerHTML =
        `<span style="color:#00e676;">▶ ${data.robots} robots, ${data.pedidos} pedidos, ${data.ticks} ticks</span>`;
    } else {
      document.getElementById('infoSim').innerHTML =
        `<span style="color:#ff5252;">${data.detail}</span>`;
    }
  } catch (e) { alert('Error: ' + e); }
}

async function detenerSim() {
  try {
    await fetch(`${API}/simulacion/detener`, { method: 'POST' });
    document.getElementById('infoSim').innerHTML = '<span style="color:#ff9100;">■ Simulación detenida</span>';
  } catch (e) { alert('Error: ' + e); }
}

let yaGuardado = false;   // evitar guardado duplicado

async function autoGuardarMetricas() {
  if (yaGuardado) return;
  const chk = document.getElementById('chkGuardar');
  if (!chk || !chk.checked) return;
  yaGuardado = true;
  try {
    const nombre = (document.getElementById('inNombreRun').value || '').trim();
    let url = `${API}/simulacion/metricas?guardar=true`;
    if (nombre) url += `&nombre=${encodeURIComponent(nombre)}`;
    const r = await fetch(url);
    const data = await r.json();
    if (r.ok) {
      document.getElementById('infoSim').innerHTML =
        `<span style="color:#00e676;">💾 Métricas guardadas automáticamente (run_id=${data.run_id})</span>`;
    } else {
      document.getElementById('infoSim').innerHTML =
        `<span style="color:#ff5252;">${data.detail}</span>`;
    }
  } catch (e) {
    document.getElementById('infoSim').innerHTML =
      `<span style="color:#ff5252;">Error guardando métricas: ${e}</span>`;
  }
}

// ═══════════════════════════════════════════════════════════════
//  POLLING & RENDER
// ═══════════════════════════════════════════════════════════════
function iniciarPolling() {
  if (pollingId) clearInterval(pollingId);
  pollingId = setInterval(pollEstado, POLL_MS);
}

async function pollEstado() {
  try {
    const r = await fetch(`${API}/simulacion/estado`);
    const data = await r.json();
    lastEstado = data;
    setStatus(true);
    actualizarUI(data);
  } catch (e) {
    setStatus(false);
  }
}

function actualizarUI(data) {
  const tickTxt = data.activo
    ? `Tick ${data.tick} / ${data.ticks_objetivo}  (${data.progreso_pct}%)`
    : (data.finalizado ? `Finalizado — Tick ${data.tick}` : '');
  document.getElementById('txtTick').textContent = tickTxt;

  // Auto-guardar métricas al finalizar si el checkbox está marcado
  if (data.finalizado && !data.activo) {
    autoGuardarMetricas();
  }
  document.getElementById('simInfo').textContent =
    `Layout: ${gridW}×${gridH}  |  ${tickTxt}`;

  // Shift curr → prev, store new target positions for interpolation
  prevPositions = { ...currPositions };
  currPositions = {};
  if (data.robots) {
    for (const r of data.robots) {
      currPositions[r.robot_id] = {
        x: r.pos_x, y: r.pos_y,
        estado: r.estado, pedido_id: r.pedido_id,
        ticks_restantes: r.ticks_restantes, eta_seg: r.eta_seg
      };
    }
  }
  lerpStart = performance.now();

  // Tables update immediately (no interpolation needed)
  renderTablaRobots(data.robots);
  renderTablaPedidos(data.pedidos);
}

// ── Animation loop (60 fps) ─────────────────────────────────────
function animationLoop() {
  const now = performance.now();
  const elapsed = now - lerpStart;
  const t = lerpStart === 0 ? 1 : Math.min(1, elapsed / LERP_DURATION);
  // easeInOutQuad for smooth acceleration/deceleration
  const ease = t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;

  const interpolated = [];
  for (const id in currPositions) {
    const curr = currPositions[id];
    const prev = prevPositions[id] || curr;
    interpolated.push({
      robot_id: parseInt(id),
      pos_x: prev.x + (curr.x - prev.x) * ease,
      pos_y: prev.y + (curr.y - prev.y) * ease,
      estado: curr.estado,
      pedido_id: curr.pedido_id,
      ticks_restantes: curr.ticks_restantes,
      eta_seg: curr.eta_seg,
    });
  }

  renderFrame(interpolated);
  requestAnimationFrame(animationLoop);
}

function renderFrame(robots) {
  if (!bgImage) return;
  ctx.clearRect(0, 0, canvas.width, canvas.height);

  ctx.fillStyle = '#111';
  ctx.fillRect(0, 0, canvas.width, canvas.height);

  ctx.save();
  ctx.translate(panX, panY);
  ctx.scale(zoom, zoom);

  ctx.drawImage(bgImage, 0, 0);

  if (robots) {
    const robotRadius = Math.max(CELL_SIZE * 1.2, 2 / zoom);
    for (const r of robots) {
      ctx.fillStyle = ROBOT_COLORS[r.estado] || '#fff';
      const x = r.pos_x * CELL_SIZE + CELL_SIZE / 2;
      const y = r.pos_y * CELL_SIZE + CELL_SIZE / 2;
      ctx.beginPath();
      ctx.arc(x, y, robotRadius, 0, Math.PI * 2);
      ctx.fill();
      ctx.strokeStyle = '#fff';
      ctx.lineWidth = 0.5 / zoom;
      ctx.stroke();
    }
  }

  ctx.restore();
}

function renderTablaRobots(robots) {
  const tbody = document.getElementById('tbodyRobots');
  if (!robots || !robots.length) { tbody.innerHTML = '<tr><td colspan="6">Sin datos</td></tr>'; return; }
  tbody.innerHTML = robots.map(r => {
    const nombre = robotsDB.find(db => db.spawn_x === r.pos_x && db.spawn_y === r.pos_y)?.nombre || `R-${r.robot_id}`;
    const badgeClass = r.estado === 'INACTIVO' ? 'badge-inactivo'
      : r.estado === 'A_RECOGER' ? 'badge-recoger'
      : r.estado === 'A_ESTACION' ? 'badge-estacion'
      : 'badge-retorno';
    const eta = r.estado === 'INACTIVO' ? '--'
      : r.ticks_restantes === 0 ? 'En destino'
      : `~${r.eta_seg}s (${r.ticks_restantes}t)`;
    return `<tr>
      <td>${r.robot_id}</td>
      <td>${nombre}</td>
      <td>(${r.pos_x}, ${r.pos_y})</td>
      <td><span class="badge ${badgeClass}">${r.estado}</span></td>
      <td>${r.pedido_id ?? '--'}</td>
      <td>${eta}</td>
    </tr>`;
  }).join('');
}

function renderTablaPedidos(pedidos) {
  const tbody = document.getElementById('tbodyPedidos');
  if (!pedidos || !pedidos.length) { tbody.innerHTML = '<tr><td colspan="4">Sin datos</td></tr>'; return; }
  const show = pedidos.slice(0, 100);
  tbody.innerHTML = show.map(p => {
    const badgeClass = `badge-${p.estado}`;
    return `<tr>
      <td>${p.pedido_id}</td>
      <td>${p.anaquel_id}</td>
      <td>${p.estacion_id}</td>
      <td><span class="badge ${badgeClass}">${p.estado}</span></td>
    </tr>`;
  }).join('');
}

// ═══════════════════════════════════════════════════════════════
//  TOOLTIP (zoom/pan aware)
// ═══════════════════════════════════════════════════════════════
function mostrarTooltip(e) {
  if (!lastEstado || !lastEstado.robots || isDragging) return;
  const rect = canvas.getBoundingClientRect();
  const mx = e.clientX - rect.left;
  const my = e.clientY - rect.top;

  const worldX = (mx - panX) / zoom;
  const worldY = (my - panY) / zoom;
  const cellX = Math.floor(worldX / CELL_SIZE);
  const cellY = Math.floor(worldY / CELL_SIZE);

  const hitRadius = Math.max(2, 3 / zoom);
  const robot = lastEstado.robots.find(r =>
    Math.abs(r.pos_x - cellX) <= hitRadius && Math.abs(r.pos_y - cellY) <= hitRadius
  );

  const tooltip = document.getElementById('tooltip');
  if (robot) {
    const nombre = robotsDB.find(db => db.robot_id === robot.robot_id + (robotsDB[0]?.robot_id || 0))?.nombre || `Robot ${robot.robot_id}`;
    const eta = robot.estado === 'INACTIVO' ? 'Inactivo'
      : robot.ticks_restantes === 0 ? 'En destino'
      : `ETA: ~${robot.eta_seg}s (${robot.ticks_restantes} ticks)`;
    tooltip.innerHTML = `<strong>${nombre}</strong><br>
      Estado: ${robot.estado}<br>
      Pos: (${robot.pos_x}, ${robot.pos_y})<br>
      Pedido: ${robot.pedido_id ?? 'Ninguno'}<br>
      ${eta}`;
    tooltip.style.display = 'block';
    tooltip.style.left = (e.clientX + 15) + 'px';
    tooltip.style.top = (e.clientY + 10) + 'px';
  } else {
    tooltip.style.display = 'none';
  }
}

// ═══════════════════════════════════════════════════════════════
//  STATUS
// ═══════════════════════════════════════════════════════════════
function setStatus(ok) {
  const dot = document.getElementById('dotStatus');
  const txt = document.getElementById('txtStatus');
  dot.className = 'status-dot ' + (ok ? 'ok' : 'off');
  txt.textContent = ok ? 'Conectado' : 'Desconectado';
}

// Recargar layout al cambiar escenario
document.getElementById('selEscenario').addEventListener('change', async () => {
  await cargarLayout();
  await cargarRobotsDB();
});
