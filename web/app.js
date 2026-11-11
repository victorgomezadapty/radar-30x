const LANG = document.documentElement.lang === "es" ? "es" : "en";
const T = (window.RADAR_I18N && (window.RADAR_I18N[LANG] || window.RADAR_I18N.en)) || {};
const LOCALE = LANG === "es" ? "es" : "en";

function fill(s, vars) {
  return String(s ?? "").replace(/\{(\w+)\}/g, (_, k) => String(vars[k] ?? ""));
}

const SENALES = {
  fuerza: [T.sig_fuerza, T.sig_fuerza_help],
  aceleracion: [T.sig_aceleracion, T.sig_aceleracion_help],
  temprano: [T.sig_temprano, T.sig_temprano_help],
  multired: [T.sig_multired, T.sig_multired_help],
  frescura: [T.sig_frescura, T.sig_frescura_help],
};
const REDES = { youtube: "YouTube", reddit: "Reddit", instagram: "Instagram", linkedin: "LinkedIn", tiktok: "TikTok", hn: "Hacker News" };
const VIAS = { api: "API", rss: "RSS", busqueda_web: T.via_web, manual: T.via_manual, comunidad: T.via_community };
const GANCHOS = T.hooks || {};
const FORMATOS = T.formats || {};
const PASOS = T.steps || [];
const ETAPAS = {
  emergente: T.stage_emergente,
  creciendo: T.stage_creciendo,
  pico: T.stage_pico,
  saturado: T.stage_saturado,
};
const etapaLabel = id => ETAPAS[id] || id;

let DATA = window.RADAR_DATA || {}, SECTORES = [], servidor = false, MODO = "estatico", REQUIERE_CLAVE = false, USO = null;
let sectorInicio = null, libre = false, sector = null, pesos = {}, abiertos = new Set(), tab = "tendencias";

const $ = id => document.getElementById(id);
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const usd = v => v == null ? T.missing_amount : "$" + (v === 0 ? "0" : v < 0.01 ? v.toFixed(4) : v < 1 ? v.toFixed(3) : v.toFixed(2));
const fecha = t => t ? new Date(t * 1000).toLocaleDateString(LOCALE, { day: "numeric", month: "short" }) : T.no_date;
const pct = v => Math.round((v || 0) * 100);
function guardar(k, v) { try { localStorage.setItem(k, v); } catch (e) {} }
function leer(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }
// Instagram manda a su página de inicio si no hay sesión; la versión "embed" del post se ve sin iniciar sesión
function enlace(url) {
  const m = String(url || "").match(/^(https?:\/\/(?:www\.)?instagram\.com\/(?:p|reel|reels)\/[A-Za-z0-9_-]+)/);
  return m ? m[1] + "/embed/captioned/" : url;
}
const slug = t => t.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "").slice(0, 40);
function toast(t) { const d = document.createElement("div"); d.className = "toast"; d.textContent = t; document.body.appendChild(d); setTimeout(() => d.remove(), 1800); }
async function copiar(texto) {
  try { await navigator.clipboard.writeText(texto); }
  catch (e) { const ta = document.createElement("textarea"); ta.value = texto; document.body.appendChild(ta); ta.select(); document.execCommand("copy"); ta.remove(); }
  toast(T.copied);
}

function syncLangLinks() {
  const h = location.hash || "";
  const en = $("lang-en"), es = $("lang-es");
  if (en) en.href = "/" + h;
  if (es) es.href = "/es/" + h;
}

async function cargarDatos() {
  if (MODO === "local") { const d = await fetch("/api/datos", { cache: "no-store" }); if (d.ok) DATA = await d.json(); }
  else if (MODO === "remoto") { const d = await fetch("/datos.json?t=" + Date.now(), { cache: "no-store" }); if (d.ok) DATA = await d.json(); }
}

async function init() {
  try {
    const r = await fetch("/api/estado", { cache: "no-store" });
    const e = r.ok || r.status === 500 ? await r.json() : null;
    if (e && e.modo === "local") MODO = "local";
    else if (e && e.modo === "remoto" && !(e.error || "").startsWith("Faltan")) MODO = "remoto";
    if (e) { REQUIERE_CLAVE = !!e.requiereClave; USO = e.uso || null; }
  } catch (e) {}
  try {
    if (MODO === "local") SECTORES = await (await fetch("/api/sectores", { cache: "no-store" })).json();
    else if (MODO === "remoto") SECTORES = await (await fetch("/sectores.json?t=" + Date.now(), { cache: "no-store" })).json();
  } catch (e) { SECTORES = []; }
  await cargarDatos().catch(() => {});
  if (!SECTORES.length) SECTORES = Object.keys(DATA).map(id => ({ id, nombre: DATA[id].nombre, redes: Object.keys(REDES).map(r => ({
    id: r, nombre: REDES[r], activa: true, disponible: (DATA[id].redes_elegidas || []).includes(r), con_metricas: ["youtube", "hn"].includes(r), via: "" })) }));
  servidor = MODO !== "estatico";
  SECTORES.sort((a, b) => (b.id === "ia_latam") - (a.id === "ia_latam") || (b.id === "fitness") - (a.id === "fitness"));
  sectorInicio = SECTORES.find(s => s.id === leer("radar-sector"))?.id || SECTORES[0]?.id;

  $("glosario-ganchos").innerHTML = Object.values(GANCHOS).map(([n, d, ej]) => `<li><b>${esc(n)}</b><span class="nota">${esc(d)}. ${esc(ej)}</span></li>`).join("");
  $("ir-landing").onclick = $("nav-landing").onclick = () => mostrar("landing");
  $("nav-correr").onclick = $("cta-probar").onclick = $("cta-probar-2").onclick = $("nueva-corrida").onclick = () => mostrar("correr");
  $("nav-res").onclick = $("cta-ultima").onclick = () => abrirResultados(sector || sectorInicio);
  $("correr").onclick = correr;
  $("tabs").onclick = e => { const b = e.target.closest("button"); if (b) cambiarTab(b.dataset.t); };
  $("r-costo").onclick = () => cambiarTab("costo");
  $("reset").onclick = () => { pesos = { ...DATA[sector].pesos }; pintarPesos(); pintarTendencias(); };
  $("pago-actual").oninput = pintarAhorro;
  $("carga-cerrar").onclick = cerrarCarga;
  $("cta-ultima").classList.toggle("oculto", !Object.keys(DATA).length);
  pintarDemo();
  observarRevelados();
  pintarCorrer();
  const h = location.hash;
  if (h.startsWith("#resultados") && DATA[sectorInicio]) {  // #resultados/viene abre esa pestaña directo
    const t = h.split("/")[1];
    if (["tendencias", "viene", "ideas", "origen", "costo"].includes(t)) tab = t;
    abrirResultados(sectorInicio);
  }
  else if (h === "#correr") mostrar("correr");
  syncLangLinks();
  if (servidor) seguirProgreso(true);
}

/* ---------- movimiento ---------- */
const sinMovimiento = () => window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
function contar(el) {
  const v = parseFloat(el.dataset.contar), fmt = el.dataset.fmt || "int";
  const pinta = x => { el.textContent = fmt === "usd" ? usd(x) : Math.round(x).toLocaleString(LOCALE); };
  if (sinMovimiento() || isNaN(v) || document.hidden) return pinta(v);
  const t0 = performance.now(), dur = 1300;
  const paso = t => { const k = Math.min(1, (t - t0) / dur); pinta(v * (1 - Math.pow(1 - k, 3))); if (k < 1) requestAnimationFrame(paso); };
  requestAnimationFrame(paso);
  setTimeout(() => pinta(v), dur + 150);  // si el navegador pausa la animación, el valor final igual queda
}
let observador = null, revisor = null;
function revisarRevelados() {  // respaldo del observador: revisa a mano qué ya está en pantalla
  const pend = document.querySelectorAll(".revelar:not(.visto)");
  pend.forEach(e => {
    const r = e.getBoundingClientRect();
    if (r.height > 0 && r.top < innerHeight - 40 && r.bottom > 0) { e.classList.add("visto"); e.querySelectorAll("[data-contar]").forEach(contar); }
  });
  if (!document.querySelectorAll(".revelar:not(.visto)").length) { clearInterval(revisor); revisor = null; }
}
function observarRevelados() {
  if (!revisor) revisor = setInterval(revisarRevelados, 500);
  addEventListener("scroll", revisarRevelados, { passive: true });
  const els = document.querySelectorAll(".revelar:not(.visto)");
  if (!("IntersectionObserver" in window)) { els.forEach(e => { e.classList.add("visto"); e.querySelectorAll("[data-contar]").forEach(contar); }); return; }
  observador = observador || new IntersectionObserver(entradas => entradas.forEach(en => {
    if (!en.isIntersecting) return;
    en.target.classList.add("visto");
    en.target.querySelectorAll("[data-contar]").forEach(contar);
    observador.unobserve(en.target);
  }), { threshold: 0, rootMargin: "0px 0px -40px 0px" });  // arranca apenas asoma, aunque el elemento sea más alto que la pantalla
  els.forEach(e => observador.observe(e));
}
function animarTab(t) {
  const el = $("t-" + t); if (!el || sinMovimiento()) return;
  el.classList.remove("animar"); void el.offsetWidth; el.classList.add("animar");
  el.querySelectorAll("[data-contar]").forEach(contar);
  clearTimeout(el._animar); el._animar = setTimeout(() => el.classList.remove("animar"), 1800);
}
function pintarDemo() {
  const id = DATA.ia_latam ? "ia_latam" : Object.keys(DATA)[0], d = DATA[id];
  $("sec-demo").classList.toggle("oculto", !d);
  if (!d) return;
  $("demo-sub").textContent = fill(T.demo_sub, {
    name: d.nombre,
    when: new Date(d.generado).toLocaleString(LOCALE, { dateStyle: "medium", timeStyle: "short" }),
  });
  $("demo-kpis").innerHTML = [[d.conteos.recolectadas, "int", T.kpi_pieces], [Object.keys(d.cobertura).length, "int", T.kpi_sources],
    [d.temas.length, "int", T.kpi_topics], [d.costo.total_usd, "usd", T.kpi_cost]]
    .map(([v, f, l]) => `<div><div class="v" data-contar="${v}" data-fmt="${f}">0</div><div class="l">${esc(l)}</div></div>`).join("");
  const minimo = d.min_piezas_top || 3;
  const top = d.temas.map(t => ({ ...t, s: Object.keys(SENALES).reduce((a, k) => a + (d.pesos[k] || 0) * (t.senales[k] || 0), 0) }))
    .sort((a, b) => ((b.volumen >= minimo) - (a.volumen >= minimo)) || (b.s - a.s)).slice(0, 5);
  const max = Math.max(...top.map(t => t.s), 0.0001);
  $("demo-barras").innerHTML = top.map((t, i) => `<div class="demo-fila">
    <div class="nom"><span class="etapa ${t.etapa === "emergente" ? "vivo" : ""}" style="background:var(--${t.etapa})">${esc(etapaLabel(t.etapa))}</span><b title="${esc(t.nombre)}">${esc(t.nombre)}</b></div>
    <div class="val">${pct(t.s)}</div>
    <div class="barra" style="--i:${i}"><i style="width:${t.s / max * 100}%"></i></div></div>`).join("");
  $("demo-ver").onclick = () => abrirResultados(id);
}

function mostrar(v) {
  ["landing", "correr", "res"].forEach(x => { $("vista-" + x).classList.toggle("oculto", x !== v); });
  $("nav-landing").classList.toggle("on", v === "landing");
  $("nav-correr").classList.toggle("on", v === "correr");
  $("nav-res").classList.toggle("on", v === "res");
  history.replaceState(null, "", v === "res" ? "#resultados" + (tab !== "tendencias" ? "/" + tab : "") : v === "correr" ? "#correr" : location.pathname);
  window.scrollTo(0, 0);
  syncLangLinks();
}

/* ---------- correr ---------- */
function pintarCorrer() {
  $("aviso-estatico").classList.toggle("oculto", servidor);
  $("clave-acceso").classList.toggle("oculto", !(MODO === "remoto" && REQUIERE_CLAVE));
  $("clave-acceso").value = leer("radar-clave") || "";
  $("correr").disabled = !servidor;
  const tarjetas = SECTORES.map(s => `<button class="opcion ${!libre && s.id === sectorInicio ? "on" : ""}" data-s="${esc(s.id)}">
    <b>${esc(s.nombre)}</b><small>${DATA[s.id] ? esc(fill(T.last_run, { when: new Date(DATA[s.id].generado).toLocaleString(LOCALE, { dateStyle: "short", timeStyle: "short" }) })) : esc(T.no_runs)}</small></button>`);
  tarjetas.push(`<button class="opcion libre ${libre ? "on" : ""}" data-s="__libre"><b>${esc(T.free_topic)}</b><small>${esc(T.free_topic_help)}</small></button>`);
  $("sectores").innerHTML = tarjetas.join("");
  $("sectores").onclick = e => {
    const b = e.target.closest(".opcion"); if (!b) return;
    if (b.dataset.s === "__libre") libre = true; else { libre = false; sectorInicio = b.dataset.s; guardar("radar-sector", sectorInicio); }
    pintarCorrer(); if (libre) $("nicho").focus();
  };
  $("libre-campos").classList.toggle("oculto", !libre);
  const s = libre ? { redes: (SECTORES[0]?.redes || []).map(r => ({ ...r, activa: true })) } : SECTORES.find(x => x.id === sectorInicio);
  const elegidas = JSON.parse(leer("radar-redes-" + (libre ? "__libre" : sectorInicio)) || "null");
  $("redes").innerHTML = (s?.redes || []).filter(r => r.activa).map(r => {
    const on = r.disponible && (!elegidas || elegidas.includes(r.id));
    return `<label class="opcion red-op ${r.disponible ? "" : "off"}">
      <input type="checkbox" value="${r.id}" ${on ? "checked" : ""} ${r.disponible ? "" : "disabled"}>
      <span><b>${esc(r.nombre)}</b>${r.via ? `<small>${esc(r.via)}</small>` : ""}
      <span class="badge ${r.con_metricas ? "si" : "no"}">${esc(r.con_metricas ? T.with_metrics : T.presence_fit)}</span></span></label>`;
  }).join("");
  $("redes").onchange = () => guardar("radar-redes-" + (libre ? "__libre" : sectorInicio), JSON.stringify(redesElegidas()));
  $("recolectar").disabled = libre; if (libre) $("recolectar").checked = true;
  let nota = MODO === "remoto" ? T.note_remote : MODO === "local" ? T.note_local : "";
  if (libre) nota += (nota ? " " : "") + T.note_free;
  if (USO && USO.limites) nota += (nota ? " " : "") + fill(T.note_usage, { done: USO.completas, limit: USO.limites.completas });
  $("nota-correr").textContent = nota.trim();
}
const redesElegidas = () => [...document.querySelectorAll("#redes input:checked")].map(i => i.value);

let generadoAntes = null, relojInicio = null, relojTimer = null, sectorCorrida = null;

function abrirCarga(titulo, sub) {
  $("carga").classList.remove("oculto");
  $("carga-spin").className = "spinner";
  $("carga-error").classList.add("oculto");
  $("carga-cerrar").classList.add("oculto");
  estadoCarga(titulo, sub);
  if (!relojTimer) {
    relojInicio = relojInicio || Date.now() / 1000;
    relojTimer = setInterval(() => {
      const s = Math.max(0, Math.round(Date.now() / 1000 - relojInicio));
      $("carga-reloj").textContent = `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
    }, 500);
  }
}
function estadoCarga(titulo, sub) { if (titulo) $("carga-titulo").textContent = titulo; if (sub !== undefined) $("carga-sub").textContent = sub; }
function pararReloj() { clearInterval(relojTimer); relojTimer = null; }
function errorCarga(msg, url) {
  pararReloj();
  $("carga").classList.remove("oculto");
  $("carga-spin").className = "spinner mal";
  estadoCarga(T.fail_title, "");
  $("carga-error").textContent = msg;
  $("carga-error").classList.remove("oculto");
  $("carga-cerrar").classList.remove("oculto");
  if (url) { $("carga-gh").href = url; $("carga-gh").classList.remove("oculto"); }
  $("correr").disabled = false;
}
function cerrarCarga() { pararReloj(); relojInicio = null; $("carga").classList.add("oculto"); }

async function correr() {
  const redes = redesElegidas();
  if (!redes.length) { $("nota-correr").textContent = T.err_network; return; }
  const nicho = $("nicho").value.trim(), audiencia = $("audiencia").value.trim();
  if (libre && nicho.length < 3) { $("nota-correr").textContent = T.err_niche; $("nicho").focus(); return; }
  const clave = $("clave-acceso").value.trim();
  if (MODO === "remoto" && REQUIERE_CLAVE && !clave) { $("nota-correr").textContent = T.err_code; $("clave-acceso").focus(); return; }
  sectorCorrida = libre ? "libre_" + (slug(nicho) || "tema") : sectorInicio;
  $("correr").disabled = true;
  generadoAntes = DATA[sectorCorrida]?.generado || null;
  relojInicio = Date.now() / 1000;
  $("pasos").innerHTML = ""; $("log").textContent = ""; $("carga-gh").classList.add("oculto");
  abrirCarga(T.loading_title, MODO === "remoto" ? T.launch_remote : T.launch_local);
  const r = await fetch("/api/correr", { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ sector: sectorCorrida, redes, recolectar: $("recolectar").checked, clave, nicho: libre ? nicho : "", audiencia: libre ? audiencia : "" }) }).catch(() => null);
  if (!r || !r.ok) {
    const e = r ? await r.json().catch(() => ({})) : {};
    if (r && r.status === 401) { guardar("radar-clave", ""); $("clave-acceso").value = ""; }
    errorCarga(r && r.status === 401 ? T.bad_code
      : r && r.status === 409 ? T.busy
      : (e.error || T.launch_fail));
    if (r && r.status === 409) seguirProgreso(false);
    return;
  }
  if (MODO === "remoto" && clave) guardar("radar-clave", clave);
  if (libre) guardar("radar-sector", sectorCorrida);
  estadoCarga(T.queued_title, MODO === "remoto" ? T.queued_sub : "");
  setTimeout(() => seguirProgreso(false), MODO === "remoto" ? 4000 : 800);
}

function pintarPasos(e) {
  if (e.pasos) {
    const cls = { hecho: "hecho", activo: "activo", omitido: "hecho", error: "", pendiente: "" };
    $("pasos").innerHTML = e.pasos.map(p => `<li class="${cls[p.estado]}"><span class="dot"></span>${esc(p.nombre)}${p.estado === "omitido" ? esc(T.step_skipped) : ""}${p.estado === "error" ? esc(T.step_failed) : ""}</li>`).join("")
      + `<li class="${e.corriendo ? "" : "activo"}"><span class="dot"></span>${esc(T.step_show)}</li>`;
    return;
  }
  const actual = Math.max(0, ...e.log.map(l => (l.match(/^PASO (\d)\/6/) || [0, 0])[1] * 1));
  const terminado = !e.corriendo && e.fin;
  $("pasos").innerHTML = PASOS.map((p, i) => {
    const n = i + 1, cls = terminado && !e.error ? "hecho" : n < actual ? "hecho" : n === actual ? "activo" : "";
    return `<li class="${cls}"><span class="dot"></span>${esc(p)}</li>`;
  }).join("");
}

function textoEstado(e) {
  if (e.pasos) {
    const activo = e.pasos.find(p => p.estado === "activo");
    if (!activo) return [T.prep_machine, T.prep_deps];
    return {
      "Crear sector para el nicho": [T.step_niche_title, T.step_niche_sub],
      "Recolectar redes": [T.step_collect_title, T.step_collect_sub],
      "Analizar con JEV y DeepSeek": [T.step_analyze_title, T.step_analyze_sub],
      "Guardar y publicar resultados": [T.step_save_title, T.step_save_sub],
    }[activo.nombre] || [activo.nombre, ""];
  }
  const ult = [...(e.log || [])].reverse().find(l => /^PASO/.test(l));
  return [ult ? ult.replace(/^PASO \d\/6 /, "") + "…" : T.running, ""];
}

async function seguirProgreso(soloSiCorre) {
  const r = await fetch("/api/estado", { cache: "no-store" }).catch(() => null);
  if (!r || !r.ok) { if (!soloSiCorre) setTimeout(() => seguirProgreso(false), 4000); return; }
  const e = await r.json();
  if (e.uso) USO = e.uso;
  if (soloSiCorre && !e.corriendo) return;
  if (e.inicio && (!relojInicio || soloSiCorre)) relojInicio = e.inicio;
  abrirCarga();
  $("correr").disabled = e.corriendo;
  if (e.url) { $("carga-gh").href = e.url; $("carga-gh").classList.remove("oculto"); }
  pintarPasos(e);
  $("log").textContent = (e.log || []).slice(-60).join("\n");
  $("log").scrollTop = 1e9;
  if (e.corriendo) {
    const [t, sub] = textoEstado(e); estadoCarga(t, sub);
    setTimeout(() => seguirProgreso(false), MODO === "remoto" ? 4000 : 1500); return;
  }
  if (e.error) return errorCarga(e.error, e.url);
  const s = e.sector || sectorCorrida || sectorInicio;
  if (MODO === "remoto") return esperarPublicacion(s, 0);
  await cargarDatos();
  terminarCarga(s);
}

async function terminarCarga(s) {
  pararReloj();
  $("carga-spin").className = "spinner ok";
  estadoCarga(T.ready_title, T.ready_sub);
  $("correr").disabled = false;
  try {
    if (MODO === "local") SECTORES = await (await fetch("/api/sectores", { cache: "no-store" })).json();
    else if (MODO === "remoto") SECTORES = await (await fetch("/sectores.json?t=" + Date.now(), { cache: "no-store" })).json();
  } catch (e) {}
  libre = false; sectorInicio = s; pintarCorrer();
  setTimeout(() => { cerrarCarga(); abrirResultados(s); }, 900);
}

async function esperarPublicacion(s, intento) {
  estadoCarga(T.publish_title, T.publish_sub);
  await cargarDatos().catch(() => {});
  if (DATA[s] && (!generadoAntes || DATA[s].generado !== generadoAntes)) return terminarCarga(s);
  if (intento > 45) return errorCarga(T.publish_slow);
  setTimeout(() => esperarPublicacion(s, intento + 1), 4000);
}

/* ---------- resultados ---------- */
function abrirResultados(s) {
  if (!DATA[s]) { mostrar("correr"); return; }
  sector = s; const d = DATA[s];
  pesos = { ...d.pesos }; abiertos = new Set();
  const es30x = !d.marca || d.marca === "30X";
  $("r-titulo").textContent = d.nombre;
  $("r-meta").textContent = fill(T.meta_line, {
    when: new Date(d.generado).toLocaleString(LOCALE, { dateStyle: "medium", timeStyle: "short" }),
    seconds: Math.round(d.duracion_s),
    networks: (d.redes_elegidas || Object.keys(d.cobertura)).length,
  });
  $("r-costo").innerHTML = `${usd(d.costo.total_usd)} <span>${esc(T.cost_this_run)}</span>`;
  $("r-pregunta").textContent = fill(T.question, { topic: s === "ia_latam" ? T.topic_ai : d.nombre.toLowerCase() });
  $("tab-ideas").textContent = es30x ? T.ideas_30x : T.ideas_generic;
  $("ideas-titulo").textContent = es30x ? T.ideas_30x : T.ideas_generic;
  $("leyenda-mov").classList.toggle("oculto", !d.corrida_anterior);
  pintarPesos(); pintarGanchos(); pintarTendencias(); pintarPredicciones(); pintarIdeas(); pintarOrigen(); pintarCosto();
  mostrar("res"); cambiarTab(tab);
}

function cambiarTab(t) {
  tab = t;
  document.querySelectorAll("#tabs button").forEach(b => b.classList.toggle("on", b.dataset.t === t));
  ["tendencias", "viene", "ideas", "origen", "costo"].forEach(x => $("t-" + x).classList.toggle("oculto", x !== t));
  if (!$("vista-res").classList.contains("oculto")) history.replaceState(null, "", location.pathname + "#resultados" + (t !== "tendencias" ? "/" + t : ""));
  window.scrollTo(0, 0);
  animarTab(t);
  syncLangLinks();
}

function pintarPesos() {
  $("pesos").innerHTML = Object.entries(SENALES).map(([k, [n, ayuda]]) => `<div class="peso"><label><span>${esc(n)}</span><span id="v-${k}">${(pesos[k] ?? 0).toFixed(2)}</span></label>
    <input type="range" min="0" max="1" step="0.05" value="${pesos[k] ?? 0}" data-k="${k}" aria-label="${esc(n)}"><small>${esc(ayuda)}</small></div>`).join("");
  $("pesos").oninput = e => { const k = e.target.dataset.k; if (!k) return; pesos[k] = parseFloat(e.target.value); $("v-" + k).textContent = pesos[k].toFixed(2); pintarTendencias(); };
}

// los temas con menos de N piezas (señales tempranas) van siempre detrás de los que tienen respaldo, con cualquier peso
const respaldo = t => (t.volumen || 0) >= (DATA[sector]?.min_piezas_top || 3);
const ranking = (temas, w) => temas.map(t => ({ ...t, s: Object.keys(SENALES).reduce((a, k) => a + (w[k] || 0) * (t.senales[k] || 0), 0) }))
  .sort((a, b) => (respaldo(b) - respaldo(a)) || (b.s - a.s));

function rutaHtml(r) {
  if (!r || !r.ruta || !r.ruta.length) return "";
  return `<div class="ruta">${r.ruta.map((n, i) => `${i ? `<span class="flecha">→ ${r.horas_entre_redes[i - 1] < 48 ? Math.round(r.horas_entre_redes[i - 1]) + " " + T.hours_short : Math.round(r.horas_entre_redes[i - 1] / 24) + " " + T.days_short} →</span>` : ""}
    <a class="nodo ${i === 0 ? "origen" : ""}" href="${esc(enlace(n.url))}" target="_blank" rel="noopener" title="${esc(n.titulo)}"><b>${esc(REDES[n.red] || n.red)}</b> ${fecha(n.fecha)}</a>`).join("")}</div>`;
}

function movHtml(t, i, d) {
  if (!d.corrida_anterior) return "";
  if (!t.rank_anterior) return `<span class="mov nuevo" title="${esc(T.new_title)}">${esc(T.new_badge)}</span>`;
  const delta = t.rank_anterior - (i + 1);
  if (delta > 0) return `<span class="mov up" title="${esc(fill(T.up_title, { n: delta, rank: t.rank_anterior }))}">▲ ${delta}</span>`;
  if (delta < 0) return `<span class="mov down" title="${esc(fill(T.down_title, { n: -delta, rank: t.rank_anterior }))}">▼ ${-delta}</span>`;
  return `<span class="mov igual" title="${esc(T.same_title)}">=</span>`;
}

const nombreGancho = g => (GANCHOS[g] || [g])[0];

function pintarGanchos() {
  const d = DATA[sector], g = d.ganchos || [];
  if (!g.length) { $("ganchos").classList.add("oculto"); return; }
  $("ganchos").classList.remove("oculto");
  const mejor = g.find(x => x.crecimiento_vs_media != null && x.crecimiento_vs_media > 0) || g[0];
  const top = d.temas[0], ganchoTop = top && top.rasgos.gancho[0];
  const fila = x => {
    const c = x.crecimiento_vs_media;
    return `<div class="ganchos-fila"><b title="${esc((GANCHOS[x.gancho] || [])[1] || "")}">${esc(nombreGancho(x.gancho))}</b>
      <div><div class="barra"><i style="width:${pct(x.pct)}%"></i></div><span class="nota">${esc(fill(T.pct_pieces, { pct: pct(x.pct) }))}</span></div>
      <span class="crec ${c == null ? "" : c >= 0 ? "pos" : "neg"}">${c == null ? esc(T.no_metrics) : (c >= 0 ? "+" : "") + Math.round(c * 100) + esc(T.growth_suffix)}</span></div>`;
  };
  const growth = mejor.crecimiento_vs_media != null
    ? fill(T.hook_growth, { pct: Math.round(mejor.crecimiento_vs_media * 100) })
    : T.hook_most_used;
  const sentence = fill(T.hook_sentence, { hook: "<b>" + esc(nombreGancho(mejor.gancho).toLowerCase()) + "</b>", growth });
  const extra = ganchoTop ? " " + fill(T.hook_top, {
    topic: esc(top.nombre),
    pct: pct(ganchoTop.pct),
    hook: "<b>" + esc(nombreGancho(ganchoTop.valor).toLowerCase()) + "</b>",
  }) : "";
  $("ganchos").innerHTML = `<h3 class="sec">${esc(T.hook_question)}</h3>
    <div class="insight">${sentence}${extra}
    <span class="nota">${esc(T.hook_example)} <a href="${esc(enlace(mejor.ejemplo.url))}" target="_blank" rel="noopener">${esc(mejor.ejemplo.titulo)}</a></span></div>
    <details><summary class="nota" style="cursor:pointer;color:var(--accent);font-weight:600">${esc(T.hook_see_all)}</summary>
    ${g.slice(0, 6).map(fila).join("")}
    <p class="nota" style="margin:8px 0 0">${esc(T.hook_note)}</p></details>`;
}

function pintarTendencias() {
  const d = DATA[sector];
  const original = ranking(d.temas, d.pesos).map(t => t.id);
  const actual = ranking(d.temas, pesos).slice(0, 10);
  const cambiados = JSON.stringify(pesos) !== JSON.stringify(d.pesos);
  const max = Math.max(...actual.map(t => t.s), 0.0001);
  if (!actual.length) { $("lista").innerHTML = `<div class="card vacio">${esc(T.no_topics)}</div>`; return; }
  $("lista").innerHTML = actual.map((t, i) => {
    const antes = original.indexOf(t.id) + 1;
    const redes = Object.entries(t.redes).sort((a, b) => b[1] - a[1]).map(([r, n]) => `<span class="chip">${esc(REDES[r] || r)} · ${n}</span>`).join("");
    const g = t.rasgos.gancho.map(x => `${nombreGancho(x.valor).toLowerCase()} ${pct(x.pct)}%`).join(", ");
    const f = t.rasgos.formato.map(x => `${FORMATOS[x.valor] || x.valor} ${pct(x.pct)}%`).join(", ");
    const fuentes = (t.rastreo?.fuentes_externas || []).map(x => `<a href="${esc(x.url)}" target="_blank" rel="noopener">${esc(x.dominio)}</a> (${x.veces})`).join(", ");
    const senales = Object.entries(SENALES).map(([k, [n]]) => `<div>${esc(n)} ${pct(t.senales[k])}<div class="barra"><i style="width:${Math.min(100, pct(t.senales[k]))}%"></i></div></div>`).join("");
    const piezas = t.top_piezas.map(p => `<li><a href="${esc(enlace(p.url))}" target="_blank" rel="noopener">${esc(p.titulo || p.url)}</a>
      <span class="red-t">${esc(REDES[p.red] || p.red)}${p.cuenta ? " · " + esc(p.cuenta) : ""}${p.con_metricas ? "" : " · " + esc(T.no_metrics)}</span></li>`).join("");
    return `<div class="card tema ${abiertos.has(t.id) ? "abierto" : ""}" data-id="${esc(t.id)}" style="--i:${i}">
      <div class="rank">${i + 1}<div>${movHtml(t, i, d)}</div></div>
      <div><h4>${esc(t.nombre)}<span class="etapa ${t.etapa === "emergente" ? "vivo" : ""}" style="background:var(--${t.etapa})">${esc(etapaLabel(t.etapa))}</span></h4></div>
      <div class="score"><b>${pct(t.s)}</b><small>${esc(T.score_label)}</small><div class="barra"><i style="width:${t.s / max * 100}%"></i></div>${cambiados && antes !== i + 1 ? `<small>${esc(fill(T.original_rank, { n: antes }))}</small>` : ""}</div>
      <div class="full">
        <p class="porque">${esc(t.porque || "")}</p>
        <div class="chips">${redes}<span class="chip gris">${esc(fill(T.pieces_week, { n: t.volumen, week: t.piezas_7d }))}</span>${t.aceleracion_estimada ? `<span class="chip gris" title="${esc(T.accel_title)}">${esc(T.accel_est)}</span>` : ""}</div>
        ${rutaHtml(t.rastreo)}
        <div class="detalle">
          <div class="senales">${senales}</div>
          <div>${esc(T.hooks_label)} ${esc(g)} · ${esc(T.formats_label)} ${esc(f)} · ${esc(T.launch_label)} ${pct(t.rasgos.menciona_lanzamiento)}%</div>
          ${fuentes ? `<div style="margin-top:6px">${esc(T.ext_sources)} ${fuentes}</div>` : ""}
          <ul class="piezas">${piezas}</ul>
        </div>
        <button class="btn chico ver">${esc(abiertos.has(t.id) ? T.hide_detail : T.show_detail)}</button>
      </div></div>`;
  }).join("");
  $("lista").onclick = e => {
    if (!e.target.classList.contains("ver")) return;
    const id = e.target.closest(".tema").dataset.id;
    abiertos.has(id) ? abiertos.delete(id) : abiertos.add(id); pintarTendencias();
  };
}

function pintarPredicciones() {
  const d = DATA[sector], nombres = Object.fromEntries(d.temas.map(t => [t.id, t.nombre]));
  const ps = d.predicciones || [];
  if (!ps.length) { $("preds").innerHTML = `<div class="card vacio">${esc(T.no_predictions)}</div>`; return; }
  $("preds").innerHTML = ps.map((p, i) => `<div class="card pred" style="--i:${i}">
    <div class="n">${i + 1}</div>
    <div>
      <h4>${esc(p.nombre)} <span class="chip gris">${esc(p.ventana)}</span></h4>
      <div class="medidor"><span>${esc(T.sig_fuerza)}</span><div class="barra"><i style="width:${pct(p.fuerza)}%"></i></div><b>${pct(p.fuerza)}</b></div>
      <ul class="puntos">
        <li><svg class="ico"><use href="#i-bulb"/></svg><div><b>${esc(T.why)}</b>${esc(p.tesis)}</div></li>
        <li><svg class="ico"><use href="#i-eye"/></svg><div><b>${esc(T.signal_watch)}</b>${esc(p.senal_a_vigilar)}</div></li>
        <li><svg class="ico"><use href="#i-pen"/></svg><div><b>${esc(T.publish_today)}</b>${esc(p.que_publicar_hoy)} <button class="btn chico" data-copiar-pred="${i}" style="margin-left:6px"><svg class="ico" style="width:14px;height:14px"><use href="#i-copy"/></svg>${esc(T.copy)}</button></div></li>
      </ul>
      ${p.basado_en.length ? `<div class="chips"><span class="nota">${esc(T.based_on)}</span>${p.basado_en.map(b => `<span class="chip">${esc(nombres[b] || b)}</span>`).join("")}</div>` : ""}
      <div class="mini"><span>${esc(T.data_support)} <b>${pct(p.respaldo_datos)}</b></span>${p.jev ? `<span>${esc(T.audience_interest)} <b>${pct(p.jev.interes_audiencia)}</b></span><span>${esc(T.novelty)} <b>${pct(p.jev.novedad)}</b></span>` : ""}</div>
    </div>
  </div>`).join("");
  $("preds").onclick = e => { const b = e.target.closest("[data-copiar-pred]"); if (b) copiar(ps[+b.dataset.copiarPred].que_publicar_hoy); };
}

function textoIdea(i) { return `${i.formato}: ${i.titulo}\n\n${T.idea_hook} ${i.gancho}\n\n${i.desarrollo}`; }
function promptIdea(i, d) {
  const tema = d.temas[0];
  const entrega = /carrusel/i.test(i.formato) ? T.delivery_carousel
    : /reel|tiktok|video/i.test(i.formato) ? T.delivery_reel
    : T.delivery_post;
  const rol = !d.marca || d.marca === "30X" ? T.prompt_role_30x : T.prompt_role;
  const why = tema && tema.porque ? " " + T.prompt_why + " " + tema.porque : "";
  const q1 = LANG === "es" ? "«" : "\"";
  const q2 = LANG === "es" ? "»" : "\"";
  return [
    rol,
    T.prompt_theme + " " + d.nombre + ".",
    T.prompt_trend + " " + q1 + (tema ? tema.nombre : "") + q2 + " (" + T.prompt_stage + " " + (tema ? tema.etapa : "") + ")." + why,
    "",
    fill(T.prompt_create, { format: i.formato.toLowerCase() }),
    "- " + T.prompt_title + " " + i.titulo,
    "- " + T.prompt_hook + " " + i.gancho,
    "- " + T.prompt_body + " " + i.desarrollo,
    "",
    fill(T.prompt_write, { delivery: entrega }),
  ].join("\n");
}

function pintarIdeas() {
  const d = DATA[sector];
  $("ideas-tema").textContent = d.temas[0] ? fill(T.ideas_sub, { name: d.temas[0].nombre }) : "";
  const ideas = d.ideas || [];
  $("ideas").innerHTML = ideas.map((i, n) => `<div class="card idea" style="--i:${n}">
    <div class="etq">${esc(i.formato)}</div><h4>${esc(i.titulo)}</h4>
    <p class="gancho">“${esc(i.gancho)}”</p><div style="font-size:14px">${esc(i.desarrollo)}</div>
    ${i.jev ? `<div class="mini"><span>${esc(T.audience_fit)} <b>${pct(i.jev.ajuste_audiencia.score)}</b></span><span>${esc(T.hook_strength)} <b>${pct(i.jev.fuerza_gancho.score)}</b></span></div>` : ""}
    <div class="acc">
      <button class="btn chico" data-texto="${n}"><svg class="ico" style="width:14px;height:14px"><use href="#i-copy"/></svg>${esc(T.copy_text)}</button>
      <button class="btn chico primario" data-prompt="${n}"><svg class="ico" style="width:14px;height:14px"><use href="#i-copy"/></svg>${esc(T.copy_prompt)}</button>
    </div>
  </div>`).join("") || `<div class="card vacio">${esc(T.no_ideas)}</div>`;
  $("ideas").onclick = e => {
    const tb = e.target.closest("[data-texto]"), p = e.target.closest("[data-prompt]");
    if (tb) copiar(textoIdea(ideas[+tb.dataset.texto]));
    if (p) copiar(promptIdea(ideas[+p.dataset.prompt], d));
  };
}

function pintarOrigen() {
  const d = DATA[sector], top = d.temas.slice(0, 10);
  const conteo = {};
  top.forEach(t => { const o = t.rastreo?.origen?.red; if (o) conteo[o] = (conteo[o] || 0) + 1; });
  const total = Object.values(conteo).reduce((a, b) => a + b, 0) || 1;
  $("origen-barras").innerHTML = Object.entries(conteo).sort((a, b) => b[1] - a[1]).map(([r, n]) =>
    `<div class="fila"><span>${esc(REDES[r] || r)}</span><div class="barra"><i style="width:${n / total * 100}%"></i></div><b>${n}</b></div>`).join("") || `<p class="nota">${esc(T.no_dates)}</p>`;
  const saltos = top.flatMap(t => t.rastreo?.horas_entre_redes || []);
  $("origen-nota").textContent = saltos.length ? fill(T.origin_note, { days: Math.round(saltos.reduce((a, b) => a + b, 0) / saltos.length / 24 * 10) / 10 }) : "";
  const fuentes = {};
  top.forEach(t => (t.rastreo?.fuentes_externas || []).forEach(f => { fuentes[f.dominio] = fuentes[f.dominio] || { ...f, veces: 0 }; fuentes[f.dominio].veces += f.veces; }));
  const lf = Object.values(fuentes).sort((a, b) => b.veces - a.veces).slice(0, 8);
  $("fuentes").innerHTML = lf.length ? `<table><tr><th>${esc(T.source_th)}</th><th class="n">${esc(T.cites_th)}</th></tr>${lf.map(f => `<tr><td><a href="${esc(f.url)}" target="_blank" rel="noopener">${esc(f.dominio)}</a></td><td class="n">${f.veces}</td></tr>`).join("")}</table>`
    : `<p class="nota">${esc(T.ext_note)}</p>`;
  $("rutas").innerHTML = top.map(t => `<div style="margin-bottom:14px"><b>${esc(t.nombre)}</b> <span class="nota">· ${esc(fill(T.active_days, { days: t.rastreo?.dias_activo ?? "?" }))}</span>${rutaHtml(t.rastreo)}</div>`).join("");
}

function pintarCosto() {
  const d = DATA[sector], c = d.costo, mensual = c.total_usd * 8 * 30;
  $("costo-resumen").textContent = fill(T.cost_summary, { cost: usd(c.total_usd), n: d.conteos.recolectadas, month: usd(mensual) });
  $("kpis").innerHTML = [[c.total_usd, T.kpi_run], [c.por_tema_usd, T.kpi_topic], [mensual, T.kpi_month]]
    .map(([v, l], i) => `<div class="card kpi" style="--i:${i}"><div class="v" data-contar="${v}" data-fmt="usd">${usd(v)}</div><div class="l">${esc(l)}</div></div>`).join("");
  const nombres = {
    jev_piezas: T.cost_jev_pieces, jev_ideas: T.cost_jev_ideas, jev_predicciones: T.cost_jev_predictions,
    llm_temas: T.cost_llm_topics, llm_redaccion: T.cost_llm_writing, llm_predicciones: T.cost_llm_predictions, llm_sector: T.cost_llm_sector,
  };
  const filas = Object.entries(c.pasos).sort((a, b) => b[1].usd - a[1].usd).map(([k, v]) => `<tr><td>${esc(nombres[k] || k.replace("busqueda_", T.web_search_prefix).replaceAll("_", " "))}</td>
    <td class="n">${v.llamadas}</td><td class="n">${usd(v.usd)}</td></tr>`).join("");
  $("costo-tabla").innerHTML = `<tr><th>${esc(T.th_step)}</th><th class="n">${esc(T.th_calls)}</th><th class="n">${esc(T.th_usd)}</th></tr>${filas}<tr><td><b>${esc(T.total)}</b></td><td></td><td class="n"><b>${usd(c.total_usd)}</b></td></tr>`;
  $("cobertura").innerHTML = `<tr><th>${esc(T.th_network)}</th><th class="n">${esc(T.th_pieces)}</th><th class="n">${esc(T.th_in_rank)}</th><th class="n">${esc(T.th_with_metrics)}</th><th>${esc(T.th_via)}</th></tr>` +
    Object.entries(d.cobertura).map(([r, v]) => `<tr><td>${esc(REDES[r] || r)}</td><td class="n">${v.recolectadas}</td><td class="n">${v.en_ranking}</td><td class="n">${v.con_metricas}</td><td>${esc(v.vias.map(x => VIAS[x] || x).join(", "))}</td></tr>`).join("");
  const n = d.conteos;
  $("conteos").textContent = fill(T.counts_line, {
    collected: n.recolectadas, ranked: n.en_ranking, out: n.fuera_de_sector, none: n.sin_tema ?? 0, low: n.baja_confianza,
  });
  const h = c.historial || [], hmax = Math.max(...h.map(x => x.usd), 0.0001);
  $("hist").innerHTML = h.slice(-30).map(x => `<i style="height:${x.usd / hmax * 100}%" title="${esc(new Date(x.generado).toLocaleString(LOCALE))}: ${usd(x.usd)}"></i>`).join("");
  $("hist-nota").textContent = h.length ? fill(T.hist_line, { n: h.length, cost: usd(h.reduce((a, x) => a + x.usd, 0)) }) : "";
  const g = leer("radar-pago"); if (g) $("pago-actual").value = g;
  pintarAhorro();
}

function pintarAhorro() {
  const v = parseFloat($("pago-actual").value), c = DATA[sector]?.costo; if (!c) return;
  const mensual = c.total_usd * 8 * 30;
  if (!isNaN(v)) guardar("radar-pago", v);
  $("ahorro-res").textContent = isNaN(v) || v <= 0
    ? fill(T.savings_only, { month: usd(mensual) })
    : fill(T.savings_compare, { pay: usd(v), month: usd(mensual), pct: Math.round(mensual / v * 1000) / 10 });
}

init();
