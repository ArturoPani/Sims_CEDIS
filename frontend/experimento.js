/* ═══════════════════════════════════════════════════════════════
   CEDIS Sim — Experimento Rápido (JS)
   ═══════════════════════════════════════════════════════════════ */

// ── Métricas y sus labels / dirección (menor=mejor, mayor=mejor, neutral) ──
const METRICAS = [
  { key: "pedidos_completados",            label: "Pedidos completados",          dir: "up"   },
  { key: "throughput_pedidos_por_1000_ticks", label: "Throughput /1000 ticks",    dir: "up"   },
  { key: "tiempo_promedio_pedido_ticks",   label: "Tiempo prom. pedido (ticks)",  dir: "down" },
  { key: "tiempo_promedio_espera_ticks",   label: "Tiempo prom. espera (ticks)",  dir: "down" },
  { key: "utilizacion_promedio",           label: "Utilización promedio",         dir: "up"   },
  { key: "distancia_total_celdas",         label: "Distancia total (celdas)",     dir: "down" },
  { key: "colisiones_vertice",             label: "Colisiones vértice",           dir: "down" },
  { key: "intercambios_arista",            label: "Intercambios arista",          dir: "down" },
  { key: "deadlock",                       label: "Deadlocks",                    dir: "down" },
  { key: "eventos_alto",                   label: "Eventos de alto",              dir: "down" },
  { key: "relevos",                        label: "Relevos",                      dir: "neutral" },
];

let resultadoA = null;
let resultadoB = null;
let chart = null;

// ── Init ────────────────────────────────────────────────────────

document.addEventListener("DOMContentLoaded", async () => {
  await cargarEscenarios();
});

async function cargarEscenarios() {
  try {
    const resp = await fetch("/layout/escenarios");
    if (!resp.ok) return;
    const lista = await resp.json();
    const maxRobotsMap = {};
    for (const sel of [document.getElementById("escA"), document.getElementById("escB")]) {
      sel.innerHTML = "";
      lista.forEach((e, i) => {
        const opt = document.createElement("option");
        opt.value = e.value;
        opt.textContent = e.label;
        if (i === 0) opt.selected = true;
        sel.appendChild(opt);
        if (e.max_robots != null) maxRobotsMap[e.value] = e.max_robots;
      });
    }
    // Default: B selects the second scenario if available
    const selB = document.getElementById("escB");
    if (lista.length > 1) selB.value = lista[1].value;

    // Track max_robots per scenario
    function actualizarMaxRobots(lado) {
      const esc = document.getElementById(`esc${lado}`).value;
      const input = document.getElementById(`robots${lado}`);
      const max = maxRobotsMap[esc];
      if (max != null) {
        input.max = max;
        if (parseInt(input.value) > max) input.value = max;
      }
    }
    for (const lado of ["A", "B"]) {
      actualizarMaxRobots(lado);
      document.getElementById(`esc${lado}`).addEventListener("change", () => actualizarMaxRobots(lado));
    }
  } catch (e) {
    console.error("Error cargando escenarios", e);
  }
}

// ── Leer parámetros de una sim ──────────────────────────────────

function leerParams(lado) {
  return {
    escenario:   document.getElementById(`esc${lado}`).value,
    num_robots:  parseInt(document.getElementById(`robots${lado}`).value) || 5,
    seed:        parseInt(document.getElementById(`seed${lado}`).value) || 42,
    num_pedidos: parseInt(document.getElementById(`pedidos${lado}`).value) || 300,
    ticks:       parseInt(document.getElementById(`ticks${lado}`).value) || 10000,
    burst:       document.getElementById(`burst${lado}`).checked,
    guardar:     document.getElementById(`guardar${lado}`).checked,
    nombre:      document.getElementById(`nombre${lado}`).value || null,
  };
}

// ── Llamar al endpoint ──────────────────────────────────────────

async function ejecutarExperimento(params) {
  const resp = await fetch("/experimento/correr", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }));
    const detail = err.detail;
    const msg = Array.isArray(detail)
      ? detail.map(e => (e.loc ? e.loc.slice(1).join(".") + ": " : "") + e.msg).join(" | ")
      : (detail || "Error desconocido");
    throw new Error(msg);
  }
  return await resp.json();
}

// ── Botones ─────────────────────────────────────────────────────

function setStatus(msg, cls) {
  const el = document.getElementById("statusMsg");
  el.textContent = msg;
  el.className = "status-msg " + (cls || "");
}

function setButtonsEnabled(enabled) {
  document.getElementById("btnCorrer").disabled = !enabled;
  document.getElementById("btnCorrerA").disabled = !enabled;
  document.getElementById("btnCorrerB").disabled = !enabled;
}

async function correrAmbas() {
  setButtonsEnabled(false);
  setStatus("⏳ Corriendo Simulación A…", "running");

  try {
    resultadoA = await ejecutarExperimento(leerParams("A"));
    setStatus("⏳ Corriendo Simulación B…", "running");
    resultadoB = await ejecutarExperimento(leerParams("B"));
    setStatus("✅ Ambas simulaciones completadas.", "ok");
    mostrarResultados();
  } catch (e) {
    setStatus("❌ " + e.message, "err");
  } finally {
    setButtonsEnabled(true);
  }
}

async function correrUna(lado) {
  setButtonsEnabled(false);
  setStatus(`⏳ Corriendo Simulación ${lado}…`, "running");

  try {
    const res = await ejecutarExperimento(leerParams(lado));
    if (lado === "A") resultadoA = res; else resultadoB = res;
    setStatus(`✅ Simulación ${lado} completada.`, "ok");
    if (resultadoA && resultadoB) mostrarResultados();
    else mostrarResultadoUnico(lado, res);
  } catch (e) {
    setStatus("❌ " + e.message, "err");
  } finally {
    setButtonsEnabled(true);
  }
}

// ── Formateo ────────────────────────────────────────────────────

function fmt(val) {
  if (val == null) return "—";
  if (typeof val === "number") {
    if (Number.isInteger(val)) return val.toLocaleString("es-MX");
    return val.toLocaleString("es-MX", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }
  return String(val);
}

function delta(a, b) {
  if (a == null || b == null) return { text: "—", cls: "neutral" };
  const diff = b - a;
  if (diff === 0) return { text: "0", cls: "neutral" };
  const sign = diff > 0 ? "+" : "";
  return { text: sign + fmt(diff), cls: "neutral" };
}

function deltaClass(a, b, dir) {
  if (a == null || b == null || a === b) return "neutral";
  // "better" means B is better than A
  if (dir === "up")   return b > a ? "better" : "worse";
  if (dir === "down") return b < a ? "better" : "worse";
  return "neutral";
}

// ── Mostrar tabla + gráfica ─────────────────────────────────────

function mostrarResultados() {
  const section = document.getElementById("resultsSection");
  section.classList.add("visible");

  const tbody = document.getElementById("tbodyResultados");
  tbody.innerHTML = "";

  const labelsChart = [];
  const valuesA = [];
  const valuesB = [];

  for (const m of METRICAS) {
    const va = resultadoA[m.key];
    const vb = resultadoB[m.key];
    const d = delta(va, vb);
    const cls = deltaClass(va, vb, m.dir);

    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${m.label}</td>
      <td>${fmt(va)}</td>
      <td>${fmt(vb)}</td>
      <td class="${cls}">${d.text}</td>
    `;
    tbody.appendChild(tr);

    // For chart: only numeric non-null, skip very large values compared to others
    if (va != null && vb != null && typeof va === "number") {
      labelsChart.push(m.label);
      valuesA.push(va);
      valuesB.push(vb);
    }
  }

  renderChart(labelsChart, valuesA, valuesB);
  mostrarHeatmapsComparacion(resultadoA, resultadoB);
}

function mostrarResultadoUnico(lado, res) {
  const section = document.getElementById("resultsSection");
  section.classList.add("visible");

  const tbody = document.getElementById("tbodyResultados");
  tbody.innerHTML = "";

  for (const m of METRICAS) {
    const val = res[m.key];
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${m.label}</td>
      <td>${lado === "A" ? fmt(val) : "—"}</td>
      <td>${lado === "B" ? fmt(val) : "—"}</td>
      <td class="neutral">—</td>
    `;
    tbody.appendChild(tr);
  }

  mostrarHeatmapUnico(lado, res);
}

// ── Chart.js ────────────────────────────────────────────────────

function renderChart(labels, dataA, dataB) {
  const ctx = document.getElementById("chartComparacion").getContext("2d");

  if (chart) chart.destroy();

  // Normalize: each metric scaled 0-100 relative to max(A,B) for that metric
  const normA = [];
  const normB = [];
  for (let i = 0; i < labels.length; i++) {
    const maxVal = Math.max(Math.abs(dataA[i]), Math.abs(dataB[i]), 1);
    normA.push((dataA[i] / maxVal) * 100);
    normB.push((dataB[i] / maxVal) * 100);
  }

  chart = new Chart(ctx, {
    type: "bar",
    data: {
      labels,
      datasets: [
        {
          label: "Sim A",
          data: normA,
          backgroundColor: "rgba(0, 212, 255, 0.7)",
          borderColor: "#00d4ff",
          borderWidth: 1,
        },
        {
          label: "Sim B",
          data: normB,
          backgroundColor: "rgba(255, 171, 64, 0.7)",
          borderColor: "#ffab40",
          borderWidth: 1,
        },
      ],
    },
    options: {
      responsive: true,
      plugins: {
        title: {
          display: true,
          text: "Comparación normalizada (% del máximo)",
          color: "#00d4ff",
          font: { size: 13 },
        },
        legend: {
          labels: { color: "#e0e0e0", font: { size: 11 } },
        },
        tooltip: {
          callbacks: {
            label: function(ctx) {
              const idx = ctx.dataIndex;
              const raw = ctx.datasetIndex === 0 ? dataA[idx] : dataB[idx];
              return `${ctx.dataset.label}: ${fmt(raw)} (${ctx.parsed.y.toFixed(1)}%)`;
            },
          },
        },
      },
      scales: {
        x: {
          ticks: { color: "#aaa", font: { size: 10 }, maxRotation: 45 },
          grid: { color: "#0f346033" },
        },
        y: {
          ticks: { color: "#aaa", callback: v => v + "%" },
          grid: { color: "#0f346033" },
          title: { display: true, text: "% del máximo", color: "#888" },
        },
      },
    },
  });
}

// ── Heatmaps ──────────────────────────────────────────────
let _heatmapTipo = "visitas";

function mostrarHeatmapsComparacion(resA, resB) {
  const sec = document.getElementById("heatmapExpSection");
  const grid = document.getElementById("heatmapExpGrid");
  const tieneA = resA && resA.heatmaps;
  const tieneB = resB && resB.heatmaps;
  if (!tieneA && !tieneB) { sec.style.display = "none"; return; }
  sec.style.display = "block";
  _heatmapTipo = "visitas";
  document.querySelectorAll("#heatmapExpSection .hm-tab").forEach((t, i) => t.classList.toggle("active", i === 0));
  _renderHeatmapGrid(grid, resA, resB, _heatmapTipo);
}

function mostrarHeatmapUnico(lado, res) {
  const sec = document.getElementById("heatmapExpSection");
  const grid = document.getElementById("heatmapExpGrid");
  if (!res || !res.heatmaps) { sec.style.display = "none"; return; }
  sec.style.display = "block";
  _heatmapTipo = "visitas";
  document.querySelectorAll("#heatmapExpSection .hm-tab").forEach((t, i) => t.classList.toggle("active", i === 0));
  const resA = lado === "A" ? res : null;
  const resB = lado === "B" ? res : null;
  _renderHeatmapGrid(grid, resA, resB, _heatmapTipo);
}

function _renderHeatmapGrid(container, resA, resB, tipo) {
  const ts = Date.now();
  const cards = [];
  if (resA && resA.heatmaps) cards.push({ label: "Sim A", url: resA.heatmaps[tipo] });
  if (resB && resB.heatmaps) cards.push({ label: "Sim B", url: resB.heatmaps[tipo] });
  container.innerHTML = cards.map(c =>
    `<div class="hm-card"><div class="hm-card-label">${c.label}</div><img src="${c.url}?t=${ts}" class="hm-img" alt="Heatmap ${c.label}"></div>`
  ).join("");
}

function switchHeatmapExp(tipo, btn) {
  _heatmapTipo = tipo;
  document.querySelectorAll("#heatmapExpSection .hm-tab").forEach(t => t.classList.remove("active"));
  if (btn) btn.classList.add("active");
  _renderHeatmapGrid(
    document.getElementById("heatmapExpGrid"),
    resultadoA,
    resultadoB,
    tipo
  );
}
