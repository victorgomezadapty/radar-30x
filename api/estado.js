// GET /api/estado -> progreso de la última corrida lanzada desde la web (pasos del flujo de GitHub Actions).
const { gh, ultimaCorrida, usoHoy, claveRequerida } = require("./_github");
const PASOS = ["Crear sector para el nicho", "Recolectar redes", "Analizar con JEV y DeepSeek", "Guardar y publicar resultados"];

module.exports = async (req, res) => {
  res.setHeader("Cache-Control", "no-store");
  try {
    const [run, uso] = await Promise.all([ultimaCorrida(), usoHoy().catch(() => null)]);
    const base = { modo: "remoto", requiereClave: !!claveRequerida(), uso };
    if (!run) return res.json({ ...base, corriendo: false, log: [], pasos: [], inicio: null, fin: null });
    const jobs = await gh(`/actions/runs/${run.id}/jobs`);
    const steps = (jobs.jobs[0] && jobs.jobs[0].steps) || [];
    const pasos = PASOS.map(nombre => {
      const s = steps.find(x => x.name === nombre);
      const estado = !s ? "pendiente" : s.status !== "completed" ? (s.status === "in_progress" ? "activo" : "pendiente")
        : s.conclusion === "skipped" ? "omitido" : s.conclusion === "success" ? "hecho" : "error";
      return { nombre, estado };
    });
    const corriendo = run.status !== "completed";
    const preparando = corriendo && !pasos.some(p => p.estado !== "pendiente");
    const log = [
      `Corrida #${run.run_number} · ${run.display_title}`,
      ...(preparando ? ["Preparando el entorno en GitHub Actions…"] : []),
      ...pasos.filter(p => p.estado !== "pendiente" && p.estado !== "omitido").map(p => `${{ hecho: "✓", activo: "…", omitido: "–", error: "✗" }[p.estado]} ${p.nombre}`),
    ];
    res.json({
      ...base, corriendo, pasos: pasos.filter(p => p.nombre !== PASOS[0] || ["activo", "hecho", "error"].includes(p.estado)), log, url: run.html_url,
      sector: (run.display_title.match(/Radar ([a-z0-9_]+)/) || [])[1] || null,
      inicio: Date.parse(run.run_started_at || run.created_at) / 1000,
      fin: corriendo ? null : Date.parse(run.updated_at) / 1000,
      error: !corriendo && run.conclusion !== "success" ? `La corrida terminó con estado "${run.conclusion}". Detalle en GitHub Actions.` : null,
    });
  } catch (e) {
    res.status(500).json({ modo: "remoto", error: String(e.message || e) });
  }
};
