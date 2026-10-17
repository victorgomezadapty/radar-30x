// Utilidades compartidas: llamadas a la API de GitHub con el token guardado en Vercel (GH_TOKEN).
const WORKFLOW = "radar.yml";

function config() {
  const repo = process.env.GH_REPO, token = process.env.GH_TOKEN;
  if (!repo || !token) throw new Error("Faltan GH_REPO o GH_TOKEN en las variables de entorno de Vercel");
  return { repo, token, ref: process.env.GH_REF || "main" };
}

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

module.exports = { WORKFLOW, config, gh, ultimaCorrida };
