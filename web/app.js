/* ==========================================================================
   MESA DE CONTROL EDITORIAL - EL TIEMPO
   Lógica de Aplicación, Conexión a APIs y Renderizado de Interfaz
   ========================================================================== */

let rawIncidents = [];
let rawHome = { total_articulos: 0, articulos: [] };
let rawWhitelist = [];

let currentFilter = 'all';
let censoFilter = 'all';
let censoSearch = '';
let isAuditing = false;

// Helpers
function pad(n) {
  return String(n).padStart(3, '0');
}

function escapeHtml(str) {
  if (!str) return '';
  return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function formatearContexto(textoCompleto, palabraErronea) {
  if (!textoCompleto) return '';
  if (!palabraErronea) return escapeHtml(textoCompleto);

  // Escapar caracteres especiales de regex
  const safeWord = palabraErronea.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const regex = new RegExp(`(${safeWord})`, 'gi');
  
  // Resaltar con la clase hl
  const partes = textoCompleto.split(regex);
  return partes.map(parte => {
    if (parte.toLowerCase() === palabraErronea.toLowerCase()) {
      return `<span class="hl">${escapeHtml(parte)}</span>`;
    }
    return escapeHtml(parte);
  }).join('');
}

/* ==========================================================================
   CARGA DE DATOS DESDE LAS APIS DE PYTHON
   ========================================================================== */
async function cargarDatos() {
  try {
    const resInc = await fetch("/api/incidencias");
    if (resInc.ok) {
      rawIncidents = await resInc.json();
    }
  } catch (err) {
    console.error("Error cargando incidencias:", err);
  }

  try {
    const resHome = await fetch("/api/home_audit");
    if (resHome.ok) {
      rawHome = await resHome.json();
    }
  } catch (err) {
    console.error("Error cargando censo:", err);
  }

  try {
    const resWl = await fetch("/api/whitelist");
    if (resWl.ok) {
      const dataWl = await resWl.json();
      rawWhitelist = dataWl.whitelist || [];
    }
  } catch (err) {
    console.error("Error cargando whitelist:", err);
  }

  actualizarKPIs();
  renderQueue();
  renderCensoChips();
  renderCenso();
  renderWhitelist();
}

/* ==========================================================================
   ACTUALIZACIÓN DE MÉTRICAS Y KPIS
   ========================================================================== */
function actualizarKPIs() {
  const pendientes = rawIncidents.filter(i => i.estado === "pendiente");
  const crit = pendientes.filter(i => (i.severidad || "").toUpperCase() === "CRÍTICA").length;
  const med = pendientes.filter(i => (i.severidad || "").toUpperCase() !== "CRÍTICA").length;
  const totalNotas = rawHome.total_articulos || (rawHome.articulos ? rawHome.articulos.length : 0);

  // KPIs superiores
  document.getElementById("kpiNotes").textContent = totalNotas;
  document.getElementById("kpiCrit").textContent = crit;
  document.getElementById("kpiMed").textContent = med;
  document.getElementById("kpiWhitelist").textContent = rawWhitelist.length;
  document.getElementById("btnDictCount").textContent = rawWhitelist.length;

  // Badges de pestañas
  document.getElementById("tabCount").textContent = pendientes.length;
  document.getElementById("tabCensoCount").textContent = totalNotas;

  // Ticker superior
  const tickerNotasEl = document.getElementById("tickerNotas");
  if (tickerNotasEl) tickerNotasEl.textContent = `${totalNotas} NOTAS`;

  // Última hora de auditoría
  if (rawHome.fecha_auditoria) {
    const hora = rawHome.fecha_auditoria.split(" ")[1] || rawHome.fecha_auditoria;
    document.getElementById("kpiTime").textContent = hora;
  }

  // Contadores en filtros de la cola
  document.getElementById("fCountAll").textContent = pendientes.length;
  document.getElementById("fCountCrit").textContent = crit;
  document.getElementById("fCountMed").textContent = med;
  document.getElementById("queueHeaderCount").textContent = `/ ${pendientes.length} REGISTROS`;
  document.getElementById("censoHeaderCount").textContent = `/ ${totalNotas} ARTÍCULOS`;
  document.getElementById("drawerWhitelistMeta").textContent = `Whitelist · ${rawWhitelist.length} términos aprobados`;
}

/* ==========================================================================
   COLA DE INCIDENCIAS (TRIAGE FEED)
   ========================================================================== */
function normalizarIncidencia(i) {
  const sev = (i.severidad || "").toUpperCase() === "CRÍTICA" ? "crit" : "med";
  const campoRaw = (i.campo || "titular").toUpperCase();
  const posRaw = (i.posicion || "").toUpperCase();
  const field = posRaw ? `${campoRaw} ${posRaw}` : campoRaw;
  const ts = i.timestamp ? (i.timestamp.split(" ")[1] || i.timestamp) : "--:--";

  return {
    id: i.id,
    sev: sev,
    field: field,
    section: i.seccion || "Portada General",
    agent: i.tipo_error ? `IA · ${i.tipo_error.toUpperCase()}` : "Centinela RAE",
    url: i.url || "https://www.eltiempo.com",
    ts: ts,
    context: formatearContexto(i.texto_completo, i.palabra_erronea),
    rawText: i.texto_completo,
    bad: i.palabra_erronea || "",
    good: i.correccion || "",
    rationale: i.explicacion || "Falta detectada por el agente corrector ortográfico y tipográfico.",
    estado: i.estado || "pendiente"
  };
}

function renderQueue() {
  const container = document.getElementById("queueList");
  const pendientes = rawIncidents.filter(i => i.estado === "pendiente").map(normalizarIncidencia);

  let filtered = pendientes;
  if (currentFilter === 'crit') {
    filtered = pendientes.filter(i => i.sev === 'crit');
  } else if (currentFilter === 'med') {
    filtered = pendientes.filter(i => i.sev === 'med');
  } else if (currentFilter === 'titular') {
    filtered = pendientes.filter(i => /TITULAR/.test(i.field));
  } else if (currentFilter === 'bajada') {
    filtered = pendientes.filter(i => /BAJADA/.test(i.field));
  } else if (currentFilter === 'seo') {
    filtered = pendientes.filter(i => /SEO|TITLE|META/.test(i.field));
  } else if (currentFilter === 'vineta') {
    filtered = pendientes.filter(i => /BALAZO|VIÑETA/.test(i.field));
  }

  if (filtered.length === 0) {
    container.innerHTML = `
      <div class="empty">
        <div class="empty-mark">
          <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#14532d" stroke-width="1.5" stroke-linecap="round">
            <path d="M20 6L9 17l-5-5"/>
          </svg>
        </div>
        <h3>Portada impecable</h3>
        <p>No hay errores que requieran intervención en esta categoría. Los 5 agentes autónomos continúan monitoreando en tiempo real.</p>
        <div class="meta">Siguiente ciclo automático en 90 segundos</div>
      </div>
    `;
    return;
  }

  container.innerHTML = filtered.map(i => `
    <article class="inc" id="inc-card-${i.id}" data-id="${i.id}">
      <div class="inc-gutter">
        <span class="inc-id">#${pad(i.id)}</span>
        <span class="inc-sev ${i.sev}">${i.sev === 'crit' ? 'CRÍT' : 'MED'}</span>
        <span class="inc-time">${i.ts}</span>
      </div>
      <div class="inc-body">
        <div class="inc-meta">
          <span class="pill field">${escapeHtml(i.field)}</span>
          <span class="arrow">/</span>
          <span class="pill sect">${escapeHtml(i.section)}</span>
          <span class="arrow">/</span>
          <span class="pill agent">⬢ ${escapeHtml(i.agent)}</span>
        </div>
        <a href="${escapeHtml(i.url)}" target="_blank" rel="noopener" class="inc-url" title="Abrir noticia original">
          <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
            <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/>
            <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>
          </svg>
          ${escapeHtml(i.url)}
        </a>
        <div class="inc-context ${i.sev}">${i.context}</div>
        <div class="contrast">
          <span class="lbl">Contraste</span>
          <span class="word bad">${escapeHtml(i.bad)}</span>
          <span class="arr">→</span>
          <span class="word good">${escapeHtml(i.good)}</span>
        </div>
        <div class="rationale">
          <span class="tag">DICTAMEN</span>
          <div>${escapeHtml(i.rationale)}</div>
        </div>
        <div class="inc-actions">
          <button class="btn accept" onclick="resolverIncidencia(${i.id}, 'aceptada', '${escapeHtml(i.bad)}')">
            ✓ Aceptar Corrección
          </button>
          <button class="btn discard" onclick="resolverIncidencia(${i.id}, 'falso_positivo', '${escapeHtml(i.bad)}')">
            ✕ Descartar · Aprender
          </button>
          <a href="${escapeHtml(i.url)}" target="_blank" rel="noopener" class="btn">
            Ver en contexto →
          </a>
        </div>
      </div>
    </article>
  `).join('');
}

// Filtros de la cola
document.querySelectorAll('.filter-bar .fchip').forEach(chip => {
  chip.addEventListener('click', () => {
    document.querySelectorAll('.filter-bar .fchip').forEach(c => c.classList.remove('active'));
    chip.classList.add('active');
    currentFilter = chip.dataset.filter;
    renderQueue();
  });
});

/* ==========================================================================
   RESOLVER INCIDENCIA (ACEPTAR / DESCARTAR WHITELIST)
   ========================================================================== */
async function resolverIncidencia(id, accion, palabra) {
  const card = document.getElementById(`inc-card-${id}`);
  if (card) {
    card.style.transition = 'all .3s ease';
    card.style.opacity = '0';
    card.style.maxHeight = '0';
    card.style.overflow = 'hidden';
  }

  try {
    const res = await fetch("/api/resolver", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id, accion, palabra })
    });

    if (res.ok) {
      const target = rawIncidents.find(i => i.id === id);
      if (target) target.estado = accion;

      if (accion === "aceptada") {
        showToast(`Corrección aprobada (#${pad(id)})`, 'ok');
      } else {
        showToast(`"${palabra}" agregada al Diccionario Editorial`, 'info');
      }

      setTimeout(() => {
        cargarDatos();
      }, 300);
    }
  } catch (err) {
    showToast("Error al procesar decisión: " + err, "warn");
    cargarDatos();
  }
}

/* ==========================================================================
   CENSO INTEGRAL DE LA PORTADA
   ========================================================================== */
function renderCensoChips() {
  const container = document.getElementById("censoSectionsChips");
  if (!container) return;

  const articulos = rawHome.articulos || [];
  const seccionesSet = new Set(["all"]);

  articulos.forEach(a => {
    if (a.seccion) seccionesSet.add(a.seccion);
  });

  let html = `<button class="fchip ${censoFilter === 'all' ? 'active' : ''}" data-censo="all">Todas</button>`;
  seccionesSet.forEach(sec => {
    if (sec !== 'all') {
      const isActive = censoFilter === sec ? 'active' : '';
      html += `<button class="fchip ${isActive}" data-censo="${escapeHtml(sec)}">${escapeHtml(sec)}</button>`;
    }
  });

  container.innerHTML = html;

  container.querySelectorAll('[data-censo]').forEach(chip => {
    chip.addEventListener('click', () => {
      container.querySelectorAll('[data-censo]').forEach(c => c.classList.remove('active'));
      chip.classList.add('active');
      censoFilter = chip.dataset.censo;
      renderCenso();
    });
  });
}

function renderCenso() {
  const grid = document.getElementById("censoGrid");
  const articulos = rawHome.articulos || [];

  let filtered = articulos;
  if (censoFilter !== 'all') {
    filtered = filtered.filter(a => a.seccion === censoFilter);
  }

  if (censoSearch) {
    const q = censoSearch.toLowerCase();
    filtered = filtered.filter(a =>
      (a.titular && a.titular.toLowerCase().includes(q)) ||
      (a.bajada && a.bajada.toLowerCase().includes(q)) ||
      (a.seccion && a.seccion.toLowerCase().includes(q))
    );
  }

  if (filtered.length === 0) {
    grid.innerHTML = `
      <div class="empty" style="grid-column:1/-1;border:none;border-top:1px solid var(--ink)">
        <div class="empty-mark" style="border-color:var(--navy)">
          <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="#1e3a5f" stroke-width="1.5" stroke-linecap="round">
            <circle cx="11" cy="11" r="8"/>
            <path d="M21 21l-4.3-4.3"/>
          </svg>
        </div>
        <h3>Sin resultados</h3>
        <p>No se encontraron artículos que coincidan con la búsqueda o filtro en la portada actual.</p>
      </div>
    `;
    return;
  }

  grid.innerHTML = filtered.map(a => {
    const tieneIncidencias = a.estado === "con_incidencia" || (a.incidencias && a.incidencias.length > 0);
    let statusClass = "clean";
    let statusText = "Limpio";

    if (tieneIncidencias) {
      const tieneCritica = a.incidencias && a.incidencias.some(inc => (inc.severidad || "").toUpperCase() === "CRÍTICA");
      statusClass = tieneCritica ? "crit" : "warn";
      statusText = tieneCritica ? "Crítico" : "Observación";
    }

    const bulletsHtml = (a.vinetas && a.vinetas.length > 0)
      ? `<ul class="news-bullets">${a.vinetas.map(v => `<li>• ${escapeHtml(v)}</li>`).join('')}</ul>`
      : '';

    const hora = a.timestamp ? (a.timestamp.split(" ")[1] || a.timestamp) : "--:--";

    return `
      <article class="news ${statusClass}">
        <div class="news-top">
          <span class="news-sect">${escapeHtml(a.seccion || "Portada")} · ${escapeHtml(a.posicion || "TITULAR")}</span>
          <span class="news-stat ${statusClass}"><span class="dot"></span>${statusText}</span>
        </div>
        <h3 class="news-title">
          <a href="${escapeHtml(a.url || '#')}" target="_blank" rel="noopener">
            ${escapeHtml(a.titular || "Sin titular")}
          </a>
        </h3>
        ${a.bajada ? `<p class="news-bajada">${escapeHtml(a.bajada)}</p>` : ''}
        ${bulletsHtml}
        <div class="news-foot">
          <span>⏱ ${hora}</span>
          ${tieneIncidencias ? `<span style="color:var(--red);font-weight:600">⚠ ${a.incidencias ? a.incidencias.length : 1} falta(s)</span>` : `<span>✔ Auditada</span>`}
          <a href="${escapeHtml(a.url || '#')}" target="_blank" rel="noopener" style="margin-left:auto;color:var(--navy);font-weight:600">
            eltiempo.com ↗
          </a>
        </div>
      </article>
    `;
  }).join('');
}

// Buscador con atajo ⌘K / Ctrl+K
document.getElementById('searchInput').addEventListener('input', e => {
  censoSearch = e.target.value.trim();
  renderCenso();
});

document.addEventListener('keydown', e => {
  if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
    e.preventDefault();
    document.getElementById('tab-btn-censo').click();
    setTimeout(() => document.getElementById('searchInput').focus(), 100);
  }
});

/* ==========================================================================
   DRAWER: DICCIONARIO EDITORIAL (WHITELIST)
   ========================================================================== */
const drawer = document.getElementById('drawer');
const overlay = document.getElementById('overlay');

document.getElementById('openDict').addEventListener('click', () => {
  drawer.classList.add('open');
  overlay.classList.add('open');
});

function closeDrawer() {
  drawer.classList.remove('open');
  overlay.classList.remove('open');
}

document.getElementById('closeDict').addEventListener('click', closeDrawer);
overlay.addEventListener('click', closeDrawer);

function renderWhitelist(filtro = '') {
  const container = document.getElementById('wlList');
  const palabras = rawWhitelist.filter(w => w.toLowerCase().includes(filtro.toLowerCase()));

  if (palabras.length === 0) {
    container.innerHTML = `<div class="empty" style="padding:30px;border:none"><p>Sin términos coincidentes en el diccionario.</p></div>`;
    return;
  }

  container.innerHTML = palabras.map((w, i) => `
    <div class="wl-item">
      <span class="wl-idx mono">${String(i + 1).padStart(2, '0')}</span>
      <span class="wl-word">${escapeHtml(w)}</span>
      <span class="wl-cat">EXCEPCIÓN</span>
      <button class="wl-rm" title="Eliminar del diccionario" onclick="eliminarPalabraWhitelist('${escapeHtml(w)}')">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
          <path d="M18 6L6 18M6 6l12 12"/>
        </svg>
      </button>
    </div>
  `).join('');
}

document.getElementById('wlSearch').addEventListener('input', e => {
  renderWhitelist(e.target.value);
});

async function agregarPalabraWhitelist() {
  const input = document.getElementById('addWordInput');
  const pal = input.value.trim().toLowerCase();
  if (!pal) return;

  try {
    const res = await fetch("/api/whitelist/add", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ palabra: pal })
    });
    if (res.ok) {
      showToast(`"${pal}" añadida al diccionario`, 'ok');
      input.value = '';
      cargarDatos();
    }
  } catch (err) {
    showToast("Error al agregar: " + err, 'warn');
  }
}

document.getElementById('addWordBtn').addEventListener('click', agregarPalabraWhitelist);
document.getElementById('addWordInput').addEventListener('keydown', e => {
  if (e.key === 'Enter') agregarPalabraWhitelist();
});

async function eliminarPalabraWhitelist(palabra) {
  try {
    const res = await fetch("/api/whitelist/remove", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ palabra })
    });
    if (res.ok) {
      showToast(`"${palabra}" eliminada del diccionario`, 'info');
      cargarDatos();
    }
  } catch (err) {
    showToast("Error al eliminar: " + err, 'warn');
  }
}

/* ==========================================================================
   BOTÓN DE AUDITORÍA FORZADA EN VIVO
   ========================================================================== */
document.getElementById('auditBtn').addEventListener('click', async () => {
  if (isAuditing) return;
  isAuditing = true;

  const btn = document.getElementById('auditBtn');
  btn.style.pointerEvents = 'none';
  btn.innerHTML = '◌ Auditando Portada…';

  showToast('Iniciando auditoría profunda de la portada de El Tiempo...', 'info');

  try {
    const res = await fetch("/api/trigger", { method: "POST" });
    if (res.ok) {
      const data = await res.json();
      showToast(data.mensaje || 'Auditoría completada exitosamente', 'ok');
      await cargarDatos();
    } else {
      showToast('Error en la llamada de auditoría', 'warn');
    }
  } catch (err) {
    showToast('Error de conexión durante la auditoría: ' + err, 'warn');
  } finally {
    isAuditing = false;
    btn.innerHTML = '⚡ Auditar Portada';
    btn.style.pointerEvents = 'auto';
  }
});

/* ==========================================================================
   PESTAÑAS DE NAVEGACIÓN
   ========================================================================== */
document.querySelectorAll('.tab').forEach(tab => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
    tab.classList.add('active');
    document.getElementById('view-' + tab.dataset.tab).classList.add('active');
  });
});

/* ==========================================================================
   TOASTS DE NOTIFICACIÓN
   ========================================================================== */
function showToast(msg, type = 'info') {
  const wrap = document.getElementById('toasts');
  const t = document.createElement('div');
  t.className = `toast ${type}`;
  t.innerHTML = `<span style="font-family:'JetBrains Mono';font-size:10px;letter-spacing:0.1em;color:var(--ink-4)">${type.toUpperCase()}</span> ${escapeHtml(msg)}`;
  wrap.appendChild(t);

  setTimeout(() => {
    t.style.transition = 'all .25s ease';
    t.style.opacity = '0';
    t.style.transform = 'translateX(40px)';
    setTimeout(() => t.remove(), 250);
  }, 3400);
}

/* ==========================================================================
   FECHA Y HORA EN VIVO
   ========================================================================== */
function actualizarReloj() {
  const now = new Date();
  const timeStr = now.toTimeString().slice(0, 8);
  document.getElementById('tTime').textContent = timeStr;
}

const months = ['ENE', 'FEB', 'MAR', 'ABR', 'MAY', 'JUN', 'JUL', 'AGO', 'SEP', 'OCT', 'NOV', 'DIC'];
const today = new Date();
document.getElementById('tDate').textContent = `${String(today.getDate()).padStart(2, '0')} ${months[today.getMonth()]} ${today.getFullYear()}`;

setInterval(actualizarReloj, 1000);
actualizarReloj();

// Carga inicial y sondeo periódico cada 20 segundos
cargarDatos();
setInterval(cargarDatos, 20000);
