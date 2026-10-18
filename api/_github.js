// Utilidades compartidas: llamadas a la API de GitHub con el token guardado en Vercel (GH_TOKEN).
const WORKFLOW = "radar.yml";

function config() {
  const repo = process.env.GH_REPO, token = process.env.GH_TOKEN;
  if (!repo || !token) throw new Error("Faltan GH_REPO o GH_TOKEN en las variables de entorno de Vercel");
  return { repo, token, ref: process.env.GH_REF || "main" };
}

// se ignoran espacios y comillas sobrantes, que suelen colarse al copiar y pegar
const limpiar = v => String(v || "").trim().replace(/^["']+|["']+$/g, "").trim();

// Código de acceso opcional: si RADAR_CLAVE_ACCESO está vacía, cualquiera puede correr (con límite diario).
const claveRequerida = () => limpiar(process.env.RADAR_CLAVE_ACCESO);

const LIMITES = {
  completas: parseInt(process.env.LIMITE_DIARIO || "8", 10),        // con datos nuevos (gastan cuota de YouTube y Tavily)
  reanalisis: parseInt(process.env.LIMITE_REANALISIS || "30", 10),  // sin recolectar (solo JEV + DeepSeek)
};

async function gh(ruta, opciones = {}) {
  const { repo, token } = config();
  const r = await fetch(`https://api.github.com/repos/${repo}${ruta}`, {
    ...opciones,
    headers: { Authorization: `Bearer ${token}`, Accept: "application/vnd.github+json",
      "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "radar-30x", ...(opciones.headers || {}) },
  });
  if (!r.ok && r.status !== 204) throw new Error(`GitHub ${r.status}: ${(await r.text()).slice(0, 200)}`);
  return r.status === 204 ? null : r.json();
}

async function ultimaCorrida() {
  const d = await gh(`/actions/workflows/${WORKFLOW}/runs?event=workflow_dispatch&per_page=1`);
  return d.workflow_runs[0] || null;
}

// Corridas lanzadas hoy (UTC), separadas entre completas y reanálisis (el título lo indica).
async function usoHoy() {
  const hoy = new Date().toISOString().slice(0, 10);
  const d = await gh(`/actions/workflows/${WORKFLOW}/runs?event=workflow_dispatch&created=%3E%3D${hoy}&per_page=100`);
  const runs = d.workflow_runs || [];
  const reanalisis = runs.filter(r => /reanálisis/.test(r.display_title)).length;
  return { completas: runs.length - reanalisis, reanalisis, limites: LIMITES };
}

module.exports = { WORKFLOW, config, gh, ultimaCorrida, usoHoy, limpiar, claveRequerida, LIMITES };
